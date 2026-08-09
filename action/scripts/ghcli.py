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
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{(proc.stderr or '').strip()}"
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
            [
                "gh",
                "api",
                "--paginate",
                "--jq",
                query,
                f"/repos/{repo}/issues/{pr_number}/comments",
            ],
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
                "gh",
                "api",
                "--method",
                "POST",
                "-F",
                f"body=@{path}",
                f"/repos/{repo}/issues/{pr_number}/comments",
            ],
            runner=runner,
        )
        return "created"

    run(
        [
            "gh",
            "api",
            "--method",
            "PATCH",
            "-F",
            f"body=@{path}",
            f"/repos/{repo}/issues/comments/{comment_id}",
        ],
        runner=runner,
    )
    return "updated"
