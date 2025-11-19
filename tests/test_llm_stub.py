# tests/test_llm_stub.py

from aura.core.llm import LLM


def test_llm_stub_default_behavior():
    """
    When no OPENAI_API_KEY is set (or openai is missing),
    LLM should fall back to the stub implementation and return
    a message starting with the stub prefix.
    """
    llm = LLM()
    out = llm.complete("Explain reentrancy in simple terms.")

    assert isinstance(out, str)
    assert out.startswith("[LLM STUB] No real LLM configured")
    assert "Prompt preview:" in out
