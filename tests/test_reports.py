from pathlib import Path

from aura.core.reporting.json_report import write_json
from aura.core.reporting.md_report import write_md


def _fake_findings():
    return [
        {
            "tool": "slither",
            "rule_id": "reentrancy-eth",
            "title": "reentrancy-eth",
            "description": "Reentrancy in withdraw()",
            "severity": "HIGH",
            "confidence": "MEDIUM",
            "category": "reentrancy-eth",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 11, "function": "withdraw"}
            ],
            "references": [],
            "raw": {},
            "score": 5.1,
        },
        {
            "tool": "slither",
            "rule_id": "low-level-calls",
            "title": "low-level-calls",
            "description": "low-level call",
            "severity": "LOW",
            "confidence": "HIGH",
            "category": "low-level-calls",
            "locations": [
                {"file": "contracts/ReentrancyDemo.sol", "line": 14, "function": "withdraw"}
            ],
            "references": [],
            "raw": {},
            "score": 1.0,
        },
    ]


def test_report_writers_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    findings = _fake_findings()
    score = 6.1

    j = write_json(findings, score)
    m = write_md(findings, score)

    jp = Path(j)
    mp = Path(m)
    assert jp.is_file() and mp.is_file()

    data = jp.read_text()
    assert '"score": 6.1' in data
    assert '"findings"' in data

    md = mp.read_text()
    assert md.splitlines()[0].startswith("# Aura Analysis Summary")
    # table header is present
    assert "| Rule | Severity | Score | Location |" in md
