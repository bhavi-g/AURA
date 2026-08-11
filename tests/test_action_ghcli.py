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
