import json
from unittest.mock import patch

from action.scripts.comment import DISCLAIMER, MARKER, render_comment
from action.scripts.run_gate import load_findings, read_changed_files


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


def test_load_findings_reads_the_analyze_json_payload(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"findings": [{"rule_id": "a"}], "score": 4.2}))
    findings, score = load_findings(path)
    assert [f["rule_id"] for f in findings] == ["a"]
    assert score == 4.2


def test_load_findings_tolerates_a_missing_file(tmp_path):
    findings, score = load_findings(tmp_path / "nope.json")
    assert findings == []
    assert score == 0


def test_load_findings_tolerates_malformed_json(tmp_path):
    path = tmp_path / "f.json"
    path.write_text("not json{")
    assert load_findings(path) == ([], 0)


def test_read_changed_files_strips_blank_lines(tmp_path):
    path = tmp_path / "changed.txt"
    path.write_text("contracts/A.sol\n\ncontracts/B.sol\n")
    assert read_changed_files(path) == ["contracts/A.sol", "contracts/B.sol"]


def test_read_changed_files_returns_empty_for_a_missing_file(tmp_path):
    assert read_changed_files(tmp_path / "nope.txt") == []


def test_load_findings_tolerates_valid_json_that_is_not_a_dict(tmp_path):
    path = tmp_path / "f.json"
    path.write_text("[1, 2, 3]")
    assert load_findings(path) == ([], 0)
    path.write_text('"string"')
    assert load_findings(path) == ([], 0)
    path.write_text("42")
    assert load_findings(path) == ([], 0)
    path.write_text("null")
    assert load_findings(path) == ([], 0)


def test_run_comment_main_returns_zero_when_not_a_pr(monkeypatch):
    from action.scripts.run_comment import main

    monkeypatch.setenv("AURA_PR_NUMBER", "")
    assert main() == 0


def test_run_comment_main_returns_zero_with_non_dict_findings_json(tmp_path, monkeypatch):
    from action.scripts.run_comment import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text("[1, 2, 3]")
    monkeypatch.setenv("AURA_PR_NUMBER", "42")
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_REPO", "owner/repo")
    monkeypatch.setenv("AURA_COMMENT_BODY_PATH", str(tmp_path / "comment.md"))

    with patch(
        "action.scripts.run_comment.upsert_pr_comment",
        return_value="created",
    ):
        result = main()
        assert result == 0


def test_run_comment_main_returns_zero_when_upsert_fails(tmp_path, monkeypatch):
    from action.scripts.ghcli import CommandError
    from action.scripts.run_comment import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps({"findings": [], "score": 0}))
    monkeypatch.setenv("AURA_PR_NUMBER", "42")
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_REPO", "owner/repo")

    with patch(
        "action.scripts.run_comment.upsert_pr_comment",
        side_effect=CommandError("test error"),
    ):
        result = main()
        assert result == 0


def test_run_comment_main_shows_error_gate_on_invalid_threshold(tmp_path, monkeypatch):
    from action.scripts.run_comment import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps({"findings": [], "score": 0}))
    monkeypatch.setenv("AURA_PR_NUMBER", "42")
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_REPO", "owner/repo")
    monkeypatch.setenv("AURA_FAIL_ON", "invalid-threshold")

    captured_body = None

    def capture_upsert(repo, pr, body, **kwargs):
        nonlocal captured_body
        captured_body = body
        return "created"

    with patch(
        "action.scripts.run_comment.upsert_pr_comment",
        side_effect=capture_upsert,
    ):
        result = main()
        assert result == 0
        assert "unknown" in captured_body


def test_run_gate_main_returns_zero_when_no_violations(tmp_path, monkeypatch):
    from action.scripts.run_gate import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps({"findings": [], "score": 0}))
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_FAIL_ON", "high")

    result = main()
    assert result == 0


def test_run_gate_main_returns_one_on_violations(tmp_path, monkeypatch):
    from action.scripts.run_gate import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "rule_id": "reentrancy",
                        "severity": "HIGH",
                        "locations": [{"file": "A.sol", "line": 1}],
                    }
                ],
                "score": 5.0,
            }
        )
    )
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_FAIL_ON", "high")

    result = main()
    assert result == 1


def test_run_gate_main_returns_one_on_unknown_threshold(tmp_path, monkeypatch):
    from action.scripts.run_gate import main

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps({"findings": [], "score": 0}))
    monkeypatch.setenv("AURA_FINDINGS_JSON", str(findings_file))
    monkeypatch.setenv("AURA_FAIL_ON", "invalid-threshold")

    result = main()
    assert result == 1
