from pathlib import Path

from aura.core.pipeline import run_analysis


def test_pipeline_with_mocked_slither(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    # Mock SlitherAnalyzer.run to avoid external binary calls
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer,
        "run",
        lambda self, target: fake_slither_findings,
    )

    # Your pipeline requires (path, project_name)
    result = run_analysis(str(sample_contract), "default")

    assert result["score"] > 0
    assert result["n_findings"] == len(fake_slither_findings)

    # Reports written
    assert Path("reports/summary.json").is_file()
    assert Path("reports/summary.md").is_file()
