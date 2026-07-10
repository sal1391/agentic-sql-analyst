"""OpenAI client: interface, error concealment, model default."""
from types import SimpleNamespace

import pytest

from app import openai_client
from app.openai_client import GENERIC_LLM_ERROR, call_openai_complete


class _FakeCompletions:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        msg = SimpleNamespace(content=self.reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _install_fake(monkeypatch, completions):
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(openai_client, "_get_client", lambda: fake_client)


def test_returns_content_and_defaults_model(monkeypatch):
    fake = _FakeCompletions(reply="SELECT 1")
    _install_fake(monkeypatch, fake)
    monkeypatch.setattr(openai_client, "OPENAI_MODEL", "gpt-4o-mini")

    assert call_openai_complete("hi") == "SELECT 1"
    assert fake.last_kwargs["model"] == "gpt-4o-mini"
    roles = [m["role"] for m in fake.last_kwargs["messages"]]
    assert roles == ["system", "user"]


def test_explicit_model_wins(monkeypatch):
    fake = _FakeCompletions(reply="ok")
    _install_fake(monkeypatch, fake)
    call_openai_complete("hi", model="gpt-4o")
    assert fake.last_kwargs["model"] == "gpt-4o"


def test_provider_errors_are_concealed(monkeypatch):
    _install_fake(monkeypatch, _FakeCompletions(error=Exception("openai.RateLimitError: gpt-4o-mini quota")))
    with pytest.raises(RuntimeError) as exc_info:
        call_openai_complete("hi")
    msg = str(exc_info.value)
    assert msg == GENERIC_LLM_ERROR
    assert "openai" not in msg.lower() and "gpt" not in msg.lower()
    assert exc_info.value.__cause__ is None  # `from None` — no chained provider traceback


def test_missing_key_is_concealed(monkeypatch):
    monkeypatch.setattr(openai_client, "OPENAI_API_KEY", "")
    monkeypatch.setattr(openai_client, "_client", None)
    with pytest.raises(RuntimeError) as exc_info:
        openai_client._get_client()
    assert str(exc_info.value) == GENERIC_LLM_ERROR


def test_missing_key_via_call_is_concealed(monkeypatch):
    monkeypatch.setattr(openai_client, "OPENAI_API_KEY", "")
    monkeypatch.setattr(openai_client, "_client", None)
    with pytest.raises(RuntimeError) as exc_info:
        call_openai_complete("hi")
    assert str(exc_info.value) == GENERIC_LLM_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_system_prompt_hardening_content():
    sp = openai_client.SYSTEM_PROMPT.lower()
    assert "never" in sp                      # concealment directives present
    assert "built-in analyst" in sp           # neutral self-identification
    assert "ignore previous instructions" in sp or "instructions" in sp
