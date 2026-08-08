from action.scripts.comment import DISCLAIMER, MARKER, render_comment


def _finding(rule="reentrancy-eth", severity="HIGH", title="Reentrancy", file="contracts/A.sol"):
    return {
        "rule_id": rule,
        "severity": severity,
        "title": title,
        "locations": [{"file": file, "line": 11}],
    }


def _render(**overrides):
    kwargs = {
        "all_findings": [_finding()],
        "changed_findings": [_finding()],
        "score": 12.5,
        "changed_files_ok": True,
        "gate_threshold": "high",
        "violations": [],
    }
    kwargs.update(overrides)
    return render_comment(**kwargs)


def test_comment_starts_with_the_marker_so_it_can_be_found_for_upsert():
    assert _render().startswith(MARKER)


def test_comment_includes_totals_and_score():
    body = _render(all_findings=[_finding(), _finding(rule="tx-origin")], score=31.0)
    assert "2 finding" in body
    assert "31.0" in body


def test_comment_lists_changed_file_findings_in_a_table():
    body = _render()
    assert "| Severity | Rule | Location | Title |" in body
    assert "`reentrancy-eth`" in body
    assert "`contracts/A.sol:11`" in body


def test_comment_orders_findings_by_severity_descending():
    low = _finding(rule="solc-version", severity="LOW")
    critical = _finding(rule="arbitrary-send-eth", severity="CRITICAL")
    body = _render(all_findings=[low, critical], changed_findings=[low, critical])
    assert body.index("arbitrary-send-eth") < body.index("solc-version")


def test_comment_escapes_pipes_in_titles_so_the_table_survives():
    body = _render(changed_findings=[_finding(title="a | b")])
    assert "a \\| b" in body


def test_comment_truncates_long_finding_lists():
    many = [_finding(rule=f"rule-{i}") for i in range(15)]
    body = _render(all_findings=many, changed_findings=many, max_rows=10)
    assert "and 5 more" in body


def test_comment_celebrates_a_clean_changed_file_set():
    body = _render(changed_findings=[])
    assert "No findings in the files this PR changes" in body


def test_comment_notes_when_changed_files_could_not_be_determined():
    body = _render(changed_files_ok=False)
    assert "Could not determine" in body


def test_comment_reports_a_passing_gate():
    body = _render(violations=[])
    assert "Severity gate" in body and "passed" in body


def test_comment_reports_a_failing_gate_with_a_count():
    body = _render(violations=[_finding(), _finding()])
    assert "failed" in body and "2 finding" in body


def test_comment_reports_a_disabled_gate():
    body = _render(gate_threshold="none")
    assert "disabled" in body


def test_comment_links_the_fix_pr_when_one_was_opened():
    body = _render(fix_pr_url="https://github.com/o/r/pull/9")
    assert "https://github.com/o/r/pull/9" in body


def test_comment_states_why_fixes_were_skipped():
    body = _render(fix_skip_reason="no LLM API key configured")
    assert "no LLM API key configured" in body


def test_comment_always_carries_the_not_an_audit_disclaimer():
    """docs/NEVER_DO.md: never present AURA output as an audit."""
    assert DISCLAIMER in _render()
    assert DISCLAIMER in _render(changed_findings=[], violations=[])
