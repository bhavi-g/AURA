# 0004 — Verify generated fixes before presenting them

**Status:** accepted (2026-07-30) — implemented in [#26](https://github.com/bhavi-g/AURA/pull/26)

## Context
`aura fix` currently emits an LLM-generated unified diff and stops. For a security
tool, presenting an unverified fix as "PR-ready" is a credibility and safety risk:
the diff might not apply, might not compile, or might not actually remove the
vulnerability — and could even introduce new ones.

## Decision
Before presenting a fix, run a **closed-loop verification** in a temp workdir:
apply the diff → compile with `solc` → re-run the analyzer → compare findings, and
emit a verdict (`VERIFIED` / `REGRESSED` / `FAILED`). On failure, feed the error
back to the LLM and retry (bounded). The user's file is only modified with
`--write`. When tools are unavailable, degrade to compile-only and label the
result `UNVERIFIED` rather than claiming success.

## Consequences
- `fix` gains real dependencies on `solc` + analyzer at fix time (with degradation).
- Fix latency increases (apply + compile + re-analyze, possibly ×retries).
- "PR-ready" becomes a defensible claim, not marketing.
- Full design: `docs/superpowers/specs/2026-07-25-verified-fix-loop-design.md` (P1).
