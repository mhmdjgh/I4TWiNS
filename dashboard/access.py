"""Optional sign-in screen for a hosted dashboard.

When DASHBOARD_PASSWORD is set, nobody can send prompts (and spend the API key's credit) without
it. When it is empty, which is the default, the dashboard opens straight away.
"""

from __future__ import annotations

import hmac

import streamlit as st
from strings import t

from skill_agent.config import get_settings


def password_ok(entered: str, expected: str) -> bool:
    return hmac.compare_digest(entered.encode(), expected.encode())


def require_password() -> None:
    """Stop the page here until the right password has been entered in this browser session."""
    secret = get_settings().dashboard_password
    if secret is None or not secret.get_secret_value() or st.session_state.get("signed_in"):
        return

    st.html(f'<div class="sa-welcome"><h1>Skill Agent</h1><p>{t("auth.prompt")}</p></div>')
    with st.form("sign-in", border=False):
        entered = st.text_input(t("auth.label"), type="password")
        submitted = st.form_submit_button(t("auth.button"), type="primary", width="stretch")
    if submitted:
        if password_ok(entered, secret.get_secret_value()):
            st.session_state.signed_in = True
            st.rerun()
        st.error(t("auth.wrong"))
    st.stop()
