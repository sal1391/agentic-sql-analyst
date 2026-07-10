"""Demo-mode config: defaults, OpenAI vars, and no AWS/Snowflake side effects."""
import importlib
import os
import sys

import pytest

_ENV_KEYS = ("DEPLOY_MODE", "OPENAI_API_KEY", "OPENAI_MODEL")


@pytest.fixture(autouse=True)
def _restore_config_module():
    """Undo the sys.modules mutation _fresh_config performs.

    importlib.reload(app.config) reloads the shared module object in place,
    so a leftover override (e.g. DEPLOY_MODE="local") would otherwise leak
    into every other test/module that does `from app.config import ...`
    afterwards — including Streamlit AppTest, which re-executes app/main.py's
    import block (and therefore re-reads app.config) on every run.
    """
    yield
    for key in _ENV_KEYS:
        os.environ.pop(key, None)
    sys.modules.pop("app.config", None)
    import app.config  # noqa: F401  (re-import so later tests see a clean module)


def _fresh_config(monkeypatch, **env):
    """Reload app.config with a controlled environment."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    # dotenv must not override the test env
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None, raising=False)
    sys.modules.pop("app.config", None)
    import app.config
    return importlib.reload(app.config)


def test_demo_is_default_mode(monkeypatch):
    cfg = _fresh_config(monkeypatch)
    assert cfg.DEPLOY_MODE == "demo"
    assert cfg.IS_DEMO is True


def test_demo_mode_skips_snowflake_and_aws(monkeypatch):
    cfg = _fresh_config(monkeypatch)
    assert cfg.SNOWFLAKE_CONNECTION is None


def test_openai_model_default_and_override(monkeypatch):
    cfg = _fresh_config(monkeypatch)
    assert cfg.OPENAI_MODEL == "gpt-4o-mini"
    assert cfg.GUARDRAIL_MODEL == "gpt-4o-mini"
    cfg = _fresh_config(monkeypatch, OPENAI_MODEL="gpt-4o")
    assert cfg.OPENAI_MODEL == "gpt-4o"
    assert cfg.GUARDRAIL_MODEL == "gpt-4o-mini"  # classifier model never changes


def test_local_mode_still_builds_connection_dict(monkeypatch):
    cfg = _fresh_config(monkeypatch, DEPLOY_MODE="local")
    assert cfg.IS_DEMO is False
    assert isinstance(cfg.SNOWFLAKE_CONNECTION, dict)
