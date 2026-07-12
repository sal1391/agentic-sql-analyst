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

try:
    from app.demo_abuse import (
        get_client_ip,
        is_rate_limited,
        record_attempt,
        render_turnstile_widget,
        verify_turnstile,
    )
except ImportError:
    from demo_abuse import (
        get_client_ip,
        is_rate_limited,
        record_attempt,
        render_turnstile_widget,
        verify_turnstile,
    )

try:
    from app.privacy import render_privacy_notice
except ImportError:
    from privacy import render_privacy_notice

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
            render_turnstile_widget()  # no-op unless Turnstile env vars are set
            submitted = st.form_submit_button("Start", type="primary",
                                              use_container_width=True)
        render_privacy_notice()
        if submitted:
            email = (email or "").strip()
            if not is_valid_email(email):
                st.error("Please enter a valid email address.")
            else:
                ip = get_client_ip()
                # 1. Turnstile (env-gated; passes through while disabled)
                token = st.session_state.get("cf_turnstile_token", "")
                if not verify_turnstile(token, ip):
                    st.error("Verification failed. Please try again.")
                # 2. Rate limit
                elif is_rate_limited(ip):
                    log_event("email_gate_rate_limited", ip=ip)
                    st.error("Too many attempts from your network. "
                             "Please try again later.")
                # 3. Accept + log (unchanged logging, now with IP)
                else:
                    record_attempt(ip)
                    st.session_state.demo_email = email
                    log_event("email_entry", email=email, ip=ip)
                    st.rerun()
    return False
