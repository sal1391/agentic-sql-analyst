"""Soft start screen shown before the public demo loads."""
from __future__ import annotations

import os

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


_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_TRIDENT_PATH = os.path.join(_ASSETS_DIR, "trident.png")


def require_start() -> bool:
    """Render the start screen until the visitor begins the demo."""
    if st.session_state.get("demo_started"):
        return True

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if os.path.exists(_TRIDENT_PATH):
            st.image(_TRIDENT_PATH, width=96)
        st.markdown("## Month-over-Month Comparison")
        st.markdown("Click Start to begin the demo.")
        render_turnstile_widget()
        started = st.button("Start", type="primary", use_container_width=True)
        render_privacy_notice()
        if started:
            ip = get_client_ip()
            token = st.session_state.get("cf_turnstile_token", "")
            if not verify_turnstile(token, ip):
                st.error("Verification failed. Please try again.")
            elif is_rate_limited(ip):
                log_event("demo_start_rate_limited", ip=ip)
                st.error("Too many attempts from your network. Please try again later.")
            else:
                record_attempt(ip)
                st.session_state.demo_started = True
                st.session_state.demo_ip = ip
                log_event("demo_start", ip=ip)
                st.rerun()
    return False
