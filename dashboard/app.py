"""Web dashboard for the agent.

A second, thin interface next to the CLI: it calls the same `Agent` in-process (there is no web
API layer) and makes the internals visible: routing decision, execution steps, tool calls and
the evaluation results. Light, minimal and responsive. The interface is in English; prompts and
answers can be English or Persian, and Persian answers are shown right-to-left.

    uv run --extra dashboard streamlit run dashboard/app.py
"""

from __future__ import annotations

import architecture_page
import chat_page
import evaluation_page
import streamlit as st
import theme
from access import require_password
from services import get_agent
from strings import t

from skill_agent.config import get_settings

st.set_page_config(page_title="Skill Agent", page_icon=":material/hub:", layout="centered")
theme.apply()
require_password()

pages = [
    st.Page(chat_page.render, title=t("nav.chat"), url_path="chat", default=True),
    st.Page(architecture_page.render, title=t("nav.architecture"), url_path="architecture"),
    st.Page(evaluation_page.render, title=t("nav.evaluation"), url_path="evaluation"),
]
current = st.navigation(pages, position="hidden")


def settings_menu() -> None:
    settings = get_settings()
    agent, _ = get_agent()
    status = t("side.connected") if agent is not None else t("side.no_key")
    st.markdown(
        f"**{t('side.status')}:** {status}  \n`{settings.llm_model}`  \n"
        f"{t('side.reasoning')}: `{settings.llm_reasoning}` · "
        f"{t('side.max_skills')}: `{settings.max_skills_per_request}`"
    )
    st.caption(t("side.stateless"))
    if st.button(t("side.new_chat"), icon=":material/add_comment:", width="stretch"):
        st.session_state.history = []
        st.rerun()


def topbar() -> None:
    """Brand, page links and settings in one row that wraps on small screens."""
    with st.container(
        horizontal=True,
        wrap=True,
        vertical_alignment="center",
        horizontal_alignment="distribute",
        key="topbar",
    ):
        st.html(
            '<div class="sa-brand"><span class="sa-brand-mark">'
            '<span class="material-symbols-rounded">hub</span></span>Skill Agent</div>'
        )
        with st.container(horizontal=True, wrap=True, gap="small", width="content"):
            for page in pages:
                st.page_link(page)
        with st.popover("", icon=":material/tune:"):
            settings_menu()


topbar()
current.run()
