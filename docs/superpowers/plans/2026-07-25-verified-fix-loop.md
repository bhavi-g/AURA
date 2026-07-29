# Verified Fix Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `aura fix` verify a generated diff (apply → compile → re-analyze) before presenting it as usable, retrying with error feedback on failure, and degrading honestly when tools are unavailable.

**Architecture:** A new core module `src/aura/core/fix.py` owns diff generation and verification (extracted from `cli.py`, matching the existing interface-agnostic `core/` pattern). `cli.py`'s `fix_cmd` becomes a thin wrapper that calls into it and handles `--write`/`--json` presentation.

**Tech Stack:** Python 3.11, `subprocess` (git, solc), `tempfile`, existing `SlitherAnalyzer` / `LLM` / `build_llm_remediation_prompt`, `pytest` + `typer.testing.CliRunner` (matching existing test conventions in `tests/conftest.py`, `tests/test_cli.py`, `tests/test_pipeline.py`).

## Global Constraints

- Finding shape is `{"rule_id": str, ..., "locations": [{"file": str, "line": int, "function": str | None}], ...}` per `src/aura/core/analyzers/normalize.py`'s `Finding` TypedDict. Do NOT use the `f.get("location")` (singular) pattern seen in `core/explain.py` — that shape does not match real analyzer output and is a pre-existing, out-of-scope bug.
- Match "is the target finding gone" by `(rule_id, function)`; fall back to `(rule_id,)` alone when `function` is `None` (contract-level findings have no function).
- Default retry budget: 3 attempts total (`max_retries=3`).
- Tool availability (`solc`, analyzer) is checked once per `verify_fix_loop` call, not per attempt.
- `UNVERIFIED` must never be presented as equivalent to `VERIFIED` in any output surface (text, `--json`, or the `--write` gate).
- CI's `test` job does not install `solc`/`slither` (see `.github/workflows/ci.yml`) — all new tests must pass without those binaries present. Use `monkeypatch` for solc/analyzer behavior; real `git` and `git apply` are safe to depend on (git is fundamental to this repo). Where a test can also validate against the real `solc` binary, guard it with `@pytest.mark.skipif(shutil.which("solc") is None, ...)` so it runs locally (confirmed available: solc 0.8.30, slither 0.11.3) without being required in CI.
- Follow existing test fixture conventions in `tests/conftest.py` (`temp_cwd`, `sample_contract`, `fake_slither_findings`) rather than inventing new ones.
- No existing tested CLI/API output shape changes — `fix` currently has zero test coverage, so this is new contract, not a breaking change.

---

### Task 1: `VerifyResult` + finding-matching key

**Files:**
- Create: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Produces: `VerifyResult` dataclass with fields `verdict: Literal["VERIFIED", "REGRESSED", "FAILED", "UNVERIFIED"]`, `diff: str`, `attempts: int`, `detail: str`, `degraded_reason: str | None = None`, `new_findings: list[dict] = field(default_factory=list)`, `patched_source: str | None = None`.
- Produces: `_finding_key(finding: dict) -> tuple` — `(rule_id, function)` or `(rule_id,)` if function is missing.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fix.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aura.core.fix'` (or `ImportError`)

- [ ] **Step 3: Write minimal implementation**

Create `src/aura/core/fix.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class VerifyResult:
    verdict: Literal["VERIFIED", "REGRESSED", "FAILED", "UNVERIFIED"]
    diff: str
    attempts: int
    detail: str
    degraded_reason: str | None = None
    new_findings: list[dict] = field(default_factory=list)
    patched_source: str | None = None


def _finding_key(finding: dict) -> tuple:
    rule_id = finding.get("rule_id")
    locations = finding.get("locations") or []
    function = locations[0].get("function") if locations else None
    if function is None:
        return (rule_id,)
    return (rule_id, function)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add VerifyResult and finding-matching key"
```

---

### Task 2: `_compile_with_solc`

**Files:**
- Modify: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `_compile_with_solc(file_path: Path) -> tuple[bool, str]` — `(success, stderr_or_empty)`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fix.py`:

```python
import shutil

import pytest


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
    f.write_text(
        "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\ncontract Valid {}\n"
    )
    ok, err = fix._compile_with_solc(f)
    assert ok is True
    assert err == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v -k compile_with_solc`
Expected: FAIL with `AttributeError: module 'aura.core.fix' has no attribute '_compile_with_solc'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/aura/core/fix.py` (add `import subprocess` and `from pathlib import Path` to the top of the file):

```python
def _compile_with_solc(file_path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["solc", "--bin", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return False, "solc not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "solc compile timed out"
    if proc.returncode != 0:
        return False, proc.stderr.strip()
    return True, ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v -k compile_with_solc`
Expected: PASS (3 tests, or 2 passed + 1 skipped if solc is unavailable in this environment)

- [ ] **Step 5: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add solc compile check"
```

---

### Task 3: `_run_git_apply`

**Files:**
- Modify: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Produces: `_run_git_apply(workdir: Path, diff_text: str) -> tuple[bool, str]` — writes `diff_text` to a temp patch file inside `workdir`, runs `git apply` there, returns `(success, stderr_or_empty)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fix.py`:

```python
import subprocess as sp


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v -k run_git_apply`
Expected: FAIL with `AttributeError: module 'aura.core.fix' has no attribute '_run_git_apply'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/aura/core/fix.py`:

```python
def _run_git_apply(workdir: Path, diff_text: str) -> tuple[bool, str]:
    patch_file = workdir / ".aura_fix.patch"
    patch_file.write_text(diff_text, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["git", "apply", "--unsafe-paths", str(patch_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
        )
    finally:
        patch_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        return False, proc.stderr.strip()
    return True, ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v -k run_git_apply`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add git apply helper"
```

---

### Task 4: `generate_fix_diff` (moved + extended prompt logic)

**Files:**
- Modify: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Consumes: `build_llm_remediation_prompt` from `aura.core.explain` (existing, unchanged signature: `build_llm_remediation_prompt(findings: Iterable[dict], max_items: int = 3) -> str`)
- Produces: `generate_fix_diff(finding: dict, source_text: str, rule: str, target: str, *, llm, error_context: str | None = None) -> str`. `llm` is any object with a `.complete(prompt: str) -> str` method (matches `aura.core.llm.LLM`) — accepted as a parameter (not constructed internally) so tests can inject a fake.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fix.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v -k generate_fix_diff`
Expected: FAIL with `AttributeError: module 'aura.core.fix' has no attribute 'generate_fix_diff'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/aura/core/fix.py` (add `from aura.core.explain import build_llm_remediation_prompt` to imports):

```python
def generate_fix_diff(
    finding: dict,
    source_text: str,
    rule: str,
    target: str,
    *,
    llm,
    error_context: str | None = None,
) -> str:
    base_prompt = build_llm_remediation_prompt([finding], max_items=1)

    error_block = ""
    if error_context:
        error_block = (
            "\nThe previous attempt FAILED verification with this error:\n"
            f"{error_context}\n"
            "Produce a corrected patch that avoids this problem.\n\n"
        )

    fix_prompt = (
        "You are generating a git patch for a pull request.\n"
        "Return ONLY a unified diff that can be applied with `git apply`.\n\n"
        "STRICT RULES:\n"
        "RULE-SPECIFIC CONSTRAINTS:"
        "- If RULE is 'reentrancy-eth': you MUST apply checks-effects-interactions."
        "Update balances or state BEFORE any external call."
        "Do NOT add comments instead of code."
        "- If RULE is 'tx-origin': replace tx.origin with msg.sender for authorization."
        "- If RULE is 'arbitrary-send-eth': restrict ETH transfer to owner (or authorized address),"
        "NOT msg.sender."
        "- Output ONLY the unified diff.\n"
        "- No explanations, no markdown, no backticks.\n"
        "- Output must start with '---' and '+++'.\n"
        "- Prefer minimal edits.\n"
        "- If no safe fix is possible, output a single line starting with '# '.\n\n"
        f"TARGET FILE: {target}\n"
        f"RULE TO FIX: {rule}\n\n"
        f"{error_block}"
        "FILE CONTENTS:\n"
        "-----BEGIN FILE-----\n"
        f"{source_text}\n"
        "-----END FILE-----\n\n"
        "NOW PRODUCE THE PATCH.\n\n" + base_prompt
    )
    return llm.complete(fix_prompt).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v -k generate_fix_diff`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add generate_fix_diff with retry error context"
```

---

### Task 5: `verify_fix` (single-attempt verification)

**Files:**
- Modify: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Consumes: `_finding_key`, `_compile_with_solc`, `_run_git_apply` (Tasks 1–3); `SlitherAnalyzer` from `aura.core.analyzers.slither_adapter` (existing, `SlitherAnalyzer().run(target: str) -> list[dict]`)
- Produces: `verify_fix(target_path: str, diff_text: str, original_finding: dict, original_findings: list[dict], *, solc_available: bool, analyzer_available: bool) -> VerifyResult`. Note: this function does not set `attempts` (always leaves it `0`) — the caller (`verify_fix_loop`, Task 6) sets it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fix.py`:

```python
import difflib


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
        "locations": [
            {"file": "contracts/ReentrancyDemo.sol", "line": 11, "function": "withdraw"}
        ],
    }


def _original_findings():
    return [_original_finding()]


def test_verify_fix_verified(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_findings
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


def test_verify_fix_regressed_on_new_finding(
    monkeypatch, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    fixed_plus_new = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"] + [
        {
            "rule_id": "unchecked-transfer",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 20, "function": "withdraw"}
            ],
        }
    ]
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_plus_new
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v -k verify_fix and not verify_fix_loop`
Expected: FAIL with `AttributeError: module 'aura.core.fix' has no attribute 'verify_fix'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/aura/core/fix.py` (add `import shutil`, `import tempfile` to imports, and `from aura.core.analyzers.slither_adapter import SlitherAnalyzer`):

```python
def verify_fix(
    target_path: str,
    diff_text: str,
    original_finding: dict,
    original_findings: list[dict],
    *,
    solc_available: bool,
    analyzer_available: bool,
) -> VerifyResult:
    workdir = Path(tempfile.mkdtemp(prefix="aura-fix-"))
    try:
        rel_path = Path(target_path)
        dest = workdir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        original_source = Path(target_path).read_text(encoding="utf-8", errors="ignore")
        dest.write_text(original_source, encoding="utf-8")

        subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)

        applied, apply_err = _run_git_apply(workdir, diff_text)
        if not applied:
            return VerifyResult(
                verdict="FAILED",
                diff=diff_text,
                attempts=0,
                detail=f"patch did not apply: {apply_err}",
            )

        patched_source = dest.read_text(encoding="utf-8", errors="ignore")

        if not solc_available:
            return VerifyResult(
                verdict="UNVERIFIED",
                diff=diff_text,
                attempts=0,
                detail="patch applied; compile/re-analysis skipped (solc not found)",
                degraded_reason="solc not found on PATH",
                patched_source=patched_source,
            )

        compiled, compile_err = _compile_with_solc(dest)
        if not compiled:
            return VerifyResult(
                verdict="FAILED",
                diff=diff_text,
                attempts=0,
                detail=f"patched file does not compile: {compile_err}",
            )

        if not analyzer_available:
            return VerifyResult(
                verdict="UNVERIFIED",
                diff=diff_text,
                attempts=0,
                detail="patch applied and compiles; re-analysis skipped (analyzer not found)",
                degraded_reason="slither (analyzer) not found on PATH",
                patched_source=patched_source,
            )

        patched_findings = SlitherAnalyzer().run(str(dest))

        target_key = _finding_key(original_finding)
        original_keys = {_finding_key(f) for f in original_findings}
        patched_keys = [_finding_key(f) for f in patched_findings]

        target_gone = target_key not in patched_keys
        new_findings = [
            f for f, k in zip(patched_findings, patched_keys, strict=True) if k not in original_keys
        ]

        if target_gone and not new_findings:
            return VerifyResult(
                verdict="VERIFIED",
                diff=diff_text,
                attempts=0,
                detail="target finding resolved; no new findings introduced",
                patched_source=patched_source,
            )
        if target_gone and new_findings:
            return VerifyResult(
                verdict="REGRESSED",
                diff=diff_text,
                attempts=0,
                detail=f"target finding resolved but {len(new_findings)} new finding(s) introduced",
                new_findings=new_findings,
                patched_source=patched_source,
            )
        return VerifyResult(
            verdict="FAILED",
            diff=diff_text,
            attempts=0,
            detail="target finding is still present after applying the patch",
            patched_source=patched_source,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v -k verify_fix and not verify_fix_loop`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add verify_fix single-attempt verification"
```

---

### Task 6: `verify_fix_loop` (retry orchestration)

**Files:**
- Modify: `src/aura/core/fix.py`
- Test: `tests/test_fix.py`

**Interfaces:**
- Consumes: `generate_fix_diff` (Task 4), `verify_fix` (Task 5)
- Produces: `verify_fix_loop(target_path: str, original_finding: dict, original_findings: list[dict], rule: str, *, llm, max_retries: int = 3) -> VerifyResult`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fix.py`:

```python
def test_solc_available_reflects_which(monkeypatch):
    monkeypatch.setattr(fix.shutil, "which", lambda name: "/usr/bin/solc" if name == "solc" else None)
    assert fix._solc_available() is True

    monkeypatch.setattr(fix.shutil, "which", lambda name: None)
    assert fix._solc_available() is False


def test_analyzer_available_reflects_which(monkeypatch):
    monkeypatch.setattr(fix.shutil, "which", lambda name: "/usr/bin/slither" if name == "slither" else None)
    assert fix._analyzer_available() is True

    monkeypatch.setattr(fix.shutil, "which", lambda name: None)
    assert fix._analyzer_available() is False


def test_verify_fix_loop_retries_and_succeeds(monkeypatch, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    fixed_findings = [f for f in fake_slither_findings if f["rule_id"] != "reentrancy-eth"]
    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fixed_findings
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
        _original_findings(),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fix.py -v -k verify_fix_loop`
Expected: FAIL with `AttributeError: module 'aura.core.fix' has no attribute 'verify_fix_loop'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/aura/core/fix.py`:

```python
def _solc_available() -> bool:
    return shutil.which("solc") is not None


def _analyzer_available() -> bool:
    return shutil.which("slither") is not None


def verify_fix_loop(
    target_path: str,
    original_finding: dict,
    original_findings: list[dict],
    rule: str,
    *,
    llm,
    max_retries: int = 3,
) -> VerifyResult:
    solc_available = _solc_available()
    analyzer_available = _analyzer_available()
    source_text = Path(target_path).read_text(encoding="utf-8", errors="ignore")

    error_context: str | None = None
    result: VerifyResult | None = None

    for attempt in range(1, max_retries + 1):
        diff_text = generate_fix_diff(
            original_finding,
            source_text,
            rule,
            target_path,
            llm=llm,
            error_context=error_context,
        )

        if diff_text.strip().startswith("#"):
            return VerifyResult(
                verdict="FAILED",
                diff=diff_text,
                attempts=attempt,
                detail="LLM reported no safe fix is available",
            )

        result = verify_fix(
            target_path,
            diff_text,
            original_finding,
            original_findings,
            solc_available=solc_available,
            analyzer_available=analyzer_available,
        )
        result.attempts = attempt

        if result.verdict in ("VERIFIED", "UNVERIFIED"):
            return result

        error_context = result.detail

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fix.py -v -k "verify_fix_loop or _available"`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full new test file**

Run: `pytest tests/test_fix.py -v`
Expected: PASS (all tests from Tasks 1–6)

- [ ] **Step 6: Commit**

```bash
git add src/aura/core/fix.py tests/test_fix.py
git commit -m "feat(fix): add verify_fix_loop retry orchestration"
```

---

### Task 7: Wire into `cli.py`'s `fix` command

**Files:**
- Modify: `src/aura/cli.py:400-483` (the existing `fix_cmd` function and its imports)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `verify_fix_loop`, `VerifyResult` from `aura.core.fix` (Task 6)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
import json

from aura.core import fix as fix_module
import aura.cli as cli_module


def test_fix_cmd_prints_verdict_and_does_not_write_without_write_flag(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    original_content = sample_contract.read_text()
    runner = CliRunner()
    result = runner.invoke(app, ["fix", str(sample_contract), "--rule", "reentrancy-eth"])

    assert result.exit_code == 0
    assert "Verdict: VERIFIED" in result.stdout
    assert sample_contract.read_text() == original_content


def test_fix_cmd_write_applies_patched_source_on_verified(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    runner = CliRunner()
    result = runner.invoke(
        app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--write"]
    )

    assert result.exit_code == 0
    assert "Wrote verified fix" in result.stdout
    assert sample_contract.read_text() == "contract Patched {}"


def test_fix_cmd_write_refuses_when_not_verified(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="FAILED",
        diff="--- a/x\n+++ b/x\n",
        attempts=3,
        detail="target finding is still present after applying the patch",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    original_content = sample_contract.read_text()
    runner = CliRunner()
    result = runner.invoke(
        app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--write"]
    )

    assert result.exit_code == 0
    assert "Refusing to write" in result.stdout
    assert sample_contract.read_text() == original_content


def test_fix_cmd_json_output(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    runner = CliRunner()
    result = runner.invoke(
        app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "VERIFIED"
    assert payload["attempts"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k fix_cmd`
Expected: FAIL — `verify_fix_loop` is not yet imported/used in `cli.py`, so monkeypatching `cli_module.verify_fix_loop` raises `AttributeError`, or the printed output doesn't match (`fix_cmd` doesn't yet print "Verdict: ..." text)

- [ ] **Step 3: Modify `cli.py`**

Add to the imports at the top of `src/aura/cli.py` (after the existing `from aura.core.llm import LLM` line):

```python
from aura.core.fix import verify_fix_loop
```

Replace the entire existing `fix_cmd` function (from `@app.command("fix")` through the final `typer.echo(out)`, i.e. `src/aura/cli.py:400-483` as currently written) with:

```python
@app.command("fix")
def fix_cmd(
    target: str,
    rule: str = typer.Option(
        "",
        "--rule",
        help="Rule ID to fix (run once without --rule to list available rules).",
    ),
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used for persistence",
    ),
    max_items: int = typer.Option(
        10,
        "--max-items",
        "-n",
        min=1,
        help="How many findings to scan when listing rules.",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply the fix to the target file. Only writes when the verdict is VERIFIED.",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        min=1,
        help="Maximum verification attempts before giving up.",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Output the verification result as JSON instead of text.",
    ),
) -> None:
    """
    Generate and verify a PR-ready remediation diff for ONE specific finding rule.

    The diff is applied in an isolated workspace, compiled, and re-analyzed
    before being presented — a VERIFIED verdict means the target finding is
    confirmed gone with no new findings introduced.

    Usage:
    - List rules:
        aura fix <target>
    - Fix + verify one rule:
        aura fix <target> --rule <rule_id>
    - Fix, verify, and apply to the file:
        aura fix <target> --rule <rule_id> --write
    """
    res = run_analysis(target, project_name=project)
    findings = res.get("findings", [])

    if not findings:
        typer.echo("No issues detected. Nothing to fix.")
        return

    if not rule:
        seen = set()
        rules = []
        for f in findings:
            rid = str(f.get("rule_id") or f.get("category") or "").strip()
            if rid and rid not in seen:
                seen.add(rid)
                rules.append(rid)
            if len(rules) >= max_items:
                break

        typer.echo("Available rules for this target:")
        for r in rules:
            typer.echo(f"- {r}")
        typer.echo("\nRe-run with: aura fix <target> --rule <rule_id>")
        return

    match = None
    for f in findings:
        if str(f.get("rule_id") or "").strip() == rule:
            match = f
            break

    if match is None:
        typer.echo(f"No finding found for rule='{rule}'.")
        return

    llm = LLM()
    result = verify_fix_loop(
        target, match, findings, rule, llm=llm, max_retries=max_retries
    )

    if json_out:
        payload = {
            "verdict": result.verdict,
            "attempts": result.attempts,
            "detail": result.detail,
            "degraded_reason": result.degraded_reason,
            "diff": result.diff,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"Verdict: {result.verdict} (attempt {result.attempts}/{max_retries})")
        typer.echo(result.detail)
        typer.echo("")
        typer.echo(result.diff)

    if write:
        if result.verdict == "VERIFIED" and result.patched_source is not None:
            Path(target).write_text(result.patched_source, encoding="utf-8")
            typer.echo(f"\nWrote verified fix to {target}")
        else:
            typer.echo(f"\nRefusing to write: verdict is {result.verdict}, not VERIFIED.")
```

Note: this removes the old direct `build_llm_remediation_prompt(...)` / raw `fix_prompt` / `llm.complete(fix_prompt)` calls from `fix_cmd` entirely — that logic now lives in `generate_fix_diff` (Task 4). `build_llm_remediation_prompt` stays imported in `cli.py` because `explain_cmd`/`explain_llm_cmd` still use it directly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v -k fix_cmd`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: PASS, no regressions in any existing test

- [ ] **Step 6: Lint check**

Run: `ruff check . && black --check . && isort --check-only .`
Expected: clean (matches CI's lint steps in `.github/workflows/ci.yml`)

- [ ] **Step 7: Commit**

```bash
git add src/aura/cli.py tests/test_cli.py
git commit -m "feat(cli): wire verified-fix loop into 'aura fix', add --write/--json"
```

---

### Task 8: Update phase doc status

**Files:**
- Modify: `docs/phases/phase-1.md`

- [ ] **Step 1: Mark phase 1 as done**

Change the `**Status:**` line at the top of `docs/phases/phase-1.md` from
`planned (next up)` to `done (2026-07-25)`.

- [ ] **Step 2: Commit**

```bash
git add docs/phases/phase-1.md
git commit -m "docs: mark phase 1 (verified fix loop) as done"
```

---

## After all tasks

This branch should be pushed and opened as a PR against `main` (which is
protected and requires the `test` CI check to pass — see the workflow
scaffolding session from 2026-07-24). Once CI is green, squash-merge and
delete the branch, matching how PR #25 was handled.
