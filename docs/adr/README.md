# Architecture Decision Records (ADR)

Each ADR captures one real decision: the context, the choice, and the
consequences. Read this index at the start of every session before writing code.

Format: `NNNN-short-title.md`. Statuses: `accepted`, `superseded`, `proposed`.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-cli-first-typer.md) | CLI-first product surface with Typer | accepted |
| [0002](0002-slither-primary-detector.md) | Slither as primary detector; Mythril optional | accepted |
| [0003](0003-llm-provider-abstraction.md) | LLM behind a thin wrapper; stub fallback; Claude next | accepted |
| [0004](0004-verified-fix-loop.md) | Verify generated fixes before presenting them | accepted |

> ADRs 0001–0003 are **backfilled** from decisions already visible in the code
> (this project is 20+ PRs in). 0004 is the decision made on 2026-07-24.
