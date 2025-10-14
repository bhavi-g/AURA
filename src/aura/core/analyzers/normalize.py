from typing import Literal, TypedDict

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]


class Location(TypedDict, total=False):
    file: str
    line: int
    function: str | None


class Finding(TypedDict):
    tool: Literal["slither", "mythril"]
    rule_id: str
    title: str
    description: str
    severity: Severity
    confidence: Confidence
    category: str
    locations: list[Location]
    references: list[str]
    raw: dict
