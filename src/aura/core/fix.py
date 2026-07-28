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
