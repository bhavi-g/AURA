import json
from pathlib import Path

from src.aura.core.reporting.aggregate import write_index_md


def test_write_index_md_tmp(tmp_path: Path):
    findings = json.loads(Path("tests/fixtures/slither_parsed_min.json").read_text())
    out = tmp_path / "index.md"
    p = write_index_md(findings, score=7.5, out_path=str(out))
    text = Path(p).read_text()
    assert "AURA Report (Week 3)" in text
    assert "Findings: **3**" in text
    assert "Score: **7.50**" in text
    assert "| `reentrancy-eth` | 1 |" in text
