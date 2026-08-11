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
