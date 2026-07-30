# src/aura/core/llm.py

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

try:
    # OpenAI client is optional at import time. If it's not installed, we
    # fall back to a dummy LLM.
    from openai import AsyncOpenAI  # type: ignore
except ImportError:  # package not installed
    AsyncOpenAI = None  # type: ignore[assignment]


@dataclass
class LLMConfig:
    """
    Configuration for the LLM client.

    `model` defaults to None: each backend supplies its own provider-specific
    default when no explicit model is requested.
    """

    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 512


class _StubBackend:
    """Deterministic fallback used when no real provider is configured."""

    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        preview = prompt.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "..."
        return (
            "[LLM STUB] No real LLM configured "
            "(missing API key or provider package for the selected provider).\n"
            f"Prompt preview: {preview}"
        )


class _OpenAIBackend:
    """Wraps AsyncOpenAI. Request shape matches the pre-refactor implementation exactly."""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, client: AsyncOpenAI, config: LLMConfig) -> None:
        self._client = client
        self._config = config

    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model or self._config.model or self.DEFAULT_MODEL,
            temperature=self._config.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self._config.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


def _make_openai_backend(config: LLMConfig) -> _OpenAIBackend | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if AsyncOpenAI is None or not api_key:
        return None
    return _OpenAIBackend(AsyncOpenAI(api_key=api_key), config)


class LLM:
    """
    Thin facade over a resolved provider backend.

    Only one real backend (OpenAI) exists at this point in the codebase's
    history; provider selection (LLMConfig.provider / AURA_LLM_PROVIDER) is
    introduced in a later change once a second backend exists to select
    between. For now, resolution is simply: try OpenAI if available, else
    the deterministic stub.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._backend = self._resolve_backend()

    def _resolve_backend(self):
        return _make_openai_backend(self.config) or _StubBackend()

    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return await self._backend.acomplete(
            prompt, model=model, temperature=temperature, max_tokens=max_tokens
        )

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return asyncio.run(
            self.acomplete(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
        )
