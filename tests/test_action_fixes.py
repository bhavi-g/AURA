import json
import subprocess

from action.scripts.fixes import (
    fix_skip_reason,
    plan_fix_targets,
    render_fix_pr_body,
    run_fix,
    verified,
)


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
