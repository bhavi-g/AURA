from aura.core.llm import LLM, LLMConfig, _AnthropicBackend, _OpenAIBackend, _StubBackend


def test_no_keys_falls_back_to_stub(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = LLM()

    assert isinstance(llm._backend, _StubBackend)


def test_openai_key_present_selects_openai_backend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")

    llm = LLM()

    assert isinstance(llm._backend, _OpenAIBackend)


def test_explicit_openai_provider_without_key_falls_back_to_stub(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AURA_LLM_PROVIDER", raising=False)

    llm = LLM(LLMConfig(provider="openai"))

    assert isinstance(llm._backend, _StubBackend)


def test_env_var_openai_provider_selection(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")
    monkeypatch.setenv("AURA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    llm = LLM()

    assert isinstance(llm._backend, _OpenAIBackend)


def test_anthropic_key_present_selects_anthropic_backend(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AURA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-resolution-test")

    llm = LLM()

    assert isinstance(llm._backend, _AnthropicBackend)


def test_anthropic_preferred_over_openai_when_both_keys_present(monkeypatch):
    monkeypatch.delenv("AURA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-resolution-test")

    llm = LLM()

    assert isinstance(llm._backend, _AnthropicBackend)


def test_explicit_anthropic_provider_without_key_falls_back_to_stub(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AURA_LLM_PROVIDER", raising=False)
    # Even with an OpenAI key present, an explicit-but-unavailable request
    # must not fall through to OpenAI.
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")

    llm = LLM(LLMConfig(provider="anthropic"))

    assert isinstance(llm._backend, _StubBackend)


def test_env_var_anthropic_provider_selection(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-resolution-test")
    monkeypatch.setenv("AURA_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = LLM()

    assert isinstance(llm._backend, _AnthropicBackend)


def test_unrecognized_provider_value_falls_through_to_auto_detect(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-resolution-test")
    monkeypatch.setenv("AURA_LLM_PROVIDER", "some-typo-value")

    llm = LLM()

    assert isinstance(llm._backend, _OpenAIBackend)
