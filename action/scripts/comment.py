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

SCAN_INCOMPLETE_NOTICE = (
    "**⚠️ The scan did not complete.** The Analyze step failed before it could "
    "produce findings — any results below are stale or empty and must not be read as a "
    "clean bill of health. Check the workflow run logs for the cause."
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
    analyze_ok: bool = True,
    max_rows: int = 10,
) -> str:
    if not analyze_ok:
        # A failed Analyze step degrades `findings`/`score` to `[]`/`0`, which
        # would otherwise render as an indistinguishable-from-real "0
        # finding(s) ... No findings ... Severity gate: passed" — the worst
        # failure mode for a security tool. Render an explicit failure state
        # instead of a clean bill of health.
        return "\n".join(
            [MARKER, "## AURA — Solidity security scan", "", SCAN_INCOMPLETE_NOTICE, "", DISCLAIMER]
        )

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
    elif threshold == "error":
        lines.append("**Severity gate:** ⚠️ unknown (invalid threshold or evaluation error).")
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
