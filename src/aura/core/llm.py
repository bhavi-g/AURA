# src/aura/core/llm.py

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Protocol

try:
    # OpenAI client is optional at import time. If it's not installed, we
    # fall back to a dummy LLM.
    from openai import AsyncOpenAI  # type: ignore
except ImportError:  # package not installed
    AsyncOpenAI = None  # type: ignore[assignment]

try:
    from anthropic import AsyncAnthropic  # type: ignore
except ImportError:  # package not installed
    AsyncAnthropic = None  # type: ignore[assignment]


@dataclass
class LLMConfig:
    """
    Configuration for the LLM client.

    `model` defaults to None: each backend supplies its own provider-specific
    default when no explicit model is requested. `provider` is an explicit
    override (mainly for tests); when unset, resolution falls back to the
    AURA_LLM_PROVIDER env var, then auto-detection.
    """

    provider: str | None = None
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 512


class _Backend(Protocol):
    """Structural contract shared by every LLM backend `LLM` can resolve to."""

    async def acomplete(
        self,
        prompt: str,
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str: ...


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


class _AnthropicBackend:
    """
    Wraps AsyncAnthropic.

    Two deliberate deviations from a naive port of the OpenAI backend, both
    required for correctness on Claude Sonnet 5:

    - Never forwards temperature/top_p/top_k: Sonnet 5 returns 400 on a
      non-default sampling value, and LLMConfig's default temperature (0.2)
      is non-default.
    - Explicitly disables thinking: these are short, deterministic
      completions (an explanation paragraph, a unified diff), not agentic
      reasoning, and Sonnet 5 runs adaptive thinking by default when
      `thinking` is omitted — sharing the same max_tokens budget as the
      response text. Disabling it avoids a fix-diff generation silently
      truncating to (near-)nothing.
    """

    DEFAULT_MODEL = "claude-sonnet-5"

    # Generic wording deliberately: Anthropic's own guidance is that naming
    # thinking tags explicitly is measurably less effective than a generic
    # "no internal/system XML tags" instruction, and that telling the model
    # not to reason can increase tag leakage rather than suppress it.
    SYSTEM_GUARD = (
        "Respond with only the requested output. Do not include internal "
        "or system XML tags in your response."
    )

    def __init__(self, client: AsyncAnthropic, config: LLMConfig) -> None:
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
        response = await self._client.messages.create(
            model=model or self._config.model or self.DEFAULT_MODEL,
            max_tokens=max_tokens or self._config.max_tokens,
            system=self.SYSTEM_GUARD,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )


def _make_openai_backend(config: LLMConfig) -> _OpenAIBackend | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if AsyncOpenAI is None or not api_key:
        return None
    return _OpenAIBackend(AsyncOpenAI(api_key=api_key), config)


def _make_anthropic_backend(config: LLMConfig) -> _AnthropicBackend | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if AsyncAnthropic is None or not api_key:
        return None
    return _AnthropicBackend(AsyncAnthropic(api_key=api_key), config)


class LLM:
    """
    Thin facade over a resolved provider backend.

    Provider selection follows this precedence:
    1. Explicit LLMConfig.provider (if set)
    2. AURA_LLM_PROVIDER env var (if set)
    3. Auto-detection: Anthropic first, then OpenAI, then stub
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._backend = self._resolve_backend()

    def _resolve_backend(self) -> _Backend:
        requested = (self.config.provider or os.getenv("AURA_LLM_PROVIDER") or "").strip().lower()

        if requested == "anthropic":
            return _make_anthropic_backend(self.config) or _StubBackend()
        if requested == "openai":
            return _make_openai_backend(self.config) or _StubBackend()

        # Unset, or an unrecognized value: auto-detect, Anthropic first.
        return (
            _make_anthropic_backend(self.config)
            or _make_openai_backend(self.config)
            or _StubBackend()
        )

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
