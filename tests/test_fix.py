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


def test_run_git_apply_times_out(monkeypatch, tmp_path):
    def _raise_timeout(*a, **k):
        raise sp.TimeoutExpired(cmd=["git", "apply"], timeout=30)

    monkeypatch.setattr(fix.subprocess, "run", _raise_timeout)

    ok, err = fix._run_git_apply(tmp_path, "--- a/x\n+++ b/x\n")
    assert ok is False
    assert "timed out" in err


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
        "description": "Reentrancy in withdraw()",
        "locations": [{"file": "contracts/ReentrancyDemo.sol", "line": 11, "function": "withdraw"}],
    }


def _original_findings():
    return [_original_finding()]


def _mock_analyzer_sequence(monkeypatch, slither_adapter, sequence):
    """
    Monkeypatch SlitherAnalyzer.run to return successive items from
    `sequence` on successive calls (clamping to the last item once
    exhausted). verify_fix now calls the analyzer twice per attempt (once
    for the pristine control run, once for the patched run), so tests need
    to control what each call sees rather than a single blanket return
    value.
    """
    calls = {"n": 0}

    def fake_run(self, target):
        idx = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        return sequence[idx]

    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", fake_run)
    return calls


def test_verify_fix_verified(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    # First call = control run on the pristine copy (must still contain the
    # target finding), second call = post-patch run (target resolved).
    _mock_analyzer_sequence(monkeypatch, slither_adapter, [fake_slither_findings, fixed_findings])
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
        solc_available=True,
        analyzer_available=True,
    )

    assert result.verdict == "VERIFIED"
    assert result.patched_source is not None
    assert "patched" in result.patched_source


def test_verify_fix_failed_when_git_init_times_out(monkeypatch, sample_contract):
    def _raise_timeout(*a, **k):
        raise sp.TimeoutExpired(cmd=["git", "init"], timeout=30)

    monkeypatch.setattr(fix.subprocess, "run", _raise_timeout)

    result = fix.verify_fix(
        str(sample_contract),
        "not a real diff\n",
        _original_finding(),
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "verification workspace" in result.detail


def test_verify_fix_failed_on_bad_apply(monkeypatch, sample_contract):
    from aura.core.analyzers import slither_adapter

    # Control run must succeed (find the target) so we actually reach the
    # apply step; only one call happens since apply fails immediately after.
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: _original_findings()
    )

    result = fix.verify_fix(
        str(sample_contract),
        "not a real diff\n",
        _original_finding(),
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "did not apply" in result.detail


def test_verify_fix_failed_on_compile_error(monkeypatch, sample_contract):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: _original_findings()
    )
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
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "FAILED"
    assert "does not compile" in result.detail


def test_verify_fix_failed_when_finding_still_present(
    monkeypatch, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    # Same findings on every call: the target finding is present in both
    # the control run and the post-patch run (patch didn't fix anything).
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
    # Control run sees the original findings (target present); patched run
    # sees the target resolved plus one new finding.
    _mock_analyzer_sequence(monkeypatch, slither_adapter, [fake_slither_findings, fixed_plus_new])
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
        solc_available=True,
        analyzer_available=True,
    )
    assert result.verdict == "REGRESSED"
    assert len(result.new_findings) == 1


def test_verify_fix_unverified_when_solc_missing(monkeypatch, sample_contract):
    from aura.core.analyzers import slither_adapter

    # Control run must succeed so we get past the target-finding check and
    # reach the solc-availability gate (which now happens after apply).
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: _original_findings()
    )

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        solc_available=False,
        analyzer_available=True,
    )
    assert result.verdict == "UNVERIFIED"
    assert "solc" in result.degraded_reason


def test_verify_fix_unverified_when_analyzer_missing(sample_contract):
    # analyzer_available=False must short-circuit before any workspace
    # setup or diff application — there is nothing meaningful to verify
    # without the analyzer for both the control run and the patched run.
    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = _make_unified_diff(str(sample_contract), original, patched)

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        solc_available=True,
        analyzer_available=False,
    )
    assert result.verdict == "UNVERIFIED"
    assert "analyzer" in result.degraded_reason or "slither" in result.degraded_reason
    assert result.patched_source is None


def test_verify_fix_unverified_when_control_run_misses_target(
    monkeypatch, sample_contract, fake_slither_findings
):
    """
    Issue 1: if the analyzer's control run against the pristine copy can't
    reproduce the target finding (e.g. the analyzer silently failed/crashed
    and returned []), verify_fix must return UNVERIFIED and must NOT
    attempt to apply the diff at all -- never VERIFIED.
    """
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", lambda self, target: [])

    apply_calls = {"n": 0}
    real_run_git_apply = fix._run_git_apply

    def spy_run_git_apply(workdir, diff_text):
        apply_calls["n"] += 1
        return real_run_git_apply(workdir, diff_text)

    monkeypatch.setattr(fix, "_run_git_apply", spy_run_git_apply)
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
        solc_available=True,
        analyzer_available=True,
    )

    assert result.verdict == "UNVERIFIED"
    assert result.verdict != "VERIFIED"
    assert "could not reproduce" in result.detail
    assert apply_calls["n"] == 0
    assert result.patched_source is None


def test_verify_fix_rejects_path_escaping_diff_header(
    monkeypatch, tmp_path, sample_contract, fake_slither_findings
):
    """
    Issue 2: a diff whose header claims a path outside the verification
    workspace (e.g. `--- a/../outside.txt`) must not be able to write
    outside that workspace. verify_fix rewrites diff headers to the
    canonical `a/<basename>`/`b/<basename>` before applying, and
    `_run_git_apply` no longer passes `--unsafe-paths`, so the patch can
    only ever land on the file we copied in.
    """
    from aura.core.analyzers import slither_adapter

    # Pin verify_fix's temp workspace to a known, inspectable location so we
    # can assert nothing escaped it (the real workspace is normally cleaned
    # up before the caller can inspect it).
    workdir = tmp_path / "aura-fix-workdir"

    def fake_mkdtemp(prefix=""):
        workdir.mkdir(parents=True, exist_ok=True)
        return str(workdir)

    monkeypatch.setattr(fix.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    original = sample_contract.read_text()
    patched = original.replace(
        'require(ok, "send failed");', 'require(ok, "send failed"); // patched'
    )
    diff_text = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile="a/../outside.txt",
            tofile="b/../outside.txt",
        )
    )
    assert diff_text.startswith("--- a/../outside.txt")
    assert "+++ b/../outside.txt" in diff_text

    result = fix.verify_fix(
        str(sample_contract),
        diff_text,
        _original_finding(),
        solc_available=True,
        analyzer_available=True,
    )

    # No file ever appears outside the (pinned) verification workspace --
    # note the workspace itself (workdir) is rmtree'd by verify_fix's own
    # cleanup before we get here, so the absence of "aura-fix-workdir" from
    # tmp_path is expected; what matters is "outside.txt" was never created
    # anywhere, i.e. the malicious header never escaped workdir in the first
    # place.
    assert not (tmp_path / "outside.txt").exists()
    assert not (tmp_path.parent / "outside.txt").exists()
    assert list(tmp_path.rglob("outside.txt")) == []

    # The rewritten header still points at our own file, so the patch
    # content itself applied successfully (findings mock is unchanged
    # between calls, so the target still reads as "present" afterwards).
    assert result.verdict == "FAILED"
    assert "still present" in result.detail
    assert result.patched_source is not None
    assert "// patched" in result.patched_source


def test_verify_fix_relative_target_with_bare_diff_headers(
    monkeypatch, temp_cwd, fake_slither_findings
):
    """
    Issue 3: a diff using bare, unprefixed headers (no `a/`/`b/`) against a
    relative target_path must still apply and verify successfully. This is
    the exact shape README.md documents for `aura fix` output, and was
    silently broken before the Issue 2 canonicalization fix (git apply's
    default -p1 strip level mismatched the old workdir/<relative-path>
    layout for bare headers).
    """
    from aura.core.analyzers import slither_adapter

    contracts_dir = temp_cwd / "contracts"
    contracts_dir.mkdir(exist_ok=True)
    rel_target = "contracts/ReentrancyDemo.sol"
    src = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ReentrancyDemo {
    mapping(address => uint256) public balances;

    function deposit() external payable { balances[msg.sender] += msg.value; }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] = 0;
    }
}
"""
    (contracts_dir / "ReentrancyDemo.sol").write_text(src)

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    _mock_analyzer_sequence(monkeypatch, slither_adapter, [fake_slither_findings, fixed_findings])
    monkeypatch.setattr(fix, "_compile_with_solc", lambda path: (True, ""))

    patched = src.replace('require(ok, "send failed");', 'require(ok, "send failed"); // patched')
    # Bare, unprefixed headers -- no "a/"/"b/" prefix.
    diff_text = _make_unified_diff(rel_target, src, patched)
    assert diff_text.startswith(f"--- {rel_target}")
    assert "a/" not in diff_text.splitlines()[0]

    result = fix.verify_fix(
        rel_target,
        diff_text,
        _original_finding(),
        solc_available=True,
        analyzer_available=True,
    )

    assert result.verdict == "VERIFIED"
    assert result.patched_source is not None
    assert "// patched" in result.patched_source


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


def test_analyzer_available_true_via_pipx_fallback_when_slither_missing(monkeypatch):
    # SlitherAnalyzer.run() falls back to `pipx run --spec slither-analyzer
    # slither ...` when slither isn't directly on PATH, so availability
    # should follow suit rather than reporting UNVERIFIED unnecessarily.
    monkeypatch.setattr(
        fix.shutil, "which", lambda name: "/usr/bin/pipx" if name == "pipx" else None
    )
    assert fix._analyzer_available() is True


def test_verify_fix_loop_retries_and_succeeds(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    # Each verify_fix call does a control run then (if it gets that far) a
    # patched run: attempt 1's malformed diff never gets past control+apply
    # (1 analyzer call), attempt 2 does control then patched (2 more calls).
    monkeypatch.setattr(fix, "_solc_available", lambda: True)
    monkeypatch.setattr(fix, "_analyzer_available", lambda: True)
    _mock_analyzer_sequence(
        monkeypatch,
        slither_adapter,
        [fake_slither_findings, fake_slither_findings, fixed_findings],
    )
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
        "reentrancy-eth",
        llm=llm,
        max_retries=3,
    )

    assert result.verdict == "VERIFIED"
    assert result.attempts == 2
    assert len(llm.prompts) == 2
    assert "did not apply" in llm.prompts[1]


def test_verify_fix_loop_exhausts_retries(monkeypatch, sample_contract):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(fix, "_solc_available", lambda: True)
    monkeypatch.setattr(fix, "_analyzer_available", lambda: True)
    # Control run always succeeds (target present); every attempt's
    # malformed diff then fails at the apply step.
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: _original_findings()
    )

    llm = FakeLLM(["not a diff", "still not a diff", "nope"])

    result = fix.verify_fix_loop(
        str(sample_contract),
        _original_finding(),
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
        "reentrancy-eth",
        llm=llm,
        max_retries=3,
    )

    assert result.verdict == "FAILED"
    assert result.attempts == 1
    assert len(llm.prompts) == 1
    assert "no safe fix" in result.detail
