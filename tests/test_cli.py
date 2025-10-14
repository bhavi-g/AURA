from typer.testing import CliRunner

from aura.cli import app


def test_cli_analyze(monkeypatch, temp_cwd, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(sample_contract)])
    assert result.exit_code == 0
    assert "Findings:" in result.stdout
