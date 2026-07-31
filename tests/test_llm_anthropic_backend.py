import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aura.core.llm import LLMConfig, _AnthropicBackend


def _fake_client(blocks):
    return SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(content=blocks)))
    )


def test_never_forwards_sampling_params_and_disables_thinking():
    client = _fake_client([SimpleNamespace(type="text", text="hello")])
    backend = _AnthropicBackend(client, LLMConfig())

    result = asyncio.run(
        backend.acomplete("explain this", model=None, temperature=0.9, max_tokens=None)
    )

    assert result == "hello"
    kwargs = client.messages.create.await_args.kwargs
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert "top_k" not in kwargs
    assert kwargs["thinking"] == {"type": "disabled"}


def test_uses_default_model_and_max_tokens_when_unset():
    client = _fake_client([SimpleNamespace(type="text", text="ok")])
    backend = _AnthropicBackend(client, LLMConfig())

    asyncio.run(backend.acomplete("x", model=None, temperature=None, max_tokens=None))

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["max_tokens"] == 512


def test_honors_explicit_model_and_max_tokens_override():
    client = _fake_client([SimpleNamespace(type="text", text="ok")])
    backend = _AnthropicBackend(client, LLMConfig())

    asyncio.run(backend.acomplete("x", model="claude-opus-5", temperature=None, max_tokens=2048))

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["max_tokens"] == 2048


def test_sends_the_exact_system_guard_string():
    client = _fake_client([SimpleNamespace(type="text", text="ok")])
    backend = _AnthropicBackend(client, LLMConfig())

    asyncio.run(backend.acomplete("x", model=None, temperature=None, max_tokens=None))

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["system"] == (
        "Respond with only the requested output. Do not include internal "
        "or system XML tags in your response."
    )


def test_extracts_only_text_blocks_ignoring_others():
    client = _fake_client(
        [
            SimpleNamespace(type="thinking", thinking="internal reasoning..."),
            SimpleNamespace(type="text", text="the real answer"),
        ]
    )
    backend = _AnthropicBackend(client, LLMConfig())

    result = asyncio.run(backend.acomplete("x", model=None, temperature=None, max_tokens=None))

    assert result == "the real answer"
