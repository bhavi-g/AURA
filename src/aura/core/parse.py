from __future__ import annotations

from typing import Any


def parse_llm_findings(raw: Any) -> list[dict[str, Any]]:
    """Parse a model response into canonical AURA finding dicts.

    Week 5: placeholder implementation.

    - If `raw` is already a list of dicts, we assume they are
      valid finding dicts and pass them through.
    - Otherwise, we wrap the raw content as a single INFO finding
      so callers never crash on unexpected formats.
    """

    if isinstance(raw, list) and all(isinstance(x, dict) for x in raw):
        # already in (approximate) finding format
        return raw  # type: ignore[return-value]

    return [
        {
            "rule_id": "llm-generic",
            "severity": "INFO",
            "title": "LLM output (unparsed)",
            "description": str(raw),
            "locations": [],
        }
    ]
