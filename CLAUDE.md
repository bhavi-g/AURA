# CLAUDE.md — working agreement for AURA

AURA is a Solidity smart-contract security tool: **detect → explain → fix**.
Read `docs/PROJECT_BRIEF.md` for the full picture.

## Start every session by reading (in order)
1. The latest log in `docs/sessions/` — what happened last time
2. `docs/adr/README.md` — the decisions in force
3. The `docs/phases/phase-N.md` you're working from
4. `docs/NEVER_DO.md` — the guardrails

## While working
- Stay within the current phase. New ideas → backlog in `docs/PROJECT_BRIEF.md`,
  not into the current change.
- Preserve tested CLI/API output shapes unless you update the tests deliberately.
- Model discipline: **Sonnet by default**; reserve Opus/Fable for genuinely hard
  calls and note it in the session log.

## End every session by
1. Writing a `docs/sessions/YYYY-MM-DD-session.md` log (use `TEMPLATE.md`):
   WHAT I BUILT / WORKS / LEFT / BLOCKERS
2. Logging real decisions as new ADRs (`docs/adr/NNNN-*.md`)
3. Committing + pushing
4. Leaving a stub for the next session (WHAT I PLAN TO DO)

## Layout
- `src/aura/core/` — interface-agnostic pipeline (analyzers, scoring, reporting, llm, persistence)
- `src/aura/cli.py` — Typer CLI (primary surface) · `api/main.py` — FastAPI · `frontend/` — React+Vite+TS
- `contracts/`, `samples/` — Solidity fixtures · `reports/` — generated output (gitignored)

## Local prerequisites
Python 3.11+, Poetry, `solc` on PATH (via `solc-select`), Slither. Mythril optional.
