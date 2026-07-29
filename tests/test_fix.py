import difflib
import shutil
import subprocess as sp

import pytest

from aura.core import fix


def test_finding_key_uses_rule_and_function():
    f = {
        "rule_id": "reentrancy-eth",
        "locations": [{"file": "x.sol", "line": 1, "function": "withdraw"}],
    }
    assert fix._finding_key(f) == ("reentrancy-eth", "withdraw")


def test_finding_key_falls_back_when_function_missing():
    f = {
        "rule_id": "solc-version",
        "locations": [{"file": "x.sol", "line": 1, "function": None}],
    }
    assert fix._finding_key(f) == ("solc-version",)


def test_finding_key_falls_back_when_no_locations():
    f = {"rule_id": "solc-version", "locations": []}
    assert fix._finding_key(f) == ("solc-version",)


def test_compile_with_solc_success(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(fix.subprocess, "run", lambda *a, **k: FakeProc())
    ok, err = fix._compile_with_solc(tmp_path / "x.sol")
    assert ok is True
    assert err == ""


def test_compile_with_solc_failure(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 1
        stderr = "ParserError: expected ';'"

    monkeypatch.setattr(fix.subprocess, "run", lambda *a, **k: FakeProc())
    ok, err = fix._compile_with_solc(tmp_path / "x.sol")
    assert ok is False
    assert "ParserError" in err


@pytest.mark.skipif(shutil.which("solc") is None, reason="solc not installed")
def test_compile_with_solc_real_valid_file(tmp_path):
    f = tmp_path / "Valid.sol"
    f.write_text("// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\ncontract Valid {}\n")
    ok, err = fix._compile_with_solc(f)
    assert ok is True
    assert err == ""


def _git_init(workdir):
    sp.run(["git", "init", "-q"], cwd=workdir, check=True)


def test_run_git_apply_success(tmp_path):
    _git_init(tmp_path)
    target = tmp_path / "Foo.sol"
    target.write_text("contract Foo {\n    uint x;\n}\n")

    diff_text = (
        "--- a/Foo.sol\n"
        "+++ b/Foo.sol\n"
        "@@ -1,3 +1,3 @@\n"
        " contract Foo {\n"
        "-    uint x;\n"
        "+    uint y;\n"
        " }\n"
    )

    ok, err = fix._run_git_apply(tmp_path, diff_text)
    assert ok is True
    assert err == ""
    assert "uint y;" in target.read_text()


def test_run_git_apply_failure_on_malformed_diff(tmp_path):
    _git_init(tmp_path)
    target = tmp_path / "Foo.sol"
    target.write_text("contract Foo {}\n")

    ok, err = fix._run_git_apply(tmp_path, "this is not a diff\n")
    assert ok is False
    assert err != ""


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def test_generate_fix_diff_includes_rule_and_target():
    finding = {
        "rule_id": "reentrancy-eth",
        "title": "reentrancy-eth",
        "description": "Reentrancy in withdraw()",
        "severity": "HIGH",
        "locations": [{"file": "contracts/X.sol", "line": 5, "function": "withdraw"}],
    }
    llm = FakeLLM(["--- a/x\n+++ b/x\n"])

    out = fix.generate_fix_diff(
        finding, "contract X {}", "reentrancy-eth", "contracts/X.sol", llm=llm
    )

    assert out.startswith("---")
    assert "RULE TO FIX: reentrancy-eth" in llm.prompts[0]
    assert "TARGET FILE: contracts/X.sol" in llm.prompts[0]


def test_generate_fix_diff_includes_error_context_when_retrying():
    finding = {
        "rule_id": "reentrancy-eth",
        "title": "reentrancy-eth",
        "description": "Reentrancy in withdraw()",
        "severity": "HIGH",
        "locations": [{"file": "contracts/X.sol", "line": 5, "function": "withdraw"}],
    }
    llm = FakeLLM(["--- a/x\n+++ b/x\n"])

    fix.generate_fix_diff(
        finding,
        "contract X {}",
        "reentrancy-eth",
        "contracts/X.sol",
        llm=llm,
        error_context="patch failed to apply: corrupt patch",
    )

    assert "patch failed to apply: corrupt patch" in llm.prompts[0]


def test_generate_fix_diff_prompt_separates_rule_constraints():
    """Verify that rule-specific constraints are properly separated (not garbled run-on)."""
    finding = {
        "rule_id": "reentrancy-eth",
        "title": "reentrancy-eth",
        "description": "Reentrancy in withdraw()",
        "severity": "HIGH",
        "locations": [{"file": "contracts/X.sol", "line": 5, "function": "withdraw"}],
    }
    llm = FakeLLM(["--- a/x\n+++ b/x\n"])

    fix.generate_fix_diff(finding, "contract X {}", "reentrancy-eth", "contracts/X.sol", llm=llm)

    prompt = llm.prompts[0]
    # Verify that rule constraints are separated with newlines, not garbled together
    assert "interactions.\n" in prompt, "reentrancy constraint should end with newline"
    assert "Update balances or state BEFORE" in prompt
    assert "Do NOT add comments instead of code.\n" in prompt
    assert "- If RULE is 'tx-origin':" in prompt
    assert "- If RULE is 'arbitrary-send-eth':" in prompt
    # Verify no run-on garbling of key phrases
    assert "interactions.Update" not in prompt, "constraints should be separated, not garbled"
    assert "code.- If RULE" not in prompt, "constraints should be separated, not garbled"
    assert "not msg.sender.\n" in prompt


def _make_unified_diff(path: str, original: str, patched: str) -> str:
    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=path,
        tofile=path,
    )
    return "".join(diff_lines)


def _original_finding():
    return {
        "rule_id": "reentrancy-eth",
        "locations": [{"file": "contracts/ReentrancyDemo.sol", "line": 11, "function": "withdraw"}],
    }


def _original_findings():
    return [_original_finding()]


def test_verify_fix_verified(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_findings)
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        fake_slither_findings,
        solc_available=True,
        analyzer_available=True,
    )

    assert result.verdict == "VERIFIED"
    assert result.patched_source is not None
    assert "patched" in result.patched_source


def test_verify_fix_failed_on_bad_apply(sample_contract):
    result = fix.verify_fix(
        str(sample_contract),
        "not a real diff\n",
        _original_finding(),
        _original_findings(),
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "did not apply" in result.detail


def test_verify_fix_failed_on_compile_error(monkeypatch, sample_contract):
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (False, "ParserError: bad"))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        _original_findings(),
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "does not compile" in result.detail


def test_verify_fix_failed_when_finding_still_present(
    monkeypatch, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        _original_findings(),
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "still present" in result.detail


def test_verify_fix_regressed_on_new_finding(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_plus_new = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"] + [
        {
            "rule_id": "unchecked-transfer",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 20, "function": "withdraw"}
            ],
        }
    ]
    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_plus_new)
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        fake_slither_findings,
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "REGRESSED"
    assert len(result.new_findings) == 1


def test_verify_fix_unverified_when_solc_missing(sample_contract):
    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        _original_findings(),
        solc_available=False,
        analyzer_available=True,
    )
    assert result.verdict == "UNVERIFIED"
    assert "solc" in result.degraded_reason


def test_verify_fix_unverified_when_analyzer_missing(monkeypatch, sample_contract):
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        _original_findings(),
        solc_available=True,
        analyzer_available=False,
    )
    assert result.verdict == "UNVERIFIED"
    assert "analyzer" in result.degraded_reason or "slither" in result.degraded_reason


def test_solc_available_reflects_which(monkeypatch):
    monkeypatch.setattr(
        fix.shutil, "which", lambda name: "/usr/bin/solc" if name == "solc" else None
    )
    assert fix._solc_available() is True

    monkeypatch.setattr(fix.shutil, "which", lambda name: None)
    assert fix._solc_available() is False


def test_analyzer_available_reflects_which(monkeypatch):
    monkeypatch.setattr(
        fix.shutil, "which", lambda name: "/usr/bin/slither" if name == "slither" else None
    )
    assert fix._analyzer_available() is True

    monkeypatch.setattr(fix.shutil, "which", lambda name: None)
    assert fix._analyzer_available() is False


def test_verify_fix_loop_retries_and_succeeds(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_findings)
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    good_diff = _make_unified_diff(str(sample_contract), original, patched)

    llm = FakeLLM(["not a diff at all", good_diff])

    result = fix.verify_fix_loop(
        str(sample_contract),
        _original_finding(),
        fake_slither_findings,
        "reentrancy-eth",
        llm=llm,
        max_retries=3,
    )

    assert result.verdict == "VERIFIED"
    assert result.attempts == 2
    assert len(llm.prompts) == 2
    assert "did not apply" in llm.prompts[1]


def test_verify_fix_loop_exhausts_retries(sample_contract):
    llm = FakeLLM(["not a diff", "still not a diff", "nope"])

    result = fix.verify_fix_loop(
        str(sample_contract),
        _original_finding(),
        _original_findings(),
        "reentrancy-eth",
        llm=llm,
        max_retries=3,
    )

    assert result.verdict == "FAILED"
    assert result.attempts == 3
    assert len(llm.prompts) == 3


def test_verify_fix_loop_stops_immediately_when_llm_declines(sample_contract):
    llm = FakeLLM(["# no safe fix is possible for this pattern"])

    result = fix.verify_fix_loop(
        str(sample_contract),
        _original_finding(),
        _original_findings(),
        "reentrancy-eth",
        llm=llm,
        max_retries=3,
    )

    assert result.verdict == "FAILED"
    assert result.attempts == 1
    assert len(llm.prompts) == 1
    assert "no safe fix" in result.detail
