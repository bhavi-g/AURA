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
    if not isinstance(payload, dict):
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

    print(
        f"::error::AURA severity gate failed: {len(violations)} finding(s) at or above "
        f"'{threshold}'."
    )
    for finding in violations:
        location = (finding.get("locations") or [{}])[0]
        print(
            f"  [{finding.get('severity')}] {finding.get('rule_id')} "
            f"— {location.get('file')}:{location.get('line')}"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
