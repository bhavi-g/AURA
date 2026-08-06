import pytest

from action.scripts.findings import (
    filter_by_files,
    finding_files,
    gate_violations,
    normalize_path,
    severity_counts,
    severity_rank,
)


def _finding(rule="reentrancy-eth", severity="HIGH", files=("contracts/A.sol",), line=11):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": rule,
        "locations": [{"file": f, "line": line} for f in files],
    }


def test_severity_rank_orders_severities():
    assert severity_rank("CRITICAL") > severity_rank("HIGH")
    assert severity_rank("HIGH") > severity_rank("MEDIUM")
    assert severity_rank("MEDIUM") > severity_rank("LOW")
    assert severity_rank("LOW") > severity_rank("INFO")


def test_severity_rank_is_case_insensitive_and_defaults_unknown_to_zero():
    assert severity_rank("high") == severity_rank("HIGH")
    assert severity_rank("nonsense") == 0
    assert severity_rank("") == 0
    assert severity_rank(None) == 0


def test_normalize_path_strips_prefixes_and_normalizes_separators():
    assert normalize_path("./contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("/contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("contracts\\A.sol") == "contracts/A.sol"
    assert normalize_path("contracts/../contracts/A.sol") == "contracts/A.sol"
    assert normalize_path("") == ""
    assert normalize_path(None) == ""


def test_finding_files_dedupes_and_normalizes():
    f = _finding(files=("./contracts/A.sol", "contracts/A.sol", "contracts/B.sol"))
    assert finding_files(f) == ["contracts/A.sol", "contracts/B.sol"]


def test_finding_files_handles_missing_locations():
    assert finding_files({"rule_id": "x"}) == []
    assert finding_files({"rule_id": "x", "locations": []}) == []


def test_filter_by_files_keeps_only_findings_touching_changed_files():
    a = _finding(rule="a", files=("contracts/A.sol",))
    b = _finding(rule="b", files=("contracts/B.sol",))
    kept = filter_by_files([a, b], ["./contracts/A.sol"])
    assert [f["rule_id"] for f in kept] == ["a"]


def test_filter_by_files_returns_empty_when_nothing_changed():
    assert filter_by_files([_finding()], []) == []


def test_severity_counts_counts_known_severities_only():
    findings = [
        _finding(severity="HIGH"),
        _finding(severity="HIGH"),
        _finding(severity="LOW"),
        _finding(severity="bogus"),
    ]
    counts = severity_counts(findings)
    assert counts["HIGH"] == 2
    assert counts["LOW"] == 1
    assert counts["CRITICAL"] == 0


def test_gate_violations_includes_findings_at_the_threshold_itself():
    """The boundary: `fail-on: high` must fail on a HIGH, not only on CRITICAL."""
    findings = [_finding(severity="HIGH"), _finding(severity="MEDIUM")]
    violations = gate_violations(findings, "high")
    assert len(violations) == 1
    assert violations[0]["severity"] == "HIGH"


def test_gate_violations_includes_severities_above_the_threshold():
    findings = [_finding(severity="CRITICAL")]
    assert len(gate_violations(findings, "high")) == 1


def test_gate_violations_disabled_by_none_and_empty():
    findings = [_finding(severity="CRITICAL")]
    assert gate_violations(findings, "none") == []
    assert gate_violations(findings, "") == []


def test_gate_violations_rejects_an_unknown_threshold():
    with pytest.raises(ValueError):
        gate_violations([], "extremely-bad")
