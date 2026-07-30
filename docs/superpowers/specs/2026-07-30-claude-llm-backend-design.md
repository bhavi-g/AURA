# Design: Claude LLM backend + provider abstraction (Phase 2)

**Status:** approved
**Phase:** [docs/phases/phase-2.md](../../phases/phase-2.md)
**ADR:** [0003-llm-provider-abstraction](../../adr/0003-llm-provider-abstraction.md)
**Date:** 2026-07-30

## Problem

`core/llm.py` only speaks to OpenAI. Per ADR 0003, the provider was always meant
to be swappable, with Anthropic/Claude as the next backend. Adding it raises the
quality ceiling of every explanation (`aura explain --llm`, `aura explain-llm`)
and every fix diff (`aura fix`) the rest of the pipeline consumes, without
changing any public CLI/API behavior.

## Goal

Introduce a provider interface with `openai`, `anthropic`, and `stub`
implementations, selected by `AURA_LLM_PROVIDER` (env) or `LLMConfig.provider`
(explicit, mainly for tests), with an auto-detect fallback chain when neither is
set. Keep `LLM`'s public interface (`LLM(config)`, `.complete()`,
`.acomplete()`) byte-for-byte unchanged for every existing caller
(`cli.py`, `explain.py`, `fix.py`). Keep the deterministic stub as the
no-key/no-SDK fallback — this must never crash the pipeline.

## Architecture

`core/llm.py` becomes a thin `LLM` facade over three small, independently
testable backend classes, each implementing the same informal protocol:

```python
async def acomplete(self, prompt: str, *, model: str | None, temperature: float | None, max_tokens: int | None) -> str
```

- **`_StubBackend`** — today's exact dummy-response logic, moved as-is. Text
  contract unchanged (`"[LLM STUB] No real LLM configured..."` prefix,
  `"Prompt preview:"` substring) so `test_llm_stub.py` keeps passing unmodified.
- **`_OpenAIBackend`** — today's `AsyncOpenAI` call, unchanged behavior. Default
  model `gpt-4o-mini`, forwards `temperature` and `max_tokens` as today.
- **`_AnthropicBackend`** — new. Wraps `AsyncAnthropic`. Default model
  `claude-sonnet-5` (current-gen Sonnet: best cost/quality fit for high-volume
  explain/fix generation, matches CLAUDE.md's "Sonnet by default" rule, and is
  the "latest cost-effective Claude model" Phase 2 calls for).

`LLM.__init__` resolves exactly one backend instance and stores it; `complete`/
`acomplete` just delegate to it. No branching lives in `LLM` itself.

## Provider resolution

Order of precedence, evaluated once at `LLM.__init__`:

1. `LLMConfig.provider` if set (`"openai"` | `"anthropic"`) — explicit override,
   primarily for tests.
2. `AURA_LLM_PROVIDER` env var if set to a recognized value.
3. Auto-detect: try Anthropic first (package importable **and**
   `ANTHROPIC_API_KEY` set), then OpenAI (package importable **and**
   `OPENAI_API_KEY` set), then stub.

If a provider is explicitly requested (step 1 or 2) but its package/key isn't
available, degrade straight to `_StubBackend` — do **not** fall through to the
other provider. An unrecognized `AURA_LLM_PROVIDER` value is treated the same
as unset (falls through to auto-detect).

This means: an existing user with only `OPENAI_API_KEY` set sees no change
(OpenAI still wins, since anthropic isn't configured). A user who sets
`ANTHROPIC_API_KEY` — with or without ever hearing about `AURA_LLM_PROVIDER` —
gets Claude automatically.

## `_AnthropicBackend` — deviations from a naive port

Claude Sonnet 5 has two API behaviors that a straight port of the OpenAI call
shape would violate or silently misuse (see the model docs cached in this
project's tooling): non-default sampling parameters are rejected outright, and
thinking runs adaptively by default, sharing the same `max_tokens` budget as
the visible response.

1. **Never forwards `temperature`/`top_p`/`top_k`.** Claude Sonnet 5 returns
   400 on a non-default sampling value; the shared `LLMConfig.temperature`
   default (0.2) is non-default. No current call site passes an explicit
   `temperature` override, so this backend simply never sends the parameter,
   regardless of what's in config — documented as a known limitation of this
   backend, not a bug.
2. **Explicitly disables thinking** (`thinking={"type": "disabled"}`). These
   are short, deterministic completions (an explanation paragraph, a unified
   diff) — not agentic reasoning — and Sonnet 5 runs adaptive thinking by
   default when `thinking` is omitted, which shares `max_tokens` (unchanged
   default: 512) with the response text. Without disabling it, a fix-diff
   generation could burn most of the budget on thinking and return a
   truncated (or empty) diff. Disabling avoids that failure mode entirely at
   the cost of losing reasoning depth we don't need for this use case.
3. **Guards against the known disabled-thinking tag-leak failure mode.** Adds
   a short `system` instruction: *"Respond with only the requested output. Do
   not include internal reasoning, `<thinking>` tags, or other internal/system
   XML tags in your response."* Cheap, and directly targets a documented
   failure mode of disabled thinking.
4. **Extracts only `text`-type content blocks** from `response.content` when
   building the returned string (ignores any other block type).

`max_tokens` default stays the shared `LLMConfig` default (512) — with thinking
disabled there's no budget contention, so no provider-specific override is
needed.

## Config change

`LLMConfig.model` default changes from `"gpt-4o-mini"` to `None`. Each backend
supplies its own default when the resolved model is `None`. No test or caller
depends on the old literal default (confirmed via search). `temperature` and
`max_tokens` defaults are unchanged. `LLMConfig` gains one new field:
`provider: str | None = None`.

## Error handling

API errors at call time (auth, rate limit, network) propagate as exceptions —
same as the current (uncaught) OpenAI path today. Only a *missing key or SDK*
degrades to the stub. This is a deliberate non-change: NEVER_DO.md's
"never let an analyzer crash the pipeline" applies to analyzer adapters, not
the LLM layer, and ADR 0003's contract has only ever been "no key/SDK → stub."

## Dependency

`anthropic` becomes a hard dependency in `pyproject.toml`, next to `openai`
(same precedent — `openai` is already a hard dependency despite ADR 0003's
"optional import" framing). The import itself stays wrapped in try/except
(`AsyncAnthropic = None` on `ImportError`) for resilience, matching the
existing OpenAI pattern.

## Testing

- `tests/test_llm_stub.py` — unchanged, must keep passing (no env vars set,
  stub wins).
- New: provider resolution tests — `AURA_LLM_PROVIDER=anthropic` with no key →
  stub; `AURA_LLM_PROVIDER=openai` with no key → stub; unset + only
  `ANTHROPIC_API_KEY` present → anthropic backend selected; unset + only
  `OPENAI_API_KEY` present → openai backend selected (unchanged from today);
  unset + both present → anthropic wins.
- New: `_AnthropicBackend` unit tests using a monkeypatched fake
  `AsyncAnthropic`-shaped client (no real network calls) asserting: no
  `temperature`/`top_p`/`top_k` key in the constructed request, `thinking`
  key is `{"type": "disabled"}`, default model is `claude-sonnet-5` when none
  given, and that only `text`-type content blocks are concatenated into the
  returned string.
- Existing `tests/test_api_explain_llm.py` / `tests/test_explain_llm_prompt.py`
  keep passing unmodified (they exercise the stub path today; no behavior
  changes there).

## Docs

- `.env.example`: add `ANTHROPIC_API_KEY=` and a comment on `AURA_LLM_PROVIDER`
  and the auto-detect precedence.
- ADR 0003: its "Next" line becomes stale once this ships — will be addressed
  at session-log time (flip to reflect the new state), not part of this spec.

## Out of scope (per Phase 2's own scope line, and to avoid scope creep)

- Local/offline models, streaming to the CLI.
- Changing OpenAI backend behavior/defaults in any way.
- Retry/fallback-model logic on Anthropic API errors (e.g. refusal handling,
  server-side fallbacks) — not needed for this internal, non-adversarial
  use case; can be a later ADR if it becomes a real problem.
- Prompt content changes (`build_llm_explanation_prompt` /
  `build_llm_remediation_prompt` stay as they are); Phase 2's "improve
  explain/fix prompts" line is deferred to a follow-up change once the
  provider is in and the team can compare Claude's output on the current
  prompts first.
