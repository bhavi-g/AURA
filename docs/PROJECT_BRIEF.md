# AURA — Project Brief

> **AURA (Automated Understanding & Remediation for Audits)** — a Solidity
> smart-contract security tool that takes developers from
> **vulnerability detection → plain-English explanation → PR-ready fix**.

_Last updated: 2026-08-02_

---

## Goal

Give Solidity developers a tool that doesn't just *report* vulnerabilities, but
explains why they matter and produces **review-ready code diffs** they can apply
during development and code review. AURA assists developers; it does **not**
replace professional audits or formal verification.

## Audience & positioning

Primary audience: **Solidity developers who install and adopt the tool** (OSS
dev tool, not a demo). Success looks like `pipx install aura`, a GitHub Action
in CI, and fixes trustworthy enough to open as PRs.

## Scope

**v1 does:**
- Detect vulnerabilities via static analyzers (Slither primary, Mythril optional)
- Score & aggregate findings into a single risk score
- Explain the top findings in plain English (static summary + optional LLM)
- Generate a `git apply`-able remediation diff for a specific rule
- Persist projects/runs/findings (SQLModel) and emit SARIF/JSON/Markdown reports
- Expose functionality via CLI (primary), FastAPI, and a React frontend

**v1 does NOT:**
- Replace audits, formal verification, or expert review
- Guarantee generated fixes are correct (they are best-effort — see roadmap P1)
- Do symbolic execution, fuzzing, or "neural scoring" (the old
  `docs/ARCHITECTURE.md` diagram is aspirational and does not reflect the code)
- Support multi-file / cross-contract fixes yet (single-file focus)

## Stack (as built)

- **Language/runtime:** Python 3.11+
- **Detection:** Slither (`slither_adapter`), Mythril (`mythril_adapter`, degrades
  to empty if `myth` not on PATH); requires `solc` on PATH
- **LLM:** OpenAI (`gpt-4o-mini`) via `openai`; falls back to a deterministic
  stub with no `OPENAI_API_KEY` (Claude backend planned — see ADR 0003)
- **Persistence:** SQLModel / SQLAlchemy (SQLite)
- **Interfaces:** Typer CLI (`aura ...`), FastAPI (`api/main.py`), React + Vite + TS (`frontend/`)
- **Infra:** Poetry, Docker, pre-commit, GitHub Actions CI (+ SARIF upload, F1 eval guard)

## Success criteria

1. `pipx install aura` works on a clean machine (P3)
2. Generated fixes are **verified** (apply → compile → finding gone) before being
   presented as PR-ready (P1 — the credibility bar)
3. A GitHub Action posts findings on PRs and uploads SARIF to Code Scanning (P4)
4. The static analyzer's F1 vs the golden baseline does not regress in CI
5. Docs are good enough that a new contributor can run the full pipeline locally

## Roadmap (see `docs/phases/`)

1. ✅ **Verified fixes (closed loop)** — trust the diffs (PR #26)
2. ✅ Claude LLM backend + provider abstraction (PRs #28, #29)
3. PyPI publish + install polish
4. GitHub Action (SARIF Code Scanning + PR comments)
5. Source-text analysis endpoint + deployed backend (unblocks web paste mode)

## Pending work (backlog, tracked so we don't forget)

### CLI bugs (surfaced by the P1 final review, 2026-07-24 — closed 2026-08-02)
- ✅ `explain.py::summarize_findings` crashed (`IndexError`) on a finding with
  an empty `description`. Fixed: `.splitlines()` on an empty string returns
  `[]`, not `[""]`; guarded the index.
- ✅ `_analyzer_available()` now also treats `pipx` on `PATH` as available,
  matching `SlitherAnalyzer.run()`'s real `pipx run --spec slither-analyzer`
  fallback (previously only checked `shutil.which("slither")`, so a
  pipx-only install always reported `UNVERIFIED`).
- ✅ `git apply` and `git init` (`src/aura/core/fix.py`) now pass
  `timeout=30`; both failure paths return a controlled `FAILED` verdict
  instead of hanging/crashing.
- ✅ `aura fix` now validates the target is a file up front and exits 1 with
  a clear message on a directory (or missing path) instead of crashing with
  an uncaught `IsADirectoryError`.
- ✅ `REGRESSED`'s `new_findings` is now included in both `--json` output and
  printed (rule + severity) in text output.
- ✅ `fix_cmd` now exits 1 on `FAILED`/`REGRESSED` verdicts (was always 0).

New backlog item surfaced while verifying the directory-target fix (not one
of the above, left open — doesn't affect the documented `aura ...` /
`python -m aura ...` entrypoints):
- `src/aura/cli.py`'s `if __name__ == "__main__": app()` guard sits mid-file
  (before the `fix` command is defined), so the undocumented
  `python -m aura.cli` invocation style silently never registers `fix` (or
  anything else defined after the guard). Trivial fix (move the guard to the
  true end of file) but out of scope for this pass.

### Deferred by design (P2, 2026-07-30 — not bugs, just out of scope)
- "Improve explain/fix prompts now that we control the provider" — held off
  until Claude's output on the *current* prompts can be compared against the
  old OpenAI output.
- Cosmetic: `openai` line in `pyproject.toml`'s dependency list uses a 4-space
  indent vs. 2-space everywhere else, including the `anthropic` line added
  next to it. No action needed, noted only.

### Known reality gaps (frontend/deploy)
- Live demo can't work: `render.yaml` deploys only the static frontend; backend
  URL is a placeholder — no backend is deployed (addressed in P5)
- Frontend "paste" mode sends a fake path and never uploads source (P5)
- `/audit` uses an in-memory `FAKE_DB` while the rest uses SQLModel (P5)
- `docs/ARCHITECTURE.md` is stale (describes a Mongo/JWT/task-queue/fuzzer/
  neural-scorer design that was never built) and should be rewritten to match
  the real system. (`.env.example` was brought current for the LLM section in
  P2 — no longer part of this gap.)
