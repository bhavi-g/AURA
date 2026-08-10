import json
import subprocess
from unittest.mock import patch

from action.scripts.fixes import (
    fix_skip_reason,
    plan_fix_targets,
    render_fix_pr_body,
    run_fix,
    verified,
)
from action.scripts.run_fixes import main as run_fixes_main


class FakeRunner:
    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        stdout, returncode = self._results.pop(0) if self._results else ("", 0)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")


def _finding(rule="reentrancy-eth", file="contracts/A.sol", severity="HIGH"):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": rule,
        "locations": [{"file": file, "line": 11}],
    }


def test_skip_when_fix_prs_are_disabled():
    reason = fix_skip_reason(
        open_fix_prs=False, has_llm_key=True, is_fork=False, head_ref="feature"
    )
    assert reason is not None and "open-fix-prs" in reason


def test_skip_on_fork_prs_because_the_token_is_read_only():
    reason = fix_skip_reason(open_fix_prs=True, has_llm_key=True, is_fork=True, head_ref="feature")
    assert reason is not None and "fork" in reason.lower()


def test_skip_on_auras_own_fix_branch_to_prevent_recursion():
    reason = fix_skip_reason(
        open_fix_prs=True, has_llm_key=True, is_fork=False, head_ref="aura/auto-fixes/pr-4"
    )
    assert reason is not None and "fix PR" in reason


def test_skip_without_an_llm_key_because_the_stub_cannot_patch():
    reason = fix_skip_reason(
        open_fix_prs=True, has_llm_key=False, is_fork=False, head_ref="feature"
    )
    assert reason is not None and "LLM" in reason


def test_no_skip_when_everything_is_configured():
    assert (
        fix_skip_reason(open_fix_prs=True, has_llm_key=True, is_fork=False, head_ref="feature")
        is None
    )


def test_plan_targets_pairs_each_changed_sol_file_with_each_rule():
    findings = [_finding(rule="a"), _finding(rule="b")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == [
        ("contracts/A.sol", "a"),
        ("contracts/A.sol", "b"),
    ]


def test_plan_targets_dedupes_repeated_file_rule_pairs():
    findings = [_finding(rule="a"), _finding(rule="a")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == [("contracts/A.sol", "a")]


def test_plan_targets_ignores_files_the_pr_did_not_change():
    findings = [_finding(file="contracts/Other.sol")]
    assert plan_fix_targets(findings, ["contracts/A.sol"]) == []


def test_plan_targets_ignores_non_solidity_files():
    findings = [_finding(file="README.md")]
    assert plan_fix_targets(findings, ["README.md"]) == []


def test_run_fix_invokes_aura_fix_with_write_and_json():
    fake = FakeRunner([(json.dumps({"verdict": "VERIFIED", "detail": "ok"}), 0)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "VERIFIED"
    cmd = fake.calls[0]
    assert cmd[:2] == ["aura", "fix"]
    assert "--write" in cmd and "--json" in cmd
    assert "--rule" in cmd and "reentrancy-eth" in cmd


def test_run_fix_records_a_nonzero_exit_without_aborting():
    """`aura fix` exits 1 on FAILED/REGRESSED; one bad rule must not stop the rest."""
    fake = FakeRunner([(json.dumps({"verdict": "REGRESSED", "detail": "new findings"}), 1)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "REGRESSED"


def test_run_fix_reports_unparseable_output_as_an_error():
    fake = FakeRunner([("traceback nonsense", 1)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "ERROR"


def test_run_fix_parses_the_real_cli_shape_for_a_verified_write():
    """`cli.py::fix_cmd` prints the JSON payload then, because --write is set,
    always appends a human-readable line after it. A plain `json.loads` on
    that raw stdout raises "Extra data" — this is the shape the real CLI
    produces on a successful write, not the clean single-object JSON a naive
    fake would return."""
    stdout = (
        json.dumps({"verdict": "VERIFIED", "detail": "ok"}, indent=2)
        + "\n\nWrote verified fix to contracts/A.sol\n"
    )
    fake = FakeRunner([(stdout, 0)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "VERIFIED"


def test_run_fix_parses_the_real_cli_shape_for_a_refused_write():
    """Same "JSON then trailing text" shape, but for the refusal branch of
    `--write` when the verdict isn't VERIFIED."""
    stdout = (
        json.dumps({"verdict": "FAILED", "detail": "could not verify"}, indent=2)
        + "\n\nRefusing to write: verdict is FAILED, not VERIFIED.\n"
    )
    fake = FakeRunner([(stdout, 1)])
    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=fake)
    assert result["verdict"] == "FAILED"


def test_run_fix_maps_a_timeout_to_an_error_result_without_raising():
    """`subprocess.TimeoutExpired` is not an `OSError` subclass; a slow LLM
    call plus compile plus Slither can genuinely hit the timeout, and it
    must not propagate out of `run_fix` and crash the caller's loop."""

    def raise_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 900))

    result = run_fix("contracts/A.sol", "reentrancy-eth", runner=raise_timeout)
    assert result["verdict"] == "ERROR"


def test_verified_keeps_only_verified_verdicts():
    """docs/NEVER_DO.md: never claim a fix is safe without verification."""
    results = [
        {"verdict": "VERIFIED", "file": "a", "rule": "r1"},
        {"verdict": "REGRESSED", "file": "b", "rule": "r2"},
        {"verdict": "FAILED", "file": "c", "rule": "r3"},
        {"verdict": "UNVERIFIED", "file": "d", "rule": "r4"},
        {"verdict": "ERROR", "file": "e", "rule": "r5"},
    ]
    assert [r["rule"] for r in verified(results)] == ["r1"]


def test_fix_pr_body_lists_each_verified_fix_and_links_the_source_pr():
    body = render_fix_pr_body(
        [{"verdict": "VERIFIED", "file": "contracts/A.sol", "rule": "reentrancy-eth"}], 42
    )
    assert "contracts/A.sol" in body
    assert "reentrancy-eth" in body
    assert "#42" in body


def test_fix_pr_body_states_the_verification_guarantee():
    body = render_fix_pr_body(
        [{"verdict": "VERIFIED", "file": "contracts/A.sol", "rule": "reentrancy-eth"}], 42
    )
    assert "verified" in body.lower()


# --- action.scripts.run_fixes::main() -----------------------------------
#
# The orchestration entrypoint: git checkout/add/commit/push and gh pr
# create/edit all go through `action.scripts.ghcli.run`, imported directly
# into `run_fixes` (no injectable `runner=` at the main() layer), so these
# tests patch `action.scripts.run_fixes.run` and `...run_fix` instead. No
# test here touches a real `git`/`gh`/`aura` binary or the network, and
# GITHUB_OUTPUT is always pointed at a file under tmp_path.


def _set_base_env(monkeypatch, tmp_path, **overrides):
    values = {
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
        "AURA_PR_NUMBER": "42",
        "AURA_OPEN_FIX_PRS": "true",
        "AURA_LLM_KEY_PRESENT": "1",
        "AURA_IS_FORK": "false",
        "AURA_HEAD_REF": "feature",
        "AURA_HEAD_SHA": "deadbeef",
        "AURA_REPO": "owner/repo",
        "AURA_FINDINGS_JSON": str(tmp_path / "findings.json"),
        "AURA_CHANGED_FILES": str(tmp_path / "changed.txt"),
        "AURA_FIX_BODY_PATH": str(tmp_path / "fix-pr.md"),
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _read_outputs(tmp_path) -> dict:
    path = tmp_path / "output.txt"
    if not path.exists():
        return {}
    outputs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        outputs[key] = value
    return outputs


def test_run_fixes_main_skips_and_touches_no_git_when_fix_prs_disabled(tmp_path, monkeypatch):
    _set_base_env(monkeypatch, tmp_path, AURA_OPEN_FIX_PRS="false")
    with patch("action.scripts.run_fixes.run") as fake_run:
        assert run_fixes_main() == 0
    fake_run.assert_not_called()
    outputs = _read_outputs(tmp_path)
    assert "open-fix-prs" in outputs["fix_skip_reason"]
    assert outputs["fix_pr_url"] == ""


def test_run_fixes_main_skips_and_touches_no_git_on_a_fork_pr(tmp_path, monkeypatch):
    _set_base_env(monkeypatch, tmp_path, AURA_IS_FORK="true")
    with patch("action.scripts.run_fixes.run") as fake_run:
        assert run_fixes_main() == 0
    fake_run.assert_not_called()
    outputs = _read_outputs(tmp_path)
    assert "fork" in outputs["fix_skip_reason"].lower()


def test_run_fixes_main_skips_and_touches_no_git_on_auras_own_fix_branch(tmp_path, monkeypatch):
    _set_base_env(monkeypatch, tmp_path, AURA_HEAD_REF="aura/auto-fixes/pr-4")
    with patch("action.scripts.run_fixes.run") as fake_run:
        assert run_fixes_main() == 0
    fake_run.assert_not_called()
    outputs = _read_outputs(tmp_path)
    assert "fix PR" in outputs["fix_skip_reason"]


def test_run_fixes_main_skips_and_touches_no_git_without_an_llm_key(tmp_path, monkeypatch):
    _set_base_env(monkeypatch, tmp_path, AURA_LLM_KEY_PRESENT="")
    with patch("action.scripts.run_fixes.run") as fake_run:
        assert run_fixes_main() == 0
    fake_run.assert_not_called()
    outputs = _read_outputs(tmp_path)
    assert "LLM" in outputs["fix_skip_reason"]


def test_run_fixes_main_emits_skip_reason_when_nothing_verifies(tmp_path, monkeypatch):
    (tmp_path / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "rule_id": "reentrancy-eth",
                        "severity": "HIGH",
                        "locations": [{"file": "contracts/A.sol", "line": 1}],
                    }
                ],
                "score": 5.0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "changed.txt").write_text("contracts/A.sol\n", encoding="utf-8")
    _set_base_env(monkeypatch, tmp_path)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return ""

    with (
        patch("action.scripts.run_fixes.run", side_effect=fake_run),
        patch(
            "action.scripts.run_fixes.run_fix",
            return_value={
                "file": "contracts/A.sol",
                "rule": "reentrancy-eth",
                "verdict": "FAILED",
                "detail": "nope",
            },
        ),
    ):
        assert run_fixes_main() == 0

    # Only the branch-prep git calls ran; no add/commit/push, no gh at all.
    assert any(cmd[:2] == ["git", "fetch"] for cmd in calls)
    assert any(cmd[:2] == ["git", "checkout"] for cmd in calls)
    assert not any(cmd[:2] == ["git", "push"] for cmd in calls)
    assert not any(cmd[:2] == ["git", "commit"] for cmd in calls)
    assert not any(cmd and cmd[0] == "gh" for cmd in calls)
    outputs = _read_outputs(tmp_path)
    assert outputs["fix_skip_reason"] == "no fix passed verification"
    assert outputs["fix_pr_url"] == ""


def test_run_fixes_main_happy_path_pushes_the_branch_and_opens_the_pr_once(tmp_path, monkeypatch):
    (tmp_path / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "rule_id": "reentrancy-eth",
                        "severity": "HIGH",
                        "locations": [{"file": "contracts/A.sol", "line": 1}],
                    }
                ],
                "score": 5.0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "changed.txt").write_text("contracts/A.sol\n", encoding="utf-8")
    _set_base_env(monkeypatch, tmp_path)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "list"]:
            return ""  # no pre-existing fix PR
        if cmd[:3] == ["gh", "pr", "create"]:
            return "https://github.com/owner/repo/pull/99\n"
        return ""

    with (
        patch("action.scripts.run_fixes.run", side_effect=fake_run),
        patch(
            "action.scripts.run_fixes.run_fix",
            return_value={
                "file": "contracts/A.sol",
                "rule": "reentrancy-eth",
                "verdict": "VERIFIED",
                "detail": "ok",
            },
        ),
    ):
        assert run_fixes_main() == 0

    push_calls = [cmd for cmd in calls if cmd[:2] == ["git", "push"]]
    create_calls = [cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"]]
    edit_calls = [cmd for cmd in calls if cmd[:3] == ["gh", "pr", "edit"]]
    assert len(push_calls) == 1
    assert len(create_calls) == 1
    assert edit_calls == []
    outputs = _read_outputs(tmp_path)
    assert outputs["fix_pr_url"] == "https://github.com/owner/repo/pull/99"
    assert outputs["fix_skip_reason"] == ""
    assert (tmp_path / "fix-pr.md").exists()
