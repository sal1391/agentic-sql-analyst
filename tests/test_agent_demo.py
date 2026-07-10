"""agent.py demo wiring: openai provider dispatch + demo error logging."""
import pytest

from app import agent


def test_call_llm_dispatches_openai(monkeypatch):
    captured = {}

    def fake_openai(prompt, model=None):
        captured["prompt"] = prompt
        captured["model"] = model
        return "response"

    monkeypatch.setattr(agent, "call_openai_complete", fake_openai)
    out = agent._call_llm("analyze this", "openai", session=None, model="gpt-4o-mini")
    assert out == "response"
    assert captured == {"prompt": "analyze this", "model": "gpt-4o-mini"}


def test_call_llm_openai_needs_no_session(monkeypatch):
    monkeypatch.setattr(agent, "call_openai_complete", lambda p, model=None: "ok")
    assert agent._call_llm("x", "openai") == "ok"


def test_call_llm_unknown_provider_still_raises():
    with pytest.raises(ValueError):
        agent._call_llm("x", "watson")


def test_cortex_still_requires_session():
    with pytest.raises(ValueError):
        agent._call_llm("x", "cortex", session=None)
