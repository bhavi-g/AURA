from aura.core.analyzers import mythril_adapter, slither_adapter
from aura.core.pipeline import run_analysis


def test_pipeline_handles_empty_findings(monkeypatch, temp_cwd, sample_contract):
    monkeypatch.setattr(slither_adapter.SlitherAnalyzer, "run", lambda self, target: [])
    monkeypatch.setattr(mythril_adapter.MythrilAnalyzer, "run", lambda self, target: [])

    result = run_analysis(str(sample_contract), "default")
    assert result["score"] == 0
    assert result["n_findings"] == 0
    # reports still produced
    assert (temp_cwd / "reports" / "summary.json").is_file()
    assert (temp_cwd / "reports" / "summary.md").is_file()
