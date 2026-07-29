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
