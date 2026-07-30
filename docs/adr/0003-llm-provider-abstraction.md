# 0003 — LLM behind a thin wrapper; stub fallback; Claude next

**Status:** accepted (backfilled 2026-07-24; provider abstraction implemented 2026-07-30, PR #28)

## Context
Explanations and remediations need an LLM, but development shouldn't require a
paid API key, and the provider shouldn't be hard-wired into calling code.

## Decision
All LLM access goes through `core/llm.py` (`LLM.complete` / `.acomplete`). If the
provider SDK is installed **and** a key is set, use the real API; otherwise return
a deterministic stub so the pipeline still runs. Provider SDK imports are
optional (import wrapped in try/except; both `openai` and `anthropic` are hard
`pyproject.toml` dependencies in practice, matching the precedent `openai`
already set — "optional" means graceful fallback at runtime, not an uninstalled
package).

**Implemented 2026-07-30 (Phase 2, PR #28):** `LLM` is now a thin facade over
`_StubBackend` / `_OpenAIBackend` / `_AnthropicBackend`. Provider selection is
`LLMConfig.provider` (explicit) > `AURA_LLM_PROVIDER` env var > auto-detect
(Anthropic first, then OpenAI, then stub) — an explicitly requested but
unavailable provider degrades straight to the stub rather than falling
through to the other. `_AnthropicBackend` defaults to `claude-sonnet-5` (the
"latest cost-effective Claude model" this ADR called for) and never forwards
`temperature`/`top_p`/`top_k` (Sonnet 5 rejects non-default sampling values)
and unconditionally disables thinking (short deterministic completions don't
need it, and adaptive thinking would otherwise share the same `max_tokens`
budget as the response text).

## Consequences
- Callers never touch a vendor SDK directly.
- No key / no SDK → stub, not a crash.
- Provider choice now lives behind config (`AURA_LLM_PROVIDER` / `LLMConfig.provider`), as planned.
