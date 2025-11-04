import json
from pathlib import Path

from aura.core.evaluation.evaluator import evaluate


def _mk_sarif(path: Path, results, name: str) -> Path:
    p = path / name
    p.write_text(json.dumps({"runs": [{"results": results}]}))
    return p


def test_zero_division_safety(tmp_path: Path) -> None:
    gold = _mk_sarif(tmp_path, [], name="gold.sarif")  # no gold findings
    pred = _mk_sarif(tmp_path, [], name="pred.sarif")  # no predicted findings
    m = evaluate(pred, gold)
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0
