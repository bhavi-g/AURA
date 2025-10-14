import json
import pathlib


def write_json(findings, score, out_path="reports/summary.json"):
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"score": score, "findings": findings}, indent=2))
    return str(p)
