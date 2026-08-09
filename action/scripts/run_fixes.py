"""Fix-PR entrypoint: run verified fixes, push a branch, upsert the PR.

Runs before the comment step so the comment can link the resulting PR.
Always exits 0 — a fix PR is a bonus surface, and failing to produce one
must not fail someone's build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from action.scripts.fixes import fix_skip_reason as compute_skip_reason
from action.scripts.fixes import plan_fix_targets, render_fix_pr_body, run_fix, verified
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
        emit(
            fix_skip_reason="no fixable findings in this PR's changed Solidity files",
            fix_pr_url="",
        )
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
            url = (
                run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--repo",
                        repo,
                        "--base",
                        head_ref,
                        "--head",
                        branch,
                        "--title",
                        f"AURA: verified fixes for #{pr_number}",
                        "--body-file",
                        str(body_path),
                    ]
                )
                .strip()
                .splitlines()[-1]
            )
    except (CommandError, IndexError) as exc:
        print(f"::warning::Could not open the fix PR: {exc}")
        emit(fix_skip_reason="could not open the fix PR", fix_pr_url="")
        return 0

    print(f"AURA fix PR ready: {url}")
    emit(fix_skip_reason="", fix_pr_url=url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
