from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SEVERITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
    "INFORMATIONAL": 0,
}


def _sort_key(f: dict[str, Any]) -> tuple[float, int]:
    """Sort by score desc, then severity, then rule_id for stability."""
    score = float(f.get("score", 0) or 0)
    sev = str(f.get("severity", "")).upper()
    sev_rank = SEVERITY_ORDER.get(sev, 0)
    return (-score, -sev_rank, f.get("rule_id", "") or "")


def summarize_findings(
    findings: Iterable[dict[str, Any]],
    max_items: int = 3,
) -> str:
    """
    Produce a simple human-readable explanation of the top findings.

    This is used by both the CLI (`aura explain`) and the API (`POST /explain`).
    """
    findings_list = list(findings)

    if not findings_list:
        return "No issues detected. The contract looks clean under the current analyzers."

    sorted_findings = sorted(findings_list, key=_sort_key)
    top = sorted_findings[: max(1, max_items)]

    lines: list[str] = []
    lines.append(f"Found {len(findings_list)} issue(s). Here are the top {len(top)}:")

    for idx, f in enumerate(top, start=1):
        rule = f.get("rule_id", "unknown-rule")
        sev = str(f.get("severity", "UNKNOWN")).upper()
        score = f.get("score", 0)
        title = f.get("title", "")
        short_desc = (f.get("description") or "").splitlines()[0].strip()

        lines.append(f"{idx}. [{sev}] {rule} (score={score}): " f"{title or short_desc}")

    return "\n".join(lines)
