# tests/test_explain_llm_prompt.py

from aura.core.explain import build_llm_explanation_prompt


def test_build_llm_explanation_prompt_with_findings():
    findings = [
        {
            "rule_id": "REENTRANCY",
            "severity": "HIGH",
            "score": 0.9,
            "title": "Possible reentrancy vulnerability",
            "description": "External call before state update.\nMore details here...",
            "location": {
                "path": "contracts/Reentrancy.sol",
                "start_line": 42,
            },
        },
        {
            "rule_id": "OVERFLOW",
            "severity": "MEDIUM",
            "score": 0.7,
            "title": "Potential integer overflow",
            "description": "Unchecked arithmetic on user input.",
            "location": {
                "path": "contracts/Overflow.sol",
                "start_line": 10,
            },
        },
    ]

    prompt = build_llm_explanation_prompt(findings, max_items=2)

    assert "You are an expert smart contract security auditor." in prompt
    assert "REENTRANCY" in prompt
    assert "HIGH" in prompt
    assert "contracts/Reentrancy.sol:42" in prompt
    assert "OVERFLOW" in prompt
    assert "integer overflow" in prompt


def test_build_llm_explanation_prompt_with_no_findings():
    prompt = build_llm_explanation_prompt([], max_items=3)

    # For empty findings we should still get a helpful instruction.
    assert "did not find any issues" in prompt
    assert "does not guarantee the absence of vulnerabilities" in prompt
