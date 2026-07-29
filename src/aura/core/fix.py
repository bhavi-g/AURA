from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
