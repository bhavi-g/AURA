# Phase 4 — GitHub Action (SARIF + PR comments) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a GitHub Action that runs AURA on pull requests, uploads SARIF to Code Scanning, upserts a findings comment, enforces a severity gate, and opens a PR containing only verified fixes.

**Architecture:** `aura analyze` gains a `--sarif` output flag so the installed PyPI package can emit SARIF without this repo's internal `tools/post_analyze.py`. A composite action at the repo root (`action.yml`) installs AURA + `solc` on the runner and drives the workflow. All non-trivial logic lives in stdlib-only Python under `action/scripts/` — split into pure functions (unit-tested directly) and subprocess wrappers that take an injectable runner (unit-tested by asserting the commands they build) — rather than inline `run: |` YAML.

**Tech Stack:** Python 3.11, Typer, pytest, GitHub Actions composite actions, `gh` CLI (preinstalled on runners), `github/codeql-action/upload-sarif@v3`, `solc-select`, Slither.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-08-06-phase4-github-action-design.md`. Read it before starting.
- **Branch:** `feat/phase4-github-action` (already created; the spec is already committed there).
- **Never change `aura analyze`'s existing stdout.** `docs/NEVER_DO.md` forbids silently changing behavior tests depend on. `--sarif` writes a file and prints nothing.
- **Never present an unverified diff as a fix.** Only `VERIFIED` verdicts may reach the fix PR.
- **`action/scripts/` is stdlib-only.** No `requests`, no third-party imports. GitHub API access goes through the `gh` CLI.
- **Python 3.11 syntax**, `from __future__ import annotations` at the top of every new module (matches the existing codebase).
- **Line length 100** (black + ruff + isort are all configured to 100).
- **Run tests from the venv, not Poetry.** `poetry install` is broken on this repo (see `PROJECT_BRIEF.md` "Tooling drift"). Use:
  ```bash
  source .venv/bin/activate
  PYTHONPATH="$(pwd)" pytest -q
  ```
- **Baseline:** 89 tests pass before this plan starts. That number only goes up.
- **Every task ends green:** `pytest -q`, `ruff check .`, `black --check .`, `isort --check-only .`.
- **Marker string** (exact, used in three files): `<!-- aura-pr-comment -->`
- **Fix branch pattern** (exact): `aura/auto-fixes/pr-<N>`

---

## File Structure

**Created:**
| File | Responsibility |
|---|---|
| `action.yml` | Composite action definition: inputs, outputs, step order |
| `action/scripts/__init__.py` | Makes `action.scripts` importable by tests |
| `action/scripts/findings.py` | Pure: severity ranking, path normalization, filtering, gate evaluation |
| `action/scripts/comment.py` | Pure: renders the PR comment Markdown |
| `action/scripts/ghcli.py` | Subprocess wrappers (`git`, `gh`) with an injectable runner |
| `action/scripts/fixes.py` | Fix planning (pure) + `aura fix` orchestration |
| `action/scripts/run_comment.py` | Entrypoint: build and upsert the PR comment |
| `action/scripts/run_gate.py` | Entrypoint: severity gate, exits 1 on violation |
| `action/scripts/run_fixes.py` | Entrypoint: run fixes, push branch, upsert fix PR |
| `.github/workflows/aura-pr-scan.yml` | Dogfood workflow (`uses: ./`) |
| `tests/test_action_findings.py` | Tests for `findings.py` |
| `tests/test_action_comment.py` | Tests for `comment.py` |
| `tests/test_action_ghcli.py` | Tests for `ghcli.py` |
| `tests/test_action_fixes.py` | Tests for `fixes.py` |
| `docs/adr/0006-composite-github-action.md` | ADR |
| `docs/adr/0007-verified-only-fix-prs.md` | ADR |
| `docs/sessions/2026-08-06-session.md` | Session log |

**Modified:**
| File | Change |
|---|---|
| `src/aura/cli.py` | Add `--sarif` to `analyze` (~line 78-103) |
| `pyproject.toml` | ruff `per-file-ignores` for T201, pytest `pythonpath`, isort `src_paths` |
| `MANIFEST.in` | `prune action` + `exclude action.yml` so neither ships in the sdist |
| `README.md` | "GitHub Action" section |
| `docs/adr/README.md` | Index rows for ADRs 0006/0007 |
| `docs/phases/phase-4.md` | Status → shipped |
| `docs/PROJECT_BRIEF.md` | Roadmap item 4 → ✅ |
| `tests/test_cli.py` | `--sarif` tests |

**Untouched (deliberately):** `tools/post_analyze.py`, `.github/workflows/upload-sarif.yml`, `.github/workflows/ci.yml`, `src/aura/core/reporting/sarif_report.py`.

---

### Task 1: `aura analyze --sarif`

Makes SARIF a first-class output of the *installed* CLI. Everything downstream depends on this.

**Files:**
- Modify: `src/aura/cli.py` (imports near line 10-19; `analyze` at lines 78-103)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `write_sarif(findings, out_path)` from `src/aura/core/reporting/sarif_report.py` (already exists, unchanged).
- Produces: `aura analyze <target> --sarif <path>` writes a SARIF 2.1.0 file. Tasks 7's `action.yml` calls this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_analyze_sarif_writes_a_sarif_file(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    out = temp_cwd / "out.sarif"
    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(sample_contract), "--sarif", str(out)])

    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["tool"]["driver"]["name"] == "AURA"
    rule_ids = {r["ruleId"] for r in data["runs"][0]["results"]}
    assert "reentrancy-eth" in rule_ids


def test_analyze_sarif_creates_missing_parent_directories(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    out = temp_cwd / "nested" / "dir" / "out.sarif"
    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(sample_contract), "--sarif", str(out)])

    assert result.exit_code == 0
    assert out.is_file()


def test_analyze_sarif_flag_does_not_change_stdout(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    """docs/NEVER_DO.md: --sarif is additive; it must not alter tested output shapes."""
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    runner = CliRunner()
    plain = runner.invoke(app, ["analyze", str(sample_contract)])
    with_sarif = runner.invoke(
        app, ["analyze", str(sample_contract), "--sarif", str(temp_cwd / "a.sarif")]
    )
    assert plain.stdout == with_sarif.stdout

    plain_json = runner.invoke(app, ["analyze", str(sample_contract), "--json"])
    json_with_sarif = runner.invoke(
        app,
        ["analyze", str(sample_contract), "--json", "--sarif", str(temp_cwd / "b.sarif")],
    )
    assert json.loads(json_with_sarif.stdout).keys() == json.loads(plain_json.stdout).keys()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
source .venv/bin/activate
PYTHONPATH="$(pwd)" pytest tests/test_cli.py -k sarif -q
```

Expected: FAIL — `No such option: --sarif`.

- [ ] **Step 3: Add the import**

In `src/aura/cli.py`, add to the existing import block (after `from aura.core.pipeline import run_analysis`):

```python
from aura.core.reporting.sarif_report import write_sarif
```

isort will want it ordered alphabetically within the `aura.core` group — run `isort .` in step 6 rather than hand-placing it.

- [ ] **Step 4: Add the `--sarif` option to `analyze`**

In `src/aura/cli.py`, add a parameter to `analyze` after `json_out` (keep it last so positional/optional ordering is unchanged):

```python
    sarif_out: str = typer.Option(
        "",
        "--sarif",
        help="Also write a SARIF 2.1.0 report to this path (for GitHub Code Scanning)",
    ),
```

Then, inside the body, immediately after `res = run_analysis(target, project_name=project)`:

```python
    if sarif_out:
        write_sarif(res.get("findings", []), sarif_out)
```

Place it **before** the `if json_out:` block so the SARIF is written regardless of output mode, and print nothing — stdout stays byte-identical.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_cli.py -k sarif -q
```

Expected: 3 passed.

- [ ] **Step 6: Full suite + lint**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
```

Expected: 92 passed (89 baseline + 3), lint clean.

- [ ] **Step 7: Commit**

```bash
git add src/aura/cli.py tests/test_cli.py
git commit -m "feat(cli): add --sarif output flag to aura analyze

Makes SARIF a first-class output of the installed package rather than
something only tools/post_analyze.py can produce, so the GitHub Action
can get SARIF in any consumer repo. Additive and default-off: stdout is
unchanged in both text and --json modes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `action/scripts/findings.py` — pure findings logic

First file under `action/`, so it also carries the tooling config that makes `action/` lintable and importable.

**Files:**
- Create: `action/scripts/__init__.py`, `action/scripts/findings.py`
- Modify: `pyproject.toml`
- Test: `tests/test_action_findings.py`

**Interfaces:**
- Produces (used by Tasks 3, 5, 6):
  - `SEVERITY_ORDER: dict[str, int]` — `INFO=0, LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4`
  - `severity_rank(severity: str) -> int`
  - `normalize_path(path: str) -> str`
  - `finding_files(finding: dict) -> list[str]`
  - `filter_by_files(findings: list[dict], changed_files) -> list[dict]`
  - `severity_counts(findings: list[dict]) -> dict[str, int]`
  - `gate_violations(findings: list[dict], threshold: str) -> list[dict]` (raises `ValueError` on an unknown threshold)

- [ ] **Step 1: Add the tooling config**

In `pyproject.toml`, add a pytest section (none exists today) — put it just above `[tool.black]`:

```toml
[tool.pytest.ini_options]
# Repo root on sys.path so tests can `import action.scripts.*`. The `aura`
# package itself comes from the editable install, not from here.
pythonpath = ["."]
```

Change the isort `src_paths` line to include `action`:

```toml
src_paths = ["src", "api", "cli", "tests", "action"]
```

And replace the commented-out per-file-ignores block at the end of the ruff section with a real one:

```toml
[tool.ruff.lint.per-file-ignores]
# These are CI glue scripts whose entire job is writing to the Actions log.
"action/scripts/*.py" = ["T201"]
```

- [ ] **Step 2: Create the package marker**

`action/scripts/__init__.py`:

```python
"""Glue scripts for the AURA GitHub Action.

Deliberately not part of the installed `aura-audit` distribution — this is
CI orchestration, not library code. Stdlib only.
"""
```

Note: there is **no** `action/__init__.py`. `action` resolves as a namespace package, which is enough for `import action.scripts.findings` and keeps `action/` from looking like a shippable package.

- [ ] **Step 3: Write the failing tests**

`tests/test_action_findings.py`:

```python
import pytest

from action.scripts.findings import (
    filter_by_files,
    finding_files,
    gate_violations,
    normalize_path,
    severity_counts,
    severity_rank,
)


def _finding(rule="reentrancy-eth", severity="HIGH", files=("contracts/A.sol",), line=11):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": rule,
        "locations": [{"file": f, "line": line} for f in files],
    }


def test_severity_rank_orders_severities():
    assert severity_rank("CRITICAL") > severity_rank("HIGH")
    assert severity_rank("HIGH") > severity_rank("MEDIUM")
    assert severity_rank("MEDIUM") > severity_rank("LOW")
    assert severity_rank("LOW") > severity_rank("INFO")


def test_severity_rank_is_case_insensitive_and_defaults_unknown_to_zero():
    assert severity_rank("high") == severity_rank("HIGH")
    assert severity_rank("nonsense") == 0
    assert severity_rank("") == 0
    assert severity_rank(None) == 0


def test_normalize_path_strips_prefixes_and_normalizes_separators():
    assert normalize_path("./contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("/contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("contracts\\A.sol") == "contracts/A.sol"
    assert normalize_path("contracts/../contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("") == ""
    assert normalize_path(None) == ""


def test_finding_files_dedupes_and_normalizes():
    f = _finding(files=("./contracts/A.sol", "contracts/A.sol", "contracts/B.sol"))
    assert finding_files(f) == ["contracts/A.sol", "contracts/B.sol"]


def test_finding_files_handles_missing_locations():
    assert finding_files({"rule_id": "x"}) == []
    assert finding_files({"rule_id": "x", "locations": []}) == []


def test_filter_by_files_keeps_only_findings_touching_changed_files():
    a = _finding(rule="a", files=("contracts/A.sol",))
    b = _finding(rule="b", files=("contracts/B.sol",))
    kept = filter_by_files([a, b], ["./contracts/A.sol"])
    assert [f["rule_id"] for f in kept] == ["a"]


def test_filter_by_files_returns_empty_when_nothing_changed():
    assert filter_by_files([_finding()], []) == []


def test_severity_counts_counts_known_severities_only():
    findings = [
        _finding(severity="HIGH"),
        _finding(severity="HIGH"),
        _finding(severity="LOW"),
        _finding(severity="bogus"),
    ]
    counts = severity_counts(findings)
    assert counts["HIGH"] == 2
    assert counts["LOW"] == 1
    assert counts["CRITICAL"] == 0


def test_gate_violations_includes_findings_at_the_threshold_itself():
    """The boundary: `fail-on: high` must fail on a HIGH, not only on CRITICAL."""
    findings = [_finding(severity="HIGH"), _finding(severity="MEDIUM")]
    violations = gate_violations(findings, "high")
    assert len(violations) == 1
    assert violations[0]["severity"] == "HIGH"


def test_gate_violations_includes_severities_above_the_threshold():
    findings = [_finding(severity="CRITICAL")]
    assert len(gate_violations(findings, "high")) == 1


def test_gate_violations_disabled_by_none_and_empty():
    findings = [_finding(severity="CRITICAL")]
    assert gate_violations(findings, "none") == []
    assert gate_violations(findings, "") == []


def test_gate_violations_rejects_an_unknown_threshold():
    with pytest.raises(ValueError):
        gate_violations([], "extremely-bad")
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_findings.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'action'`.

- [ ] **Step 5: Implement `action/scripts/findings.py`**

```python
"""Pure helpers for interpreting AURA findings inside the GitHub Action.

No subprocess, no network, no filesystem: every function here is a plain
transformation over the JSON that `aura analyze --json` emits, so it can be
unit-tested without an injected runner.
"""

from __future__ import annotations

import posixpath

SEVERITY_ORDER: dict[str, int] = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

GATE_DISABLED = "none"


def severity_rank(severity: str | None) -> int:
    """Rank a severity for comparison. Unknown/missing severities rank lowest."""
    return SEVERITY_ORDER.get(str(severity or "").strip().upper(), 0)


def normalize_path(path: str | None) -> str:
    """Reduce a path to repo-relative POSIX form for comparison.

    Slither reports `filename_relative`, git reports repo-relative POSIX;
    this collapses the remaining differences (`./` prefixes, leading
    slashes, Windows separators, `..` segments) so the two can be compared.
    """
    if not path:
        return ""
    candidate = str(path).replace("\\", "/").strip()
    while candidate.startswith("./"):
        candidate = candidate[2:]
    candidate = candidate.lstrip("/")
    if not candidate:
        return ""
    return posixpath.normpath(candidate)


def finding_files(finding: dict) -> list[str]:
    """Normalized, de-duplicated file paths a finding points at, in order."""
    files: list[str] = []
    for location in finding.get("locations") or []:
        path = normalize_path(location.get("file", ""))
        if path and path not in files:
            files.append(path)
    return files


def filter_by_files(findings: list[dict], changed_files) -> list[dict]:
    """Findings that touch at least one of `changed_files`."""
    wanted = {normalize_path(path) for path in changed_files}
    wanted.discard("")
    if not wanted:
        return []
    return [f for f in findings if any(path in wanted for path in finding_files(f))]


def severity_counts(findings: list[dict]) -> dict[str, int]:
    """Count findings per known severity. Unrecognized severities are ignored."""
    counts = dict.fromkeys(SEVERITY_ORDER, 0)
    for finding in findings:
        severity = str(finding.get("severity") or "").strip().upper()
        if severity in counts:
            counts[severity] += 1
    return counts


def gate_violations(findings: list[dict], threshold: str) -> list[dict]:
    """Findings at or above `threshold`. Empty for `none`/empty threshold.

    Raises ValueError on an unrecognized threshold rather than silently
    letting a typo'd `fail-on` disable the gate.
    """
    normalized = str(threshold or "").strip().lower()
    if normalized in ("", GATE_DISABLED):
        return []
    minimum = SEVERITY_ORDER.get(normalized.upper())
    if minimum is None:
        raise ValueError(
            f"unknown fail-on threshold: {threshold!r} "
            f"(expected one of: none, {', '.join(k.lower() for k in SEVERITY_ORDER)})"
        )
    return [f for f in findings if severity_rank(f.get("severity")) >= minimum]
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_findings.py -q
```

Expected: 12 passed.

- [ ] **Step 7: Full suite + lint, then commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
git add action/ tests/test_action_findings.py pyproject.toml
git commit -m "feat(action): add pure findings helpers for the GitHub Action

Severity ranking, path normalization, changed-file filtering and the
fail-on gate, as plain functions with no I/O so they are directly
unit-testable. Also wires action/ into pytest's pythonpath, isort's
src_paths, and a ruff T201 exemption (these scripts log to stdout).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `action/scripts/comment.py` — PR comment rendering

**Files:**
- Create: `action/scripts/comment.py`
- Test: `tests/test_action_comment.py`

**Interfaces:**
- Consumes: `severity_counts`, `severity_rank`, `finding_files` from `action.scripts.findings`.
- Produces (used by Tasks 5, 6):
  - `MARKER: str` = `"<!-- aura-pr-comment -->"`
  - `DISCLAIMER: str`
  - `render_comment(*, all_findings, changed_findings, score, changed_files_ok, gate_threshold, violations, fix_pr_url=None, fix_skip_reason=None, max_rows=10) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_action_comment.py`:

```python
from action.scripts.comment import DISCLAIMER, MARKER, render_comment


def _finding(rule="reentrancy-eth", severity="HIGH", title="Reentrancy", file="contracts/A.sol"):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": title,
        "locations": [{"file": file, "line": 11}],
    }


def _render(**overrides):
    kwargs = {
        "all_findings": [_finding()],
        "changed_findings": [_finding()],
        "score": 12.5,
        "changed_files_ok": True,
        "gate_threshold": "high",
        "violations": [],
    }
    kwargs.update(overrides)
    return render_comment(**kwargs)


def test_comment_starts_with_the_marker_so_it_can_be_found_for_upsert():
    assert _render().startswith(MARKER)


def test_comment_includes_totals_and_score():
    body = _render(all_findings=[_finding(), _finding(rule="tx-origin")], score=31.0)
    assert "2 finding" in body
    assert "31.0" in body


def test_comment_lists_changed_file_findings_in_a_table():
    body = _render()
    assert "| Severity | Rule | Location | Title |" in body
    assert "`reentrancy-eth`" in body
    assert "`contracts/A.sol:11`" in body


def test_comment_orders_findings_by_severity_descending():
    low = _finding(rule="solc-version", severity="LOW")
    critical = _finding(rule="arbitrary-send-eth", severity="CRITICAL")
    body = _render(all_findings=[low, critical], changed_findings=[low, critical])
    assert body.index("arbitrary-send-eth") < body.index("solc-version")


def test_comment_escapes_pipes_in_titles_so_the_table_survives():
    body = _render(changed_findings=[_finding(title="a | b")])
    assert "a \\| b" in body


def test_comment_truncates_long_finding_lists():
    many = [_finding(rule=f"rule-{i}") for i in range(15)]
    body = _render(all_findings=many, changed_findings=many, max_rows=10)
    assert "and 5 more" in body


def test_comment_celebrates_a_clean_changed_file_set():
    body = _render(changed_findings=[])
    assert "No findings in the files this PR changes" in body


def test_comment_notes_when_changed_files_could_not_be_determined():
    body = _render(changed_files_ok=False)
    assert "Could not determine" in body


def test_comment_reports_a_passing_gate():
    body = _render(violations=[])
    assert "Severity gate" in body and "passed" in body


def test_comment_reports_a_failing_gate_with_a_count():
    body = _render(violations=[_finding(), _finding()])
    assert "failed" in body and "2 finding" in body


def test_comment_reports_a_disabled_gate():
    body = _render(gate_threshold="none")
    assert "disabled" in body


def test_comment_links_the_fix_pr_when_one_was_opened():
    body = _render(fix_pr_url="https://github.com/o/r/pull/9")
    assert "https://github.com/o/r/pull/9" in body


def test_comment_states_why_fixes_were_skipped():
    body = _render(fix_skip_reason="no LLM API key configured")
    assert "no LLM API key configured" in body


def test_comment_always_carries_the_not_an_audit_disclaimer():
    """docs/NEVER_DO.md: never present AURA output as an audit."""
    assert DISCLAIMER in _render()
    assert DISCLAIMER in _render(changed_findings=[], violations=[])
```

- [ ] **Step 2: Run to verify they fail**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_comment.py -q
```

Expected: `ModuleNotFoundError: No module named 'action.scripts.comment'`.

- [ ] **Step 3: Implement `action/scripts/comment.py`**

```python
"""Renders the AURA pull-request comment.

Pure string building — no I/O — so every branch is directly testable.
"""

from __future__ import annotations

from action.scripts.findings import GATE_DISABLED, finding_files, severity_counts, severity_rank

MARKER = "<!-- aura-pr-comment -->"

DISCLAIMER = (
    "_AURA assists code review — it does not replace a professional audit or "
    "formal verification. Treat these findings as leads, not verdicts._"
)

_DISPLAY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


def _findings_table(findings: list[dict], max_rows: int) -> list[str]:
    ordered = sorted(findings, key=lambda f: -severity_rank(f.get("severity")))
    rows = ["| Severity | Rule | Location | Title |", "|---|---|---|---|"]
    for finding in ordered[:max_rows]:
        files = finding_files(finding)
        location = files[0] if files else "?"
        line = ((finding.get("locations") or [{}])[0]).get("line", "")
        rule = str(finding.get("rule_id") or "unknown")
        # A pipe in a title would otherwise split the Markdown table cell.
        title = str(finding.get("title") or "").replace("|", "\\|")
        severity = str(finding.get("severity") or "").upper()
        rows.append(f"| {severity} | `{rule}` | `{location}:{line}` | {title} |")
    if len(ordered) > max_rows:
        rows.extend(["", f"_…and {len(ordered) - max_rows} more._"])
    return rows


def render_comment(
    *,
    all_findings: list[dict],
    changed_findings: list[dict],
    score,
    changed_files_ok: bool,
    gate_threshold: str,
    violations: list[dict],
    fix_pr_url: str | None = None,
    fix_skip_reason: str | None = None,
    max_rows: int = 10,
) -> str:
    counts = severity_counts(all_findings)
    lines = [
        MARKER,
        "## AURA — Solidity security scan",
        "",
        f"**{len(all_findings)} finding(s)** across the scanned path · risk score **{score}**",
        "",
    ]

    severity_rows = [f"| {name} | {counts[name]} |" for name in _DISPLAY_ORDER if counts[name]]
    if severity_rows:
        lines.extend(["| Severity | Count |", "|---|---|", *severity_rows, ""])

    if changed_files_ok:
        lines.append(f"### In this PR's changed files ({len(changed_findings)})")
        lines.append("")
    else:
        lines.append(f"### All findings ({len(changed_findings)})")
        lines.append("")
        lines.append(
            "> Could not determine this PR's changed files, so every finding is listed. "
            "Check that the workflow checks out with `fetch-depth: 0`."
        )
        lines.append("")

    if changed_findings:
        lines.extend(_findings_table(changed_findings, max_rows))
    else:
        lines.append("No findings in the files this PR changes. ✅")
    lines.append("")

    threshold = str(gate_threshold or "").strip().lower()
    if threshold in ("", GATE_DISABLED):
        lines.append("**Severity gate:** disabled (`fail-on: none`).")
    elif violations:
        lines.append(
            f"**Severity gate:** ❌ failed — {len(violations)} finding(s) "
            f"at or above `{threshold}`."
        )
    else:
        lines.append(f"**Severity gate:** ✅ passed — nothing at or above `{threshold}`.")
    lines.append("")

    if fix_pr_url:
        lines.append(f"**Verified fixes:** opened → {fix_pr_url}")
        lines.append("")
    elif fix_skip_reason:
        lines.append(f"**Verified fixes:** skipped — {fix_skip_reason}")
        lines.append("")

    lines.append(DISCLAIMER)
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_comment.py -q
```

Expected: 14 passed.

- [ ] **Step 5: Full suite + lint, then commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
git add action/scripts/comment.py tests/test_action_comment.py
git commit -m "feat(action): render the AURA PR comment

Pure Markdown rendering with the hidden upsert marker, a severity
breakdown, a changed-files findings table, gate status, fix-PR status,
and the mandatory not-an-audit disclaimer.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `action/scripts/ghcli.py` — git/gh wrappers

Every function takes an injectable `runner`, so tests assert on the *commands built* without any network or repo state.

**Files:**
- Create: `action/scripts/ghcli.py`
- Test: `tests/test_action_ghcli.py`

**Interfaces:**
- Consumes: `MARKER` from `action.scripts.comment`.
- Produces (used by Tasks 5, 6):
  - `class CommandError(RuntimeError)`
  - `run(cmd: list[str], *, runner=None, check=True, timeout=120) -> str`
  - `changed_files(base_ref: str, *, runner=None) -> tuple[list[str], bool]`
  - `find_marker_comment_id(repo, pr_number, marker=MARKER, *, runner=None) -> int | None`
  - `upsert_pr_comment(repo, pr_number, body, *, body_path, marker=MARKER, runner=None) -> str` (returns `"created"` or `"updated"`)

- [ ] **Step 1: Write the failing tests**

`tests/test_action_ghcli.py`:

```python
import subprocess

import pytest

from action.scripts.ghcli import (
    CommandError,
    changed_files,
    find_marker_comment_id,
    run,
    upsert_pr_comment,
)


class FakeRunner:
    """Records the commands it is asked to run and replays canned results."""

    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if self._results:
            stdout, returncode = self._results.pop(0)
        else:
            stdout, returncode = "", 0
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="boom")

    @property
    def commands(self):
        return [" ".join(c) for c in self.calls]


def test_run_returns_stdout_on_success():
    assert run(["echo", "hi"], runner=FakeRunner([("hi\n", 0)])) == "hi\n"


def test_run_raises_on_failure_when_checking():
    with pytest.raises(CommandError):
        run(["false"], runner=FakeRunner([("", 1)]))


def test_run_returns_output_on_failure_when_not_checking():
    assert run(["false"], runner=FakeRunner([("out", 1)]), check=False) == "out"


def test_changed_files_parses_the_diff_against_the_base_ref():
    fake = FakeRunner([("contracts/A.sol\ncontracts/B.sol\n", 0)])
    files, ok = changed_files("main", runner=fake)
    assert ok is True
    assert files == ["contracts/A.sol", "contracts/B.sol"]
    assert "git diff --name-only origin/main...HEAD" in fake.commands[0]


def test_changed_files_reports_failure_instead_of_pretending_nothing_changed():
    """A shallow checkout must degrade visibly, not silently look clean."""
    files, ok = changed_files("main", runner=FakeRunner([("", 1)]))
    assert files == []
    assert ok is False


def test_find_marker_comment_id_returns_the_first_match():
    fake = FakeRunner([("123\n456\n", 0)])
    assert find_marker_comment_id("o/r", 7, runner=fake) == 123
    assert "gh api" in fake.commands[0]
    assert "/repos/o/r/issues/7/comments" in fake.commands[0]


def test_find_marker_comment_id_returns_none_when_absent():
    assert find_marker_comment_id("o/r", 7, runner=FakeRunner([("", 0)])) is None


def test_find_marker_comment_id_returns_none_when_the_api_call_fails():
    assert find_marker_comment_id("o/r", 7, runner=FakeRunner([("", 1)])) is None


def test_upsert_creates_a_comment_when_none_exists(tmp_path):
    fake = FakeRunner([("", 0), ("", 0)])
    body_path = tmp_path / "c.md"
    assert upsert_pr_comment("o/r", 7, "hello", body_path=body_path, runner=fake) == "created"
    assert body_path.read_text() == "hello"
    assert "--method POST" in fake.commands[1]
    assert f"body=@{body_path}" in fake.commands[1]


def test_upsert_edits_the_existing_comment_instead_of_adding_another(tmp_path):
    fake = FakeRunner([("99\n", 0), ("", 0)])
    body_path = tmp_path / "c.md"
    assert upsert_pr_comment("o/r", 7, "hello", body_path=body_path, runner=fake) == "updated"
    assert "--method PATCH" in fake.commands[1]
    assert "/repos/o/r/issues/comments/99" in fake.commands[1]
```

- [ ] **Step 2: Run to verify they fail**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_ghcli.py -q
```

Expected: `ModuleNotFoundError: No module named 'action.scripts.ghcli'`.

- [ ] **Step 3: Implement `action/scripts/ghcli.py`**

```python
"""Thin `git` / `gh` wrappers for the AURA GitHub Action.

Every entry point accepts an injectable `runner` (defaulting to
`subprocess.run`) so tests can assert on the commands that get built
without touching the network or a real repository.

GitHub API access goes through the `gh` CLI, which is preinstalled on
GitHub-hosted runners — that keeps these scripts stdlib-only.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from action.scripts.comment import MARKER


class CommandError(RuntimeError):
    """A subprocess exited non-zero while `check=True`."""


def run(cmd: list[str], *, runner=None, check: bool = True, timeout: int = 120) -> str:
    runner = runner or subprocess.run
    proc = runner(cmd, capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise CommandError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{(proc.stderr or '').strip()}"
        )
    return proc.stdout or ""


def changed_files(base_ref: str, *, runner=None) -> tuple[list[str], bool]:
    """Files this PR changes, and whether the diff could be computed at all.

    The bool matters: an empty list because the PR is clean and an empty
    list because the diff blew up mean opposite things to a reviewer, so
    the caller is forced to distinguish them.
    """
    try:
        out = run(
            ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"],
            runner=runner,
        )
    except CommandError:
        return [], False
    return [line.strip() for line in out.splitlines() if line.strip()], True


def find_marker_comment_id(
    repo: str, pr_number: int | str, marker: str = MARKER, *, runner=None
) -> int | None:
    """The id of AURA's existing comment on this PR, if it has one.

    Filtering happens server-side via --jq so bodies never have to be
    parsed locally, which also keeps this correct across paginated results.
    """
    query = f'.[] | select(.body != null and (.body | contains("{marker}"))) | .id'
    try:
        out = run(
            ["gh", "api", "--paginate", "--jq", query, f"/repos/{repo}/issues/{pr_number}/comments"],
            runner=runner,
        )
    except CommandError:
        return None
    ids = [line.strip() for line in out.splitlines() if line.strip()]
    return int(ids[0]) if ids else None


def upsert_pr_comment(
    repo: str,
    pr_number: int | str,
    body: str,
    *,
    body_path,
    marker: str = MARKER,
    runner=None,
) -> str:
    """Edit AURA's comment if it exists, otherwise post one. Returns the action taken."""
    path = Path(body_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")

    comment_id = find_marker_comment_id(repo, pr_number, marker, runner=runner)
    if comment_id is None:
        run(
            [
                "gh", "api", "--method", "POST",
                "-F", f"body=@{path}",
                f"/repos/{repo}/issues/{pr_number}/comments",
            ],
            runner=runner,
        )
        return "created"

    run(
        [
            "gh", "api", "--method", "PATCH",
            "-F", f"body=@{path}",
            f"/repos/{repo}/issues/comments/{comment_id}",
        ],
        runner=runner,
    )
    return "updated"
```

Note: black will reformat the multi-item lists above onto one-per-line — let it.

- [ ] **Step 4: Run to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_ghcli.py -q
```

Expected: 10 passed.

- [ ] **Step 5: Full suite + lint, then commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
git add action/scripts/ghcli.py tests/test_action_ghcli.py
git commit -m "feat(action): add git/gh wrappers with an injectable runner

Changed-file diffing and marker-based PR comment upsert, built so the
commands themselves are unit-testable. Comment lookup filters server-side
via gh's --jq so it stays correct across paginated results.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `run_comment.py` + `run_gate.py` entrypoints

**Files:**
- Create: `action/scripts/run_comment.py`, `action/scripts/run_gate.py`
- Test: append to `tests/test_action_comment.py`

**Interfaces:**
- Consumes: everything from Tasks 2-4.
- Produces (called by `action.yml` in Task 7):
  - `python -m action.scripts.run_comment` — reads env, upserts the comment, always exits 0
  - `python -m action.scripts.run_gate` — reads env, exits 1 on violations
  - `load_findings(path) -> tuple[list[dict], float]` in `run_gate.py`, reused by `run_comment.py`

**Environment contract** (set by `action.yml`):

| Var | Meaning |
|---|---|
| `AURA_FINDINGS_JSON` | Path to `aura analyze --json` output |
| `AURA_CHANGED_FILES` | Path to the newline-delimited changed-file list |
| `AURA_CHANGED_FILES_OK` | `"true"`/`"false"` — whether the diff succeeded |
| `AURA_FAIL_ON` | Gate threshold |
| `AURA_REPO` | `owner/repo` |
| `AURA_PR_NUMBER` | PR number (empty when not a PR) |
| `AURA_FIX_PR_URL` | Fix PR URL, or empty |
| `AURA_FIX_SKIP_REASON` | Skip reason, or empty |
| `AURA_COMMENT_BODY_PATH` | Where to stage the comment body |

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_action_comment.py`:

```python
import json

from action.scripts.run_gate import load_findings, read_changed_files


def test_load_findings_reads_the_analyze_json_payload(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"findings": [{"rule_id": "a"}], "score": 4.2}))
    findings, score = load_findings(path)
    assert [f["rule_id"] for f in findings] == ["a"]
    assert score == 4.2


def test_load_findings_tolerates_a_missing_file(tmp_path):
    findings, score = load_findings(tmp_path / "nope.json")
    assert findings == []
    assert score == 0


def test_load_findings_tolerates_malformed_json(tmp_path):
    path = tmp_path / "f.json"
    path.write_text("not json{")
    assert load_findings(path) == ([], 0)


def test_read_changed_files_strips_blank_lines(tmp_path):
    path = tmp_path / "changed.txt"
    path.write_text("contracts/A.sol\n\ncontracts/B.sol\n")
    assert read_changed_files(path) == ["contracts/A.sol", "contracts/B.sol"]


def test_read_changed_files_returns_empty_for_a_missing_file(tmp_path):
    assert read_changed_files(tmp_path / "nope.txt") == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_comment.py -q
```

Expected: `ModuleNotFoundError: No module named 'action.scripts.run_gate'`.

- [ ] **Step 3: Implement `action/scripts/run_gate.py`**

```python
"""Severity gate entrypoint: fails the check when findings breach `fail-on`.

Runs last in the action so that a red check never suppresses the SARIF
upload, the PR comment, or the fix PR.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from action.scripts.findings import gate_violations


def load_findings(path) -> tuple[list[dict], float]:
    """Findings and score from `aura analyze --json`, degrading to empty."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], 0
    return payload.get("findings") or [], payload.get("score") or 0


def read_changed_files(path) -> list[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def main() -> int:
    findings, _ = load_findings(os.environ.get("AURA_FINDINGS_JSON", ""))
    threshold = os.environ.get("AURA_FAIL_ON", "high")

    try:
        violations = gate_violations(findings, threshold)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1

    if not violations:
        print(f"AURA severity gate passed (fail-on: {threshold}).")
        return 0

    print(f"::error::AURA severity gate failed: {len(violations)} finding(s) at or above "
          f"'{threshold}'.")
    for finding in violations:
        location = (finding.get("locations") or [{}])[0]
        print(
            f"  [{finding.get('severity')}] {finding.get('rule_id')} "
            f"— {location.get('file')}:{location.get('line')}"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `action/scripts/run_comment.py`**

```python
"""PR comment entrypoint: builds the body and upserts it onto the PR.

Always exits 0. A comment that could not be posted (fork token, API
hiccup) is a degraded surface, not a reason to fail someone's build —
the SARIF upload and the gate still carry the signal.
"""

from __future__ import annotations

import os
import sys

from action.scripts.comment import render_comment
from action.scripts.findings import filter_by_files, gate_violations
from action.scripts.ghcli import CommandError, upsert_pr_comment
from action.scripts.run_gate import load_findings, read_changed_files


def main() -> int:
    pr_number = os.environ.get("AURA_PR_NUMBER", "").strip()
    if not pr_number:
        print("Not a pull request — skipping the AURA PR comment.")
        return 0

    findings, score = load_findings(os.environ.get("AURA_FINDINGS_JSON", ""))
    changed = read_changed_files(os.environ.get("AURA_CHANGED_FILES", ""))
    changed_ok = os.environ.get("AURA_CHANGED_FILES_OK", "true").lower() == "true"
    threshold = os.environ.get("AURA_FAIL_ON", "high")

    # When the diff is unavailable we show everything rather than an
    # empty list that would read as "this PR is clean".
    changed_findings = filter_by_files(findings, changed) if changed_ok else list(findings)

    try:
        violations = gate_violations(findings, threshold)
    except ValueError:
        violations = []

    body = render_comment(
        all_findings=findings,
        changed_findings=changed_findings,
        score=score,
        changed_files_ok=changed_ok,
        gate_threshold=threshold,
        violations=violations,
        fix_pr_url=os.environ.get("AURA_FIX_PR_URL", "").strip() or None,
        fix_skip_reason=os.environ.get("AURA_FIX_SKIP_REASON", "").strip() or None,
    )

    try:
        outcome = upsert_pr_comment(
            os.environ["AURA_REPO"],
            pr_number,
            body,
            body_path=os.environ.get("AURA_COMMENT_BODY_PATH", "aura-comment.md"),
        )
    except (CommandError, KeyError) as exc:
        print(f"::warning::Could not post the AURA PR comment: {exc}")
        return 0

    print(f"AURA PR comment {outcome}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_comment.py -q
```

Expected: 19 passed (14 from Task 3 + 5 new).

- [ ] **Step 6: Smoke-test the gate entrypoint by hand**

```bash
cat > /tmp/aura-gate-smoke.json <<'JSON'
{"findings": [{"rule_id": "reentrancy-eth", "severity": "HIGH",
 "locations": [{"file": "contracts/A.sol", "line": 11}]}], "score": 12.0}
JSON
AURA_FINDINGS_JSON=/tmp/aura-gate-smoke.json AURA_FAIL_ON=high \
  python -m action.scripts.run_gate; echo "exit=$?"
AURA_FINDINGS_JSON=/tmp/aura-gate-smoke.json AURA_FAIL_ON=critical \
  python -m action.scripts.run_gate; echo "exit=$?"
AURA_FINDINGS_JSON=/tmp/aura-gate-smoke.json AURA_FAIL_ON=none \
  python -m action.scripts.run_gate; echo "exit=$?"
```

Expected: `exit=1`, then `exit=0`, then `exit=0`.

- [ ] **Step 7: Full suite + lint, then commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
git add action/scripts/run_comment.py action/scripts/run_gate.py tests/test_action_comment.py
git commit -m "feat(action): add PR comment and severity gate entrypoints

The gate exits 1 on violations; the comment step always exits 0 so a
posting failure degrades the surface rather than failing the build.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Auto-opened verified-fix PRs

The credibility-critical task. `aura fix --write` only writes on `VERIFIED` (existing behavior in `cli.py::fix_cmd`), and this task must not weaken that.

**Files:**
- Create: `action/scripts/fixes.py`, `action/scripts/run_fixes.py`
- Test: `tests/test_action_fixes.py`

**Interfaces:**
- Consumes: `finding_files`, `normalize_path` from `findings`; `run`, `CommandError` from `ghcli`; `load_findings`, `read_changed_files` from `run_gate`.
- Produces (called by `action.yml`):
  - `fix_skip_reason(*, open_fix_prs, has_llm_key, is_fork, head_ref) -> str | None`
  - `plan_fix_targets(findings, changed_files) -> list[tuple[str, str]]`
  - `run_fix(path, rule, *, runner=None, timeout=900) -> dict`
  - `verified(results) -> list[dict]`
  - `render_fix_pr_body(results, source_pr) -> str`
  - `python -m action.scripts.run_fixes` — writes `fix_pr_url` / `fix_skip_reason` to `$GITHUB_OUTPUT`

- [ ] **Step 1: Write the failing tests**

`tests/test_action_fixes.py`:

```python
import json
import subprocess

from action.scripts.fixes import (
    fix_skip_reason,
    plan_fix_targets,
    render_fix_pr_body,
    run_fix,
    verified,
)


class FakeRunner:
    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        stdout, returncode = self._results.pop(0) if self._results else ("", 0)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")


def _finding(rule="reentrancy-eth", file="contracts/A.sol", severity="HIGH"):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": rule,
        "locations": [{"file": file, "line": 11}],
    }


def test_skip_when_fix_prs_are_disabled():
    reason = fix_skip_reason(
        open_fix_prs=False, has_llm_key=True, is_fork=False, head_ref="feature"
    )
    assert reason is not None and "open-fix-prs" in reason


def test_skip_on_fork_prs_because_the_token_is_read_only():
    reason = fix_skip_reason(
        open_fix_prs=True, has_llm_key=True, is_fork=True, head_ref="feature"
    )
    assert reason is not None and "fork" in reason.lower()


def test_skip_on_auras_own_fix_branch_to_prevent_recursion():
    reason = fix_skip_reason(
        open_fix_prs=True, has_llm_key=True, is_fork=False, head_ref="aura/auto-fixes/pr-4"
    )
    assert reason is not None and "fix PR" in reason


def test_skip_without_an_llm_key_because_the_stub_cannot_patch():
    reason = fix_skip_reason(
        open_fix_prs=True, has_llm_key=False, is_fork=False, head_ref="feature"
    )
    assert reason is not None and "LLM" in reason


def test_no_skip_when_everything_is_configured():
    assert (
        fix_skip_reason(open_fix_prs=True, has_llm_key=True, is_fork=False, head_ref="feature")
        is None
    )


def test_plan_targets_pairs_each_changed_sol_file_with_each_rule():
    findings = [_finding(rule="a"), _finding(rule="b")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == [
        ("contracts/A.sol", "a"),
        ("contracts/A.sol", "b"),
    ]


def test_plan_targets_dedupes_repeated_file_rule_pairs():
    findings = [_finding(rule="a"), _finding(rule="a")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == [("contracts/A.sol", "a")]


def test_plan_targets_ignores_files_the_pr_did_not_change():
    findings = [_finding(file="contracts/Other.sol")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == []


def test_plan_targets_ignores_non_solidity_files():
    findings = [_finding(file="README.md")]
    assert plan_fix_targets(findings, ["README.md"]) == []


def test_run_fix_invokes_aura_fix_with_write_and_json():
    fake = FakeRunner([(json.dumps({"verdict": "VERIFIED", "detail": "ok"}), 0)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "VERIFIED"
    cmd = fake.calls[0]
    assert cmd[:2] == ["aura", "fix"]
    assert "--write" in cmd and "--json" in cmd
    assert "--rule" in cmd and "reentrancy-eth" in cmd


def test_run_fix_records_a_nonzero_exit_without_aborting():
    """`aura fix` exits 1 on FAILED/REGRESSED; one bad rule must not stop the rest."""
    fake = FakeRunner([(json.dumps({"verdict": "REGRESSED", "detail": "new findings"}), 1)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "REGRESSED"


def test_run_fix_reports_unparseable_output_as_an_error():
    fake = FakeRunner([("traceback nonsense", 1)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "ERROR"


def test_verified_keeps_only_verified_verdicts():
    """docs/NEVER_DO.md: never claim a fix is safe without verification."""
    results = [
        {"verdict": "VERIFIED", "file": "a", "rule": "r1"},
        {"verdict": "REGRESSED", "file": "b", "rule": "r2"},
        {"verdict": "FAILED", "file": "c", "rule": "r3"},
        {"verdict": "UNVERIFIED", "file": "d", "rule": "r4"},
        {"verdict": "ERROR", "file": "e", "rule": "r5"},
    ]
    assert [r["rule"] for r in verified(results)] == ["r1"]


def test_fix_pr_body_lists_each_verified_fix_and_links_the_source_pr():
    body = render_fix_pr_body(
        [{"verdict": "VERIFIED", "file": "contracts/A.sol", "rule": "reentrancy-eth"}], 42
    )
    assert "contracts/A.sol" in body
    assert "reentrancy-eth" in body
    assert "#42" in body


def test_fix_pr_body_states_the_verification_guarantee():
    body = render_fix_pr_body(
        [{"verdict": "VERIFIED", "file": "contracts/A.sol", "rule": "reentrancy-eth"}], 42
    )
    assert "verified" in body.lower()
```

- [ ] **Step 2: Run to verify they fail**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_fixes.py -q
```

Expected: `ModuleNotFoundError: No module named 'action.scripts.fixes'`.

- [ ] **Step 3: Implement `action/scripts/fixes.py`**

```python
"""Planning and execution of `aura fix` runs for the auto-fix PR.

The rule that makes an automated PR acceptable at all: only VERIFIED
verdicts reach the branch. `aura fix --write` already refuses to write
anything else; `verified()` is the second gate on top of that.
"""

from __future__ import annotations

import json

from action.scripts.findings import finding_files, normalize_path
from action.scripts.ghcli import CommandError, run

FIX_BRANCH_PREFIX = "aura/auto-fixes/"


def fix_skip_reason(
    *, open_fix_prs: bool, has_llm_key: bool, is_fork: bool, head_ref: str
) -> str | None:
    """Why the fix step should not run, or None if it should."""
    if not open_fix_prs:
        return "disabled via `open-fix-prs: false`"
    if is_fork:
        # GitHub caps GITHUB_TOKEN at read-only for fork PRs regardless of
        # the workflow's permissions block, so the branch push cannot land.
        return "fork pull requests get a read-only token, so the fix branch cannot be pushed"
    if normalize_path(head_ref).startswith(FIX_BRANCH_PREFIX):
        return "this PR is already an AURA fix PR"
    if not has_llm_key:
        return "no LLM API key configured (`llm-api-key`), so only the deterministic stub is available"
    return None


def plan_fix_targets(findings: list[dict], changed_files) -> list[tuple[str, str]]:
    """(file, rule_id) pairs to attempt, deduplicated, in discovery order.

    Restricted to .sol files the PR actually changed — `aura fix` is
    single-file only (PROJECT_BRIEF "v1 does NOT").
    """
    wanted = {
        path for path in (normalize_path(p) for p in changed_files) if path.endswith(".sol")
    }
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        rule = str(finding.get("rule_id") or "").strip()
        if not rule:
            continue
        for path in finding_files(finding):
            if path not in wanted:
                continue
            key = (path, rule)
            if key not in seen:
                seen.add(key)
                targets.append(key)
    return targets


def run_fix(path: str, rule: str, *, runner=None, timeout: int = 900) -> dict:
    """Run `aura fix` for one file/rule pair and normalize the outcome.

    Never raises: `aura fix` exits 1 on FAILED/REGRESSED by design, and one
    unfixable rule must not abort the remaining targets.
    """
    try:
        out = run(
            ["aura", "fix", path, "--rule", rule, "--write", "--json"],
            runner=runner,
            check=False,
            timeout=timeout,
        )
    except (CommandError, OSError) as exc:
        return {"file": path, "rule": rule, "verdict": "ERROR", "detail": str(exc)}

    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return {
            "file": path,
            "rule": rule,
            "verdict": "ERROR",
            "detail": "could not parse `aura fix --json` output",
        }

    return {
        "file": path,
        "rule": rule,
        "verdict": str(payload.get("verdict") or "UNKNOWN"),
        "detail": str(payload.get("detail") or ""),
    }


def verified(results: list[dict]) -> list[dict]:
    """Only the VERIFIED results — the sole verdict allowed into a PR."""
    return [r for r in results if r.get("verdict") == "VERIFIED"]


def render_fix_pr_body(results: list[dict], source_pr: int | str) -> str:
    lines = [
        f"Automated remediation for #{source_pr}, generated by AURA.",
        "",
        "Every change below was **verified**: the patch was applied in an isolated "
        "workspace, compiled, and re-analyzed, and the target finding is confirmed "
        "gone with no new findings introduced. Unverified suggestions are never "
        "included here.",
        "",
        "| File | Rule resolved |",
        "|---|---|",
    ]
    for result in verified(results):
        lines.append(f"| `{result['file']}` | `{result['rule']}` |")
    lines.extend(
        [
            "",
            "_AURA assists code review — it does not replace a professional audit or "
            "formal verification. Review these changes before merging._",
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify they pass**

```bash
PYTHONPATH="$(pwd)" pytest tests/test_action_fixes.py -q
```

Expected: 15 passed.

- [ ] **Step 5: Implement `action/scripts/run_fixes.py`**

```python
"""Fix-PR entrypoint: run verified fixes, push a branch, upsert the PR.

Runs before the comment step so the comment can link the resulting PR.
Always exits 0 — a fix PR is a bonus surface, and failing to produce one
must not fail someone's build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from action.scripts.fixes import render_fix_pr_body, run_fix, verified
from action.scripts.fixes import fix_skip_reason as compute_skip_reason
from action.scripts.fixes import plan_fix_targets
from action.scripts.ghcli import CommandError, run
from action.scripts.run_gate import load_findings, read_changed_files

BOT_NAME = "aura-bot"
BOT_EMAIL = "aura-bot@users.noreply.github.com"


def emit(**outputs: str) -> None:
    """Write step outputs for action.yml to consume."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    pr_number = os.environ.get("AURA_PR_NUMBER", "").strip()
    if not pr_number:
        emit(fix_skip_reason="", fix_pr_url="")
        return 0

    skip = compute_skip_reason(
        open_fix_prs=os.environ.get("AURA_OPEN_FIX_PRS", "true").lower() == "true",
        has_llm_key=bool(os.environ.get("AURA_LLM_KEY_PRESENT", "").strip()),
        is_fork=os.environ.get("AURA_IS_FORK", "false").lower() == "true",
        head_ref=os.environ.get("AURA_HEAD_REF", ""),
    )
    if skip:
        print(f"Skipping AURA fix PR: {skip}")
        emit(fix_skip_reason=skip, fix_pr_url="")
        return 0

    findings, _ = load_findings(os.environ.get("AURA_FINDINGS_JSON", ""))
    changed = read_changed_files(os.environ.get("AURA_CHANGED_FILES", ""))
    targets = plan_fix_targets(findings, changed)
    if not targets:
        emit(fix_skip_reason="no fixable findings in this PR's changed Solidity files",
             fix_pr_url="")
        return 0

    head_sha = os.environ.get("AURA_HEAD_SHA", "").strip()
    head_ref = os.environ.get("AURA_HEAD_REF", "").strip()
    branch = f"aura/auto-fixes/pr-{pr_number}"

    try:
        # Fix on top of the PR's head, not the synthetic merge commit the
        # pull_request event checks out, so the PR contains only our changes.
        run(["git", "fetch", "--no-tags", "origin", head_sha])
        run(["git", "checkout", "-B", branch, head_sha])
    except CommandError as exc:
        print(f"::warning::Could not prepare the fix branch: {exc}")
        emit(fix_skip_reason="could not prepare the fix branch", fix_pr_url="")
        return 0

    results = [run_fix(path, rule) for path, rule in targets]
    for result in results:
        print(f"  {result['verdict']:<10} {result['file']} :: {result['rule']}")

    wins = verified(results)
    if not wins:
        emit(fix_skip_reason="no fix passed verification", fix_pr_url="")
        return 0

    body_path = Path(os.environ.get("AURA_FIX_BODY_PATH", "aura-fix-pr.md"))
    body_path.write_text(render_fix_pr_body(results, pr_number), encoding="utf-8")

    repo = os.environ.get("AURA_REPO", "")
    try:
        run(["git", "config", "user.name", BOT_NAME])
        run(["git", "config", "user.email", BOT_EMAIL])
        # Only .sol files: `aura fix` also drops reports/ artifacts in cwd.
        run(["git", "add", "--", "*.sol"])
        run(
            [
                "git",
                "commit",
                "-m",
                f"fix: apply {len(wins)} AURA-verified remediation(s) for #{pr_number}",
            ]
        )
        run(["git", "push", "--force", "origin", branch])
    except CommandError as exc:
        print(f"::warning::Could not push the fix branch: {exc}")
        emit(fix_skip_reason="could not push the fix branch", fix_pr_url="")
        return 0

    existing = run(
        ["gh", "pr", "list", "--repo", repo, "--head", branch, "--json", "url", "--jq", ".[].url"],
        check=False,
    ).strip()

    try:
        if existing:
            run(["gh", "pr", "edit", existing, "--body-file", str(body_path)])
            url = existing
        else:
            url = run(
                [
                    "gh", "pr", "create",
                    "--repo", repo,
                    "--base", head_ref,
                    "--head", branch,
                    "--title", f"AURA: verified fixes for #{pr_number}",
                    "--body-file", str(body_path),
                ]
            ).strip().splitlines()[-1]
    except (CommandError, IndexError) as exc:
        print(f"::warning::Could not open the fix PR: {exc}")
        emit(fix_skip_reason="could not open the fix PR", fix_pr_url="")
        return 0

    print(f"AURA fix PR ready: {url}")
    emit(fix_skip_reason="", fix_pr_url=url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Full suite + lint, then commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && isort . && black . && ruff check .
git add action/scripts/fixes.py action/scripts/run_fixes.py tests/test_action_fixes.py
git commit -m "feat(action): open a PR containing only AURA-verified fixes

Plans (file, rule) targets from the PR's changed Solidity files, runs
'aura fix --write --json' per target, and opens/updates one aggregated PR
from the VERIFIED results only. Guarded against forks (read-only token),
recursion on its own branch, a missing LLM key, and empty result sets.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `action.yml` — the composite action

**Files:**
- Create: `action.yml`
- Modify: `MANIFEST.in`

**Interfaces:**
- Consumes: `aura analyze --sarif` (Task 1); `python -m action.scripts.{run_fixes,run_comment,run_gate}` (Tasks 5-6).
- Produces: `uses: bhavi-g/AURA@<ref>` with the inputs below; outputs `findings-count`, `score`, `sarif-path`.

- [ ] **Step 1: Write `action.yml`**

```yaml
name: "AURA Solidity Security Scan"
description: "Detect Solidity vulnerabilities, upload SARIF to Code Scanning, comment on the PR, and open verified fixes."
author: "Bhavish Goyal"

branding:
  icon: shield
  color: purple

inputs:
  path:
    description: "Path to analyze."
    required: false
    default: "."
  solc-version:
    description: "Solidity compiler version to install via solc-select."
    required: false
    default: "0.8.20"
  aura-version:
    description: "Pin a specific aura-audit release. Empty installs the latest."
    required: false
    default: ""
  github-token:
    description: "Token used for PR comments and fix PRs."
    required: false
    default: ${{ github.token }}
  fail-on:
    description: "Fail the check on findings at or above this severity: critical, high, medium, low, or none."
    required: false
    default: "high"
  llm-provider:
    description: "LLM provider for fix generation: anthropic or openai. Empty disables fixes."
    required: false
    default: ""
  llm-api-key:
    description: "API key for the chosen LLM provider. Required for fix PRs."
    required: false
    default: ""
  open-fix-prs:
    description: "Open a PR with AURA-verified fixes. Requires llm-api-key."
    required: false
    default: "true"

outputs:
  findings-count:
    description: "Total findings across the scanned path."
    value: ${{ steps.analyze.outputs.findings-count }}
  score:
    description: "Aggregate risk score."
    value: ${{ steps.analyze.outputs.score }}
  sarif-path:
    description: "Path to the generated SARIF file."
    value: ${{ steps.analyze.outputs.sarif-path }}

runs:
  using: composite
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install AURA and Slither
      shell: bash
      run: |
        python -m pip install -U pip
        if [ -n "${{ inputs.aura-version }}" ]; then
          pip install "aura-audit==${{ inputs.aura-version }}"
        else
          pip install aura-audit
        fi
        pip install slither-analyzer solc-select

    - name: Install solc
      shell: bash
      run: |
        solc-select install "${{ inputs.solc-version }}"
        solc-select use "${{ inputs.solc-version }}"
        solc --version

    - name: Analyze
      id: analyze
      shell: bash
      run: |
        set -o pipefail
        aura analyze "${{ inputs.path }}" --json --sarif aura-results.sarif > aura-findings.json
        python - <<'PY' >> "$GITHUB_OUTPUT"
        import json
        with open("aura-findings.json") as fh:
            data = json.load(fh)
        print(f"findings-count={len(data.get('findings') or [])}")
        print(f"score={data.get('score', 0)}")
        print("sarif-path=aura-results.sarif")
        PY

    - name: Determine changed files
      id: changed
      if: github.event_name == 'pull_request'
      shell: bash
      run: |
        BASE="${{ github.event.pull_request.base.ref }}"
        if git fetch --no-tags --depth=0 origin "$BASE" 2>/dev/null \
           && git diff --name-only "origin/$BASE...HEAD" > aura-changed-files.txt 2>/dev/null; then
          echo "ok=true" >> "$GITHUB_OUTPUT"
        else
          : > aura-changed-files.txt
          echo "ok=false" >> "$GITHUB_OUTPUT"
          echo "::warning::Could not diff against origin/$BASE — check out with fetch-depth: 0."
        fi

    - name: Upload SARIF to Code Scanning
      if: always()
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: aura-results.sarif

    - name: Open verified-fix PR
      id: fixes
      if: always() && github.event_name == 'pull_request'
      shell: bash
      env:
        GH_TOKEN: ${{ inputs.github-token }}
        AURA_LLM_PROVIDER: ${{ inputs.llm-provider }}
        ANTHROPIC_API_KEY: ${{ inputs.llm-provider == 'anthropic' && inputs.llm-api-key || '' }}
        OPENAI_API_KEY: ${{ inputs.llm-provider == 'openai' && inputs.llm-api-key || '' }}
        AURA_LLM_KEY_PRESENT: ${{ inputs.llm-api-key }}
        AURA_OPEN_FIX_PRS: ${{ inputs.open-fix-prs }}
        AURA_IS_FORK: ${{ github.event.pull_request.head.repo.fork }}
        AURA_HEAD_REF: ${{ github.event.pull_request.head.ref }}
        AURA_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        AURA_PR_NUMBER: ${{ github.event.pull_request.number }}
        AURA_REPO: ${{ github.repository }}
        AURA_FINDINGS_JSON: aura-findings.json
        AURA_CHANGED_FILES: aura-changed-files.txt
        PYTHONPATH: ${{ github.action_path }}
      run: python -m action.scripts.run_fixes

    - name: Comment on the PR
      if: always() && github.event_name == 'pull_request'
      shell: bash
      env:
        GH_TOKEN: ${{ inputs.github-token }}
        AURA_PR_NUMBER: ${{ github.event.pull_request.number }}
        AURA_REPO: ${{ github.repository }}
        AURA_FINDINGS_JSON: aura-findings.json
        AURA_CHANGED_FILES: aura-changed-files.txt
        AURA_CHANGED_FILES_OK: ${{ steps.changed.outputs.ok }}
        AURA_FAIL_ON: ${{ inputs.fail-on }}
        AURA_FIX_PR_URL: ${{ steps.fixes.outputs.fix_pr_url }}
        AURA_FIX_SKIP_REASON: ${{ steps.fixes.outputs.fix_skip_reason }}
        AURA_COMMENT_BODY_PATH: aura-comment.md
        PYTHONPATH: ${{ github.action_path }}
      run: python -m action.scripts.run_comment

    - name: Severity gate
      if: always()
      shell: bash
      env:
        AURA_FINDINGS_JSON: aura-findings.json
        AURA_FAIL_ON: ${{ inputs.fail-on }}
        PYTHONPATH: ${{ github.action_path }}
      run: python -m action.scripts.run_gate
```

`PYTHONPATH: ${{ github.action_path }}` is what lets `python -m action.scripts.*` resolve when the action is consumed from another repo — the action's own checkout lives at `github.action_path`, not the caller's workspace.

- [ ] **Step 2: Validate the YAML parses**

```bash
python -c "import yaml,sys; yaml.safe_load(open('action.yml')); print('action.yml OK')"
```

If PyYAML is not in the venv: `pip install pyyaml` first (dev-only, do not add it to `pyproject.toml`).

Expected: `action.yml OK`.

- [ ] **Step 3: Keep the action out of the sdist**

`docs/NEVER_DO.md`: never trust a source diff to know what a release ships. Add to `MANIFEST.in`, in the existing `prune` block (alphabetical, before `prune api`):

```
prune action
```

and in the `exclude` block (alphabetical, before `exclude docker-compose.yml`):

```
exclude action.yml
```

- [ ] **Step 4: Verify the built sdist is unchanged in size**

```bash
python -m build --sdist 2>&1 | tail -3
tar tzf dist/aura_audit-*.tar.gz | wc -l
tar tzf dist/aura_audit-*.tar.gz | grep -c "action" || echo "no action files: correct"
```

Expected: 50 files (the Phase 3 baseline), and zero `action` entries.

- [ ] **Step 5: Lint and commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && ruff check . && black --check . && isort --check-only .
git add action.yml MANIFEST.in
git commit -m "feat(action): add the composite action definition

Installs aura-audit + slither + solc on the runner, analyzes, uploads
SARIF, opens the verified-fix PR, comments, then gates last so a red
check never suppresses the surfaces above it. Pruned from the sdist.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Dogfood workflow + README

**Files:**
- Create: `.github/workflows/aura-pr-scan.yml`
- Modify: `README.md`

- [ ] **Step 1: Write the dogfood workflow**

`.github/workflows/aura-pr-scan.yml`:

```yaml
name: aura-pr-scan

on:
  pull_request:

concurrency:
  group: aura-pr-scan-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  security-events: write
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run AURA
        uses: ./
        with:
          path: samples/contracts
          # samples/contracts holds deliberately vulnerable fixtures, so a
          # gate would fail every PR by design, and auto-fixing them would
          # defeat their purpose as test data.
          fail-on: none
          open-fix-prs: false
```

- [ ] **Step 2: Validate it parses**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/aura-pr-scan.yml')); print('workflow OK')"
```

- [ ] **Step 3: Add the README section**

Insert after the installation section (find it with `grep -n "pipx install aura-audit" README.md`):

````markdown
## GitHub Action

Run AURA on every pull request: findings land in the Security tab via SARIF,
a summary comment lands on the PR, and (optionally) verified fixes land as
their own PR.

```yaml
name: aura

on:
  pull_request:

permissions:
  contents: write        # needed only for auto-fix PRs; use `read` otherwise
  security-events: write # SARIF upload
  pull-requests: write   # PR comment + fix PR

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required — AURA diffs against the PR base

      - uses: bhavi-g/AURA@main
        with:
          path: contracts
          solc-version: "0.8.20"
          fail-on: high
          # Optional: enables PRs containing AURA-verified fixes
          llm-provider: anthropic
          llm-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Inputs

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Path to analyze |
| `solc-version` | `0.8.20` | Compiler version installed via `solc-select` |
| `aura-version` | latest | Pin a specific `aura-audit` release |
| `github-token` | `${{ github.token }}` | Token for PR comments and fix PRs |
| `fail-on` | `high` | Fail on findings at/above this severity; `none` disables |
| `llm-provider` | — | `anthropic` or `openai`; required for fix PRs |
| `llm-api-key` | — | API key for that provider |
| `open-fix-prs` | `true` | Open a PR with verified fixes (no-op without a key) |

### Outputs

`findings-count`, `score`, `sarif-path`.

### Notes

- **`fetch-depth: 0` is required.** Without it AURA cannot diff against the PR
  base, and the comment falls back to listing every finding.
- **Fix PRs contain only `VERIFIED` fixes** — applied, compiled, and
  re-analyzed with the finding confirmed gone. Unverified suggestions are
  never opened as a PR.
- **Fix PRs are skipped on pull requests from forks.** GitHub issues a
  read-only token there, so the fix branch cannot be pushed.
````

- [ ] **Step 4: Lint and commit**

```bash
PYTHONPATH="$(pwd)" pytest -q && ruff check . && black --check . && isort --check-only .
git add .github/workflows/aura-pr-scan.yml README.md
git commit -m "docs: dogfood workflow and README section for the AURA Action

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: ADRs, phase/brief updates, session log

`CLAUDE.md` requires ADRs for real decisions and a session log to close the session.

**Files:**
- Create: `docs/adr/0006-composite-github-action.md`, `docs/adr/0007-verified-only-fix-prs.md`, `docs/sessions/2026-08-06-session.md`
- Modify: `docs/adr/README.md`, `docs/phases/phase-4.md`, `docs/PROJECT_BRIEF.md`

- [ ] **Step 1: Write ADR 0006**

`docs/adr/0006-composite-github-action.md`:

```markdown
# 0006 — Composite GitHub Action at the repo root

**Status:** accepted
**Date:** 2026-08-06

## Context

Phase 4 ships AURA as a GitHub Action. Two packaging choices had to be made:
container vs. composite, and same-repo vs. a dedicated actions repo.

A Docker container action would pin Python, `solc`, and Slither into one
reproducible image. It also means building, publishing, and patching that
image, and paying an image pull on every run.

## Decision

A **composite action**, defined in **`action.yml` at the repo root**, so
consumers write `uses: bhavi-g/AURA@<ref>`.

Reproducibility is recovered through inputs rather than an image:
`solc-version` pins the compiler and `aura-version` pins the AURA release.

The action's Python glue lives in `action/scripts/`, resolved at runtime via
`PYTHONPATH: ${{ github.action_path }}`, and is pruned from the sdist in
`MANIFEST.in` so it never ships inside the `aura-audit` wheel.

## Consequences

- No image to build, publish, or keep patched; startup is a `pip install`.
- Consumers who want byte-for-byte reproducibility must pin `aura-version`
  and `solc-version` themselves; the defaults track latest.
- The action version and the PyPI release version share a tag, so an action
  fix requires cutting a release tag even when no Python code changed.
- A second repo for the action was rejected: it would split the ADRs, tests,
  and release process across two places for no benefit at this size.
```

- [ ] **Step 2: Write ADR 0007**

`docs/adr/0007-verified-only-fix-prs.md`:

```markdown
# 0007 — Auto-opened fix PRs carry VERIFIED fixes only

**Status:** accepted
**Date:** 2026-08-06

## Context

Phase 4's action can open pull requests containing AURA-generated
remediations. An automated PR against someone's contracts is the highest-
trust action AURA takes: a wrong patch to a Solidity contract is not a
cosmetic bug.

ADR 0004 established the verified-fix loop — apply, compile, re-analyze —
producing verdicts VERIFIED / REGRESSED / FAILED / UNVERIFIED.
`docs/NEVER_DO.md` forbids claiming a fix is safe without verification.

## Decision

Only **VERIFIED** results may reach an auto-opened PR. Two independent
gates enforce this:

1. `aura fix --write` already refuses to write anything but VERIFIED
   (existing behavior in `cli.py::fix_cmd`).
2. `action/scripts/fixes.py::verified()` filters the result set again
   before any branch is committed or PR opened.

If nothing verifies, no PR is opened at all — an empty or speculative PR is
worse than silence. The PR body states the verification guarantee and
carries the not-an-audit disclaimer.

## Consequences

- Fix PRs are rarer but trustworthy: the review question becomes "do I want
  this change?" rather than "does this change even work?"
- REGRESSED/FAILED/UNVERIFIED outcomes are invisible to the PR author except
  as an absent fix PR. Surfacing them per-rule is possible future work.
- Fix PRs require an LLM API key; without one the provider abstraction falls
  back to a deterministic stub that cannot produce a patch, so the step
  skips and says so in the PR comment.
```

- [ ] **Step 3: Update the ADR index**

In `docs/adr/README.md`, add two rows to the table after the 0005 row:

```markdown
| [0006](0006-composite-github-action.md) | Composite GitHub Action at the repo root | accepted |
| [0007](0007-verified-only-fix-prs.md) | Auto-opened fix PRs carry VERIFIED fixes only | accepted |
```

And extend the trailing note's final sentence to mention that 0006-0007 are the decisions made on 2026-08-06 (Phase 4).

- [ ] **Step 4: Update the phase file and brief**

In `docs/phases/phase-4.md`, change `**Status:** planned` to:

```markdown
**Status:** shipped (2026-08-06)
```

In `docs/PROJECT_BRIEF.md`:
- Bump `_Last updated:_` to `2026-08-06`.
- Roadmap item 4 → `4. ✅ **GitHub Action** (SARIF Code Scanning + PR comments + verified-fix PRs)`.
- Success criterion 3 → prefix with `✅`.

- [ ] **Step 5: Write the session log**

`docs/sessions/2026-08-06-session.md`, following `docs/sessions/TEMPLATE.md`, with sections WHAT I BUILT / WORKS (verified — how?) / LEFT / BLOCKERS / Decisions → new ADRs / End-of-session. Record:
- the model used (note any Opus/Fable use, per `CLAUDE.md`'s model discipline)
- the exact verification commands run and their real output (test count, lint results)
- that the dogfood workflow's green run is only observable once the PR is open — record the actual result once CI reports, and do not claim it passed before then
- WHAT I PLAN TO DO next: Phase 5 (source-text analysis endpoint + deployed backend)

- [ ] **Step 6: Final full verification**

```bash
source .venv/bin/activate
PYTHONPATH="$(pwd)" pytest -q
ruff check .
black --check .
isort --check-only .
```

Record the real numbers in the session log. Expected: ~130 tests passing, all lint clean.

- [ ] **Step 7: Commit and push**

```bash
git add docs/
git commit -m "docs: ADRs 0006/0007, phase-4 shipped, session log

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -u origin feat/phase4-github-action
```

- [ ] **Step 8: Open the PR and watch the dogfood run**

```bash
gh pr create --base main --title "Phase 4: GitHub Action (SARIF + PR comments + verified fixes)" --body "$(cat <<'EOF'
Implements `docs/phases/phase-4.md`.

- `aura analyze --sarif` so the installed package emits SARIF
- Composite action at `action.yml` (ADR 0006)
- SARIF upload, upserted PR comment, `fail-on` severity gate
- Auto-opened PRs carrying VERIFIED fixes only (ADR 0007)
- Dogfood workflow + README

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

The `aura-pr-scan` check running green on this PR is phase-4.md's success
criterion. If it fails, fix it before considering the phase done — and update
the session log with what actually happened.

---

## Self-Review

**Spec coverage:**

| Spec decision | Task |
|---|---|
| 1. `aura analyze --sarif` | 1 |
| 2. Composite action, root `action.yml`, inputs/outputs, step order | 7 |
| 3. Full-path scan, comment filtered to changed files | 2 (`filter_by_files`), 7 (`changed` step) |
| 4. PR comment upsert via marker | 3, 4, 5 |
| 5. Severity gate, last step, glue-only | 2 (`gate_violations`), 5, 7 |
| 6. Verified-fix PRs + all four guards | 6 |
| 7. Glue in `action/scripts/`, stdlib-only, unit-tested | 2-6 |
| 8. Dogfood workflow | 8 |
| 9. README | 8 |
| ADRs (composite action; VERIFIED-only) | 9 |

No gaps.

**Refinement to note during implementation:** the spec says the comment lookup
finds the comment "authored by the token's identity containing that marker."
The plan filters on the marker alone — the token identity varies (a
`github-actions[bot]` default vs. a PAT), and the marker is already unique to
AURA. Same effect, one less failure mode.

**Placeholder scan:** clean — every code step contains real code, every test
step real assertions.

**Type consistency:** `severity_rank`, `normalize_path`, `finding_files`,
`filter_by_files`, `severity_counts`, `gate_violations`, `MARKER`,
`DISCLAIMER`, `render_comment`, `run`, `CommandError`, `changed_files`,
`find_marker_comment_id`, `upsert_pr_comment`, `load_findings`,
`read_changed_files`, `fix_skip_reason`, `plan_fix_targets`, `run_fix`,
`verified`, `render_fix_pr_body` — each defined once and used with matching
signatures downstream. `GATE_DISABLED` is defined in `findings.py` (Task 2)
and imported by `comment.py` (Task 3). The `AURA_*` environment contract in
Task 5 matches the `env:` blocks in Task 7's `action.yml`.
