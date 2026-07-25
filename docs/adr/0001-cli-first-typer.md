# 0001 — CLI-first product surface with Typer

**Status:** accepted (backfilled 2026-07-24)

## Context
AURA needs a primary interface. It targets developers and CI, where a scriptable
command-line tool is the natural fit. A web UI exists but analysis requires
`solc`/`slither` on the host, which is a server/CLI concern, not a browser one.

## Decision
The CLI (Typer, entry point `aura = "aura.cli:app"`) is the primary product
surface. FastAPI and the React frontend are secondary consumers of the same
`core` pipeline.

## Consequences
- Core logic lives in `src/aura/core/` and stays interface-agnostic.
- CLI output shapes (e.g. `Findings: N | Score: S`) are a tested contract.
- The web UI cannot analyze in-browser; it needs a backend running the same tools
  (see the P5 deployment gap).
