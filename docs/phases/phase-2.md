# Phase 2 — Claude LLM backend + provider abstraction

**Status:** done (2026-07-30) — PRs [#28](https://github.com/bhavi-g/AURA/pull/28), [#29](https://github.com/bhavi-g/AURA/pull/29)
**ADR:** [0003-llm-provider-abstraction](../adr/0003-llm-provider-abstraction.md)

## Why
`core/llm.py` is OpenAI-only and silently falls back to a stub with no key.
Adding an Anthropic/Claude backend raises the quality ceiling of every
explanation and every fix the P1 loop consumes.

## What v1 of this does
- Introduce a provider interface (`complete`/`acomplete`) with implementations
  for OpenAI and Anthropic, selected by env/config (`AURA_LLM_PROVIDER`).
- Default to the latest cost-effective Claude model; keep OpenAI as an option.
- Keep the deterministic stub as the no-key fallback.
- Improve explain/fix prompts now that we control the provider.

## Out of scope
- Local/offline models; streaming to the CLI.

## Success criteria
- Same CLI/API behavior, provider swappable via config
- No provider SDK required at import time (optional imports, graceful fallback)
