from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_precommit_config_present():
    cfg = ROOT / ".pre-commit-config.yaml"
    assert cfg.exists(), "missing .pre-commit-config.yaml"
    text = cfg.read_text()
    assert "ruff-pre-commit" in text and "black" in text


def test_editorconfig_present():
    path = ROOT / ".editorconfig"
    assert path.exists(), "missing .editorconfig"
    txt = path.read_text()
    assert "indent_style" in txt and "insert_final_newline" in txt


def test_vscode_settings_present():
    s = ROOT / ".vscode" / "settings.json"
    e = ROOT / ".vscode" / "extensions.json"
    assert s.exists(), "missing .vscode/settings.json"
    assert e.exists(), "missing .vscode/extensions.json"


def test_ci_workflow_present_and_basic_yaml():
    wf = ROOT / ".github" / "workflows" / "ci.yml"
    assert wf.exists(), "missing .github/workflows/ci.yml"
    data = yaml.safe_load(wf.read_text())
    assert "jobs" in data and "test" in data["jobs"]
    steps = data["jobs"]["test"]["steps"]
    joined = " ".join(str(s) for s in steps)
    assert "actions/checkout" in joined and "actions/setup-python" in joined
