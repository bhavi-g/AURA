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

    violations = []
    gate_threshold = threshold
    try:
        violations = gate_violations(findings, threshold)
    except ValueError as exc:
        print(f"::warning::Invalid gate threshold: {exc}")
        gate_threshold = "error"

    body = render_comment(
        all_findings=findings,
        changed_findings=changed_findings,
        score=score,
        changed_files_ok=changed_ok,
        gate_threshold=gate_threshold,
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
    except (CommandError, KeyError, OSError, ValueError) as exc:
        print(f"::warning::Could not post the AURA PR comment: {exc}")
        return 0

    print(f"AURA PR comment {outcome}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
