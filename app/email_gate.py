"""Email gate: a soft identification screen shown before the demo app loads.

Any format-valid email is accepted (no password, no verification). Entries are
logged via demo_log (stdout -> Railway log console, plus local JSONL).
"""
from __future__ import annotations

import os
import re

import streamlit as st

try:
    from app.demo_log import log_event
except ImportError:
    from demo_log import log_event

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_TRIDENT_PATH = os.path.join(_ASSETS_DIR, "trident.png")


def is_valid_email(email) -> bool:
    if not email:
        return False
    return bool(_EMAIL_RE.match(str(email).strip()))


def require_email() -> bool:
    """True if the visitor has already entered an email; otherwise render the gate."""
    if st.session_state.get("demo_email"):
        return True

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if os.path.exists(_TRIDENT_PATH):
            st.image(_TRIDENT_PATH, width=96)
        st.markdown("## Month-over-Month Comparison")
        st.markdown("Enter your email address to start the demo.")
        with st.form("email_gate_form"):
            email = st.text_input("Email address", key="email_gate_input",
                                  placeholder="you@company.com")
            submitted = st.form_submit_button("Start", type="primary",
                                              use_container_width=True)
        if submitted:
            email = (email or "").strip()
            if is_valid_email(email):
                st.session_state.demo_email = email
                log_event("email_entry", email=email)
                st.rerun()
            else:
                st.error("Please enter a valid email address.")
    return False
