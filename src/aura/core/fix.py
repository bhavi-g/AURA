from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
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
