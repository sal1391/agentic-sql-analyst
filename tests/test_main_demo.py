"""Demo-mode app boot via Streamlit AppTest: email gate, hidden provider, months load."""
from streamlit.testing.v1 import AppTest


def _boot(**session_state):
    at = AppTest.from_file("app/main.py", default_timeout=60)
    for key, val in session_state.items():
        at.session_state[key] = val
    at.run()
    return at


def test_email_gate_blocks_until_email_entered():
    at = _boot()
    assert not at.exception
    # gate is showing: no sidebar month selectors yet
    assert len(at.selectbox) == 0
    assert any("email" in (ti.label or "").lower() for ti in at.text_input)


def test_app_renders_after_email_with_no_provider_controls():
    at = _boot(demo_email="visitor@example.com")
    assert not at.exception
    # months came from DuckDB demo data
    labels = [sb.label for sb in at.selectbox]
    assert "Month A (baseline)" in labels and "Month B (compare to)" in labels
    month_options = at.selectbox[0].options
    assert "2026-06-01" in month_options and len(month_options) == 18
    # provider controls are gone
    assert len(at.radio) == 0
    assert all("model" not in (ti.label or "").lower() for ti in at.text_input)
    # nothing on the page mentions the provider
    page_text = " ".join(str(getattr(el, "value", "")) for el in at.markdown)
    assert "openai" not in page_text.lower() and "gpt" not in page_text.lower()


def test_locked_session_hides_chat_input():
    at = _boot(demo_email="visitor@example.com", gr_locked=True)
    assert not at.exception
    assert len(at.chat_input) == 0
