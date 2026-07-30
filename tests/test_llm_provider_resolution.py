# tests/test_llm_provider_resolution.py
#
# NOTE: this file grows in a later change once a second backend
# (Anthropic) exists to select between. For now it only covers the
# has-key / no-key OpenAI cases that are real today.

from aura.core.llm import LLM, _OpenAIBackend, _StubBackend


def test_no_keys_falls_back_to_stub(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = LLM()

    assert isinstance(llm._backend, _StubBackend)


def test_openai_key_present_selects_openai_backend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")

    llm = LLM()

    assert isinstance(llm._backend, _OpenAIBackend)
