from aura.core.explain import summarize_findings


def test_summarize_findings_empty_list():
    assert "No issues detected" in summarize_findings([])


def test_summarize_findings_handles_empty_description():
    findings = [
        {
            "rule_id": "reentrancy-eth",
            "severity": "HIGH",
            "score": 5.1,
            "title": "",
            "description": "",
        }
    ]

    summary = summarize_findings(findings)

    assert "reentrancy-eth" in summary


def test_summarize_findings_handles_missing_description():
    findings = [
        {
            "rule_id": "reentrancy-eth",
            "severity": "HIGH",
            "score": 5.1,
        }
    ]

    summary = summarize_findings(findings)

    assert "reentrancy-eth" in summary


def test_summarize_findings_uses_first_line_of_description_when_no_title():
    findings = [
        {
            "rule_id": "reentrancy-eth",
            "severity": "HIGH",
            "score": 5.1,
            "description": "External call before state update.\nMore details here...",
        }
    ]

    summary = summarize_findings(findings)

    assert "External call before state update." in summary
    assert "More details here" not in summary
