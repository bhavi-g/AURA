import json

from typer.testing import CliRunner

import aura.cli as cli_module
from aura.cli import app
from aura.core import fix as fix_module


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


def test_fix_cmd_prints_verdict_and_does_not_write_without_write_flag(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    original_content = sample_contract.read_text()
    runner = CliRunner()
    result = runner.invoke(app, ["fix", str(sample_contract), "--rule", "reentrancy-eth"])

    assert result.exit_code == 0
    assert "Verdict: VERIFIED" in result.stdout
    assert sample_contract.read_text() == original_content


def test_fix_cmd_write_applies_patched_source_on_verified(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    runner = CliRunner()
    result = runner.invoke(
        app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--write"]
    )

    assert result.exit_code == 0
    assert "Wrote verified fix" in result.stdout
    assert sample_contract.read_text() == "contract Patched {}"


def test_fix_cmd_write_refuses_when_not_verified(
    monkeypatch, temp_cwd, sample_contract, fake_slither_findings
):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="FAILED",
        diff="--- a/x\n+++ b/x\n",
        attempts=3,
        detail="target finding is still present after applying the patch",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    original_content = sample_contract.read_text()
    runner = CliRunner()
    result = runner.invoke(
        app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--write"]
    )

    assert result.exit_code == 0
    assert "Refusing to write" in result.stdout
    assert sample_contract.read_text() == original_content


def test_fix_cmd_json_output(monkeypatch, temp_cwd, sample_contract, fake_slither_findings):
    from aura.core.analyzers import slither_adapter

    monkeypatch.setattr(
        slither_adapter.SlitherAnalyzer, "run", lambda self, target: fake_slither_findings
    )

    fake_result = fix_module.VerifyResult(
        verdict="VERIFIED",
        diff="--- a/x\n+++ b/x\n",
        attempts=1,
        detail="target finding resolved; no new findings introduced",
        patched_source="contract Patched {}",
    )
    monkeypatch.setattr(cli_module, "verify_fix_loop", lambda *a, **k: fake_result)

    runner = CliRunner()
    result = runner.invoke(app, ["fix", str(sample_contract), "--rule", "reentrancy-eth", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "VERIFIED"
    assert payload["attempts"] == 1
