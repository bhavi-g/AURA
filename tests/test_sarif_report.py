import json
from pathlib import Path

from aura.core.reporting.sarif_report import write_sarif


def _finding(severity: str) -> dict:
    return {
        "rule_id": "reentrancy-eth",
        "severity": severity,
        "description": "Reentrancy in withdraw()",
        "score": 9.0,
        "tool": "slither",
        "locations": [{"file": "contracts/A.sol", "line": 11}],
    }


def test_critical_severity_maps_to_error_not_note(tmp_path):
    """CRITICAL is the highest AURA severity; it must not render as SARIF's
    lowest level ("note") in Code Scanning."""
    out_path = tmp_path / "out.sarif"
    write_sarif([_finding("CRITICAL")], out_path=str(out_path))
    payload = json.loads(Path(out_path).read_text())
    assert payload["runs"][0]["results"][0]["level"] == "error"


def test_high_severity_still_maps_to_error(tmp_path):
    out_path = tmp_path / "out.sarif"
    write_sarif([_finding("HIGH")], out_path=str(out_path))
    payload = json.loads(Path(out_path).read_text())
    assert payload["runs"][0]["results"][0]["level"] == "error"


def test_unknown_severity_falls_back_to_note(tmp_path):
    out_path = tmp_path / "out.sarif"
    write_sarif([_finding("WEIRD")], out_path=str(out_path))
    payload = json.loads(Path(out_path).read_text())
    assert payload["runs"][0]["results"][0]["level"] == "note"
