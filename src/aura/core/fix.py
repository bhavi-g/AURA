from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from aura.core.analyzers.slither_adapter import SlitherAnalyzer
from aura.core.explain import build_llm_remediation_prompt


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
        "RULE-SPECIFIC CONSTRAINTS:\n"
        "- If RULE is 'reentrancy-eth': you MUST apply checks-effects-interactions.\n"
        "Update balances or state BEFORE any external call.\n"
        "Do NOT add comments instead of code.\n"
        "- If RULE is 'tx-origin': replace tx.origin with msg.sender for authorization.\n"
        "- If RULE is 'arbitrary-send-eth': restrict ETH transfer to owner\n"
        "(or authorized address), not msg.sender.\n"
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
    diff_text = llm.complete(fix_prompt).strip()
    if diff_text and not diff_text.endswith("\n"):
        # `git apply` is sensitive to the trailing newline of the last diff
        # line matching the underlying file's line-ending state. Stripping
        # outer whitespace above removes a well-formed diff's final "\n"
        # whenever the patched file ends with a trailing newline (the
        # common case), which makes git apply reject it as a corrupt patch.
        # Restore a single trailing newline so a well-formed diff still
        # applies cleanly.
        diff_text += "\n"
    return diff_text


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
        if rel_path.is_absolute():
            # `git apply` (invoked by _run_git_apply with its default -p1 strip
            # level) resolves an absolute diff header by dropping just the
            # leading "/" and treating the remainder as relative to its cwd
            # (workdir). Mirror that here so the copy we create is exactly
            # where git apply will look, regardless of whether target_path is
            # absolute or repo-relative.
            rel_path = rel_path.relative_to(rel_path.anchor)
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
