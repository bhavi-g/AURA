# src/aura/core/llm.py

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

try:
    # OpenAI client is optional. If it's not installed, we fall back to a dummy LLM.
    from openai import AsyncOpenAI  # type: ignore
except ImportError:  # package not installed yet
    AsyncOpenAI = None  # type: ignore[assignment]


@dataclass
class LLMConfig:
    """
    Configuration for the LLM client.

    The defaults are chosen for cheap/small models once you enable OpenAI.
    """

    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 512


class LLM:
    """
    Thin wrapper around an LLM.

    - If OpenAI is installed *and* OPENAI_API_KEY is set → use real OpenAI.
    - Otherwise → use a dummy implementation that just echoes a placeholder.

    This lets you develop AURA without paying anything right now.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
    ) -> None:
        self.config = config or LLMConfig()
        self._client: AsyncOpenAI | None = None
        self._use_dummy: bool = True

        api_key = os.getenv("OPENAI_API_KEY")

        # Only enable real OpenAI if:
        # - the package is installed, and
        # - the API key is present
        if AsyncOpenAI is not None and api_key:
            self._client = AsyncOpenAI(api_key=api_key)  # type: ignore[call-arg]
            self._use_dummy = False

    # -----------------------------
    # Public API
    # -----------------------------
    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Async completion interface.

        If no real LLM is configured, returns a deterministic dummy response so that
        the rest of the pipeline can still run in development.
        """
        if self._use_dummy or self._client is None:
            return self._dummy_response(prompt)

        response = await self._client.chat.completions.create(
            model=model or self.config.model,
            temperature=self.config.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # OpenAI v1: content is on message.content
        return response.choices[0].message.content or ""

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Sync wrapper for CLI / non-async code.

        Internally just runs `acomplete` in a fresh event loop.
        """
        return asyncio.run(
            self.acomplete(
                prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _dummy_response(self, prompt: str) -> str:
        """
        Fallback when there is no real LLM configured.

        This is intentionally simple and cheap; it just makes the rest of the
        system usable in development without any API keys or payments.
        """
        preview = prompt.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "..."
        return (
            "[LLM STUB] No real LLM configured "
            "(missing OPENAI_API_KEY or openai package).\n"
            f"Prompt preview: {preview}"
        )
