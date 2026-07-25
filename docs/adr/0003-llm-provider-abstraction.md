# 0003 — LLM behind a thin wrapper; stub fallback; Claude next

**Status:** accepted (backfilled 2026-07-24)

## Context
Explanations and remediations need an LLM, but development shouldn't require a
paid API key, and the provider shouldn't be hard-wired into calling code.

## Decision
All LLM access goes through `core/llm.py` (`LLM.complete` / `.acomplete`). If the
provider SDK is installed **and** a key is set, use the real API; otherwise return
a deterministic stub so the pipeline still runs. Provider SDK imports are
optional (no hard import-time dependency).

Currently OpenAI (`gpt-4o-mini`). **Next:** generalize to a provider interface and
add an Anthropic/Claude backend, defaulting to the latest cost-effective Claude
model (see `docs/phases/phase-2.md`).

## Consequences
- Callers never touch a vendor SDK directly.
- No key / no SDK → stub, not a crash.
- Provider choice will move behind config (`AURA_LLM_PROVIDER`) in P2.
