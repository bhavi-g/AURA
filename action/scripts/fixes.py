"""Planning and execution of `aura fix` runs for the auto-fix PR.

The rule that makes an automated PR acceptable at all: only VERIFIED
verdicts reach the branch. `aura fix --write` already refuses to write
anything else; `verified()` is the second gate on top of that.
"""

from __future__ import annotations

import json
import subprocess

from action.scripts.findings import finding_files, normalize_path
from action.scripts.ghcli import CommandError, run

FIX_BRANCH_PREFIX = "aura/auto-fixes/"


def _extract_leading_json(text: str) -> str:
    """Extract the first JSON object `text` starts with, ignoring trailing noise.

    `aura fix --write --json` (`cli.py::fix_cmd`) prints the JSON payload and
    then, because `--write` is set, always appends a human-readable line
    after it ("Wrote verified fix to ..." or "Refusing to write: ..."). A
    plain `json.loads` on that stdout fails with "Extra data" on every real
    invocation. This mirrors the noise-tolerant parsing pattern in
    `slither_adapter.py::_extract_json_block`, adapted for JSON-then-text
    (Slither's wrapper banners are text-then-JSON) via `raw_decode`, which
    parses one JSON value and reports where it ended rather than assuming
    the whole string is JSON.
    """
    if not text:
        return ""
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return ""
    try:
        _, end = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError:
        return ""
    return stripped[:end]


def _standalone_skip_detail(text: str, rule: str) -> str | None:
    """Recognize `cli.py::fix_cmd`'s known plain-text non-error outcomes.

    `plan_fix_targets` derives (file, rule) pairs from a *directory-wide*
    analysis; `aura fix` then re-analyzes that one file *standalone*, where
    the rule may legitimately not reproduce (or the file may have no
    findings at all). `cli.py::fix_cmd` reports both as plain text (not
    JSON) and returns 0 — a normal outcome, not a parse failure. The exact
    strings mirror `cli.py`'s `typer.echo(...)` calls; do not edit `cli.py`
    to "fix" this, its output shapes are pinned by other tests.
    """
    stripped = text.strip()
    if stripped == "No issues detected. Nothing to fix.":
        return "no issues detected when the file was analyzed standalone"
    if stripped == f"No finding found for rule='{rule}'.":
        return "rule did not reproduce when the file was analyzed standalone"
    return None


def fix_skip_reason(
    *,
    open_fix_prs: bool,
    has_llm_key: bool,
    is_fork: bool,
    head_ref: str,
    llm_provider: str,
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
    if not str(llm_provider or "").strip():
        # `llm-provider`'s documented default is empty, meaning "disable
        # fixes" — but with no provider set, LLM() silently falls back to
        # the deterministic stub, which can never produce a VERIFIED verdict.
        # Without this check the step would still burn up to 900s per
        # target producing only non-VERIFIED stub results.
        return "no `llm-provider` configured (empty disables fixes; the LLM stub cannot verify)"
    if not has_llm_key:
        return (
            "no LLM API key configured (`llm-api-key`), so only the deterministic "
            "stub is available"
        )
    return None


def plan_fix_targets(findings: list[dict], changed_files) -> list[tuple[str, str]]:
    """(file, rule_id) pairs to attempt, deduplicated, in discovery order.

    Restricted to .sol files the PR actually changed — `aura fix` is
    single-file only (PROJECT_BRIEF "v1 does NOT").
    """
    wanted = {path for path in (normalize_path(p) for p in changed_files) if path.endswith(".sol")}
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
    unfixable rule must not abort the remaining targets. A slow LLM call
    plus compile plus Slither can genuinely hit `timeout`, and
    `subprocess.TimeoutExpired` is not an `OSError` subclass, so it is
    caught explicitly alongside `CommandError`.
    """
    try:
        out = run(
            ["aura", "fix", path, "--rule", rule, "--write", "--json"],
            runner=runner,
            check=False,
            timeout=timeout,
        )
    except (CommandError, OSError, subprocess.TimeoutExpired) as exc:
        return {"file": path, "rule": rule, "verdict": "ERROR", "detail": str(exc)}

    try:
        payload = json.loads(_extract_leading_json(out))
    except json.JSONDecodeError:
        skip_detail = _standalone_skip_detail(out, rule)
        if skip_detail is not None:
            return {"file": path, "rule": rule, "verdict": "SKIPPED", "detail": skip_detail}
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
