import json
from pathlib import Path

from .metrics import Key, confusion, f1, precision, recall


def _sarif_to_keys(p: Path) -> set[Key]:
    d = json.loads(p.read_text())
    keys: set[Key] = set()
    for run in d.get("runs", []):
        rule_lookup: dict[str, str] = {}
        for r in (run.get("tool", {}) or {}).get("driver", {}).get("rules", []) or []:
            if r.get("id"):
                rule_lookup[r["id"]] = r["id"]
        for r in run.get("results", []) or []:
            rid = r.get("ruleId") or (r.get("rule", {}) or {}).get("id") or "unknown"
            for loc in r.get("locations", []) or []:
                phys = loc.get("physicalLocation", {}) or {}
                art = phys.get("artifactLocation", {}) or {}
                file = art.get("uri") or art.get("uriBaseId") or "unknown"
                region = phys.get("region", {}) or {}
                line = int(region.get("startLine") or 0)
                keys.add((file, line, rule_lookup.get(rid, rid)))
    return keys


def evaluate(report: Path, golden: Path) -> dict[str, float]:
    pred = _sarif_to_keys(report)
    gold = _sarif_to_keys(golden)
    c = confusion(pred, gold)
    p = precision(c.tp, c.fp)
    r = recall(c.tp, c.fn)
    f = f1(p, r)
    return {
        "tp": c.tp,
        "fp": c.fp,
        "fn": c.fn,
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f, 4),
        "pred_count": len(pred),
        "gold_count": len(gold),
    }
