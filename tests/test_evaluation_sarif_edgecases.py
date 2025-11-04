import json
from pathlib import Path

from aura.core.evaluation.evaluator import evaluate


def _mk(path: Path, runs, name: str) -> Path:
    p = path / name
    p.write_text(json.dumps({"runs": runs}))
    return p


def test_parses_ruleId_or_rule_dot_id(tmp_path: Path) -> None:
    gold = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "tx-origin"}]}},
                "results": [
                    {
                        "ruleId": "tx-origin",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "X.sol"},
                                    "region": {"startLine": 10},
                                }
                            }
                        ],
                    },
                ],
            },
        ],
        name="gold.sarif",
    )
    # Variant: missing ruleId, but has rule.id
    pred = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "tx-origin"}]}},
                "results": [
                    {
                        "rule": {"id": "tx-origin"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "X.sol"},
                                    "region": {"startLine": 10},
                                }
                            }
                        ],
                    },
                ],
            },
        ],
        name="pred.sarif",
    )
    m = evaluate(pred, gold)
    assert m["tp"] == 1 and m["fp"] == 0 and m["fn"] == 0


def test_missing_startLine_defaults_to_zero(tmp_path: Path) -> None:
    gold = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "solc-version"}]}},
                "results": [
                    {
                        "ruleId": "solc-version",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "File.sol"},
                                    "region": {"startLine": 0},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
        name="gold.sarif",
    )
    pred = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "solc-version"}]}},
                "results": [
                    {
                        "ruleId": "solc-version",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "File.sol"},
                                    "region": {},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
        name="pred.sarif",
    )
    m = evaluate(pred, gold)
    assert m["tp"] == 1 and m["fp"] == 0 and m["fn"] == 0


def test_uriBaseId_fallback_when_uri_absent(tmp_path: Path) -> None:
    gold = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "low-level-calls"}]}},
                "results": [
                    {
                        "ruleId": "low-level-calls",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uriBaseId": "SRC"},
                                    "region": {"startLine": 12},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
        name="gold.sarif",
    )
    pred = _mk(
        tmp_path,
        [
            {
                "tool": {"driver": {"rules": [{"id": "low-level-calls"}]}},
                "results": [
                    {
                        "ruleId": "low-level-calls",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uriBaseId": "SRC"},
                                    "region": {"startLine": 12},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
        name="pred.sarif",
    )
    m = evaluate(pred, gold)
    assert m["tp"] == 1 and m["fp"] == 0 and m["fn"] == 0
