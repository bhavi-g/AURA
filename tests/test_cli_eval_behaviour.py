import json
from pathlib import Path

from typer.testing import CliRunner

from aura.cli import app

runner = CliRunner()


def _write_minimal_sarif(p: Path, fname="A.sol", line=2, rule="solc-version"):
    sarif = {
        "runs": [
            {
                "tool": {"driver": {"rules": [{"id": rule}]}},
                "results": [
                    {
                        "ruleId": rule,
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": fname},
                                    "region": {"startLine": line},
                                }
                            }
                        ],
                    }
                ],
            }
        ]
    }
    p.write_text(json.dumps(sarif))


def test_eval_autogolden_and_index_append(tmp_path: Path, monkeypatch) -> None:
    # Work in an isolated CWD
    monkeypatch.chdir(tmp_path)

    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    # write current analyzer SARIF
    current = reports / "summary.sarif"
    _write_minimal_sarif(current)

    # golden will be missing initially -> CLI should auto-create it
    result = runner.invoke(app, ["eval"])
    assert result.exit_code == 0

    # golden created?
    golden = reports / "golden" / "summary.sarif"
    assert golden.exists()

    # metrics created and contain by_rule
    metrics = json.loads((reports / "metrics.json").read_text())
    assert metrics["tp"] == 1 and metrics["fp"] == 0 and metrics["fn"] == 0
    assert "by_rule" in metrics and "solc-version" in metrics["by_rule"]

    # index.md appended
    idx = reports / "index.md"
    txt = idx.read_text()
    assert "### Evaluation" in txt
    assert "`solc-version`" in txt

    # run again -> should append another Evaluation section
    result2 = runner.invoke(app, ["eval"])
    assert result2.exit_code == 0
    txt2 = idx.read_text()
    assert txt2.count("### Evaluation") == 2
