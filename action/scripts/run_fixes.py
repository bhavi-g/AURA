"""Fix-PR entrypoint: run verified fixes, push a branch, upsert the PR.

Runs before the comment step so the comment can link the resulting PR.
Always exits 0 — a fix PR is a bonus surface, and failing to produce one
must not fail someone's build. Every `git`/`gh` call below can raise
`ghcli.CommandError`, `OSError` (e.g. `FileNotFoundError` if a binary is
missing), or `subprocess.TimeoutExpired` (NOT an `OSError` subclass) —
all three are caught at every call site so none of them can escape
`main()` and redden the caller's build.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from action.scripts.fixes import fix_skip_reason as compute_skip_reason
from action.scripts.fixes import plan_fix_targets, render_fix_pr_body, run_fix, verified
from action.scripts.ghcli import CommandError, run
from action.scripts.run_gate import load_findings, read_changed_files

BOT_NAME = "aura-bot"
BOT_EMAIL = "aura-bot@users.noreply.github.com"

# Every `git`/`gh` call must be guarded against all three of these — see the
# module docstring.
GIT_ERRORS = (CommandError, OSError, subprocess.TimeoutExpired)


def emit(**outputs: str) -> None:
    """Write step outputs for action.yml to consume."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def _restore_original_ref(ref: str | None) -> None:
    """Best-effort: leave the caller's checkout the way we found it.

    `git checkout -B` below mutates the *consuming* workflow's checkout in
    place. Any steps the user runs after `uses: bhavi-g/AURA@...` would
    otherwise see our fix branch instead of their own checkout. Restored on
    every exit path (see the `finally` in `main()`), including failures.
    """
    if not ref:
        return
    try:
        run(["git", "checkout", ref])
    except GIT_ERRORS as exc:
        print(f"::warning::Could not restore the original ref ({ref}): {exc}")


def _open_fix_pr(
    targets: list[tuple[str, str]], pr_number: str, head_sha: str, head_ref: str, branch: str
) -> int:
    try:
        # Fix on top of the PR's head, not the synthetic merge commit the
        # pull_request event checks out, so the PR contains only our changes.
        run(["git", "fetch", "--no-tags", "origin", head_sha])
        run(["git", "checkout", "-B", branch, head_sha])
    except GIT_ERRORS as exc:
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
    # Only the files a VERIFIED result actually touched — never a tree-wide
    # glob. This makes the safety invariant structural: if `aura fix` is
    # killed mid-write by its own timeout, that target's verdict is ERROR
    # and its (possibly truncated) file is never staged, even when a
    # different target in the same run verified (docs/NEVER_DO.md: never
    # claim a fix is safe without verification).
    staged = list(dict.fromkeys(result["file"] for result in wins))
    try:
        run(["git", "config", "user.name", BOT_NAME])
        run(["git", "config", "user.email", BOT_EMAIL])
        run(["git", "add", "--", *staged])
        run(
            [
                "git",
                "commit",
                "-m",
                f"fix: apply {len(wins)} AURA-verified remediation(s) for #{pr_number}",
            ]
        )
        run(["git", "push", "--force", "origin", branch])
    except GIT_ERRORS as exc:
        print(f"::warning::Could not push the fix branch: {exc}")
        emit(fix_skip_reason="could not push the fix branch", fix_pr_url="")
        return 0

    try:
        existing = run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--head",
                branch,
                "--json",
                "url",
                "--jq",
                ".[].url",
            ],
            check=False,
        ).strip()
    except GIT_ERRORS as exc:
        print(f"::warning::Could not check for an existing fix PR: {exc}")
        emit(fix_skip_reason="could not open the fix PR", fix_pr_url="")
        return 0

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
    except (*GIT_ERRORS, IndexError) as exc:
        print(f"::warning::Could not open the fix PR: {exc}")
        emit(fix_skip_reason="could not open the fix PR", fix_pr_url="")
        return 0

    print(f"AURA fix PR ready: {url}")
    emit(fix_skip_reason="", fix_pr_url=url)
    return 0


def main() -> int:
    pr_number = os.environ.get("AURA_PR_NUMBER", "").strip()
    if not pr_number:
        emit(fix_skip_reason="", fix_pr_url="")
        return 0

    skip = compute_skip_reason(
        open_fix_prs=os.environ.get("AURA_OPEN_FIX_PRS", "true").lower() == "true",
        has_llm_key=os.environ.get("AURA_LLM_KEY_PRESENT", "false").lower() == "true",
        is_fork=os.environ.get("AURA_IS_FORK", "false").lower() == "true",
        head_ref=os.environ.get("AURA_HEAD_REF", ""),
        llm_provider=os.environ.get("AURA_LLM_PROVIDER", ""),
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

    original_ref: str | None = None
    try:
        original_ref = run(["git", "rev-parse", "HEAD"]).strip() or None
    except GIT_ERRORS as exc:
        print(f"::warning::Could not capture the current ref: {exc}")

    try:
        return _open_fix_pr(targets, pr_number, head_sha, head_ref, branch)
    finally:
        _restore_original_ref(original_ref)


if __name__ == "__main__":
    sys.exit(main())
