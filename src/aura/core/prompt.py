from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AnalysisPrompt:
    """Container for an LLM analysis prompt (Week 5 scaffold).

    This does NOT call any model yet. It just standardizes the
    structure so a future analyzer can turn this into API calls.
    """

    contract_path: Path
    language: str = "solidity"
    extra_context: dict[str, Any] | None = None

    def to_messages(self) -> list[dict[str, str]]:
        """Return an OpenAI-style `messages` list."""

        system_msg = (
            "You are a smart-contract security assistant. "
            "Given a Solidity contract, you identify vulnerabilities and explain them."
        )

        user_msg = (
            "Analyze the following contract for security issues.\n\n"
            f"Contract path (on disk): {self.contract_path}\n"
            "Focus on reentrancy, overflow/underflow, access control, tx.origin, "
            "unchecked calls, and any other critical issues."
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
