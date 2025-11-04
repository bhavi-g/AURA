from __future__ import annotations

import json
import logging
from pathlib import Path

from src.aura.core.reporting.aggregate import load_parsed_and_score, write_index_md
from src.aura.core.reporting.sarif_report import write_sarif

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main():
    findings, score = load_parsed_and_score("reports")
    if not findings:
        logging.info("No findings to aggregate; run `python -m aura analyze ...` first.")
        return
    out_md = write_index_md(findings, score, "reports/index.md")
    write_sarif(findings, "reports/summary.sarif")
    logging.info("Wrote: %s and reports/summary.sarif", out_md)
    # keep summary.json consistent with score & count
    try:
        Path("reports/summary.json").write_text(
            json.dumps({"score": score, "count": len(findings)}, indent=2)
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
