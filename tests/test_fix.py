import shutil

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
