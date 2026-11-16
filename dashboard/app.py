"""Web dashboard for the agent.

A second, thin interface next to the CLI: it calls the same `Agent` in-process (there is no web
API layer) and makes the internals visible: routing decision, execution pipeline, tool calls and
the evaluation results. The interface is available in English and Persian (right-to-left).

    uv run --extra dashboard streamlit run dashboard/app.py
"""

from __future__ import annotations

from html import escape

import architecture_page
import chat_page
import evaluation_page
import streamlit as st
import theme
from services import get_agent
from strings import language, t

from skill_agent.config import get_settings

st.set_page_config(
    page_title="Skill Agent",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="auto",
)


def sidebar() -> None:
    with st.sidebar:
        st.html(
            '<div class="sa-brand"><div class="sa-logo">'
            '<span class="material-symbols-rounded">hub</span></div>'
            f'<div><div class="sa-brand-name">Skill Agent</div>'
            f'<div class="sa-brand-tag">{escape(t("brand.tagline"))}</div></div></div>'
        )
        st.segmented_control(
            t("side.language"),
            options=["en", "fa"],
            format_func=lambda code: "English" if code == "en" else "فارسی",
            key="ui_lang",
            width="stretch",
        )

        settings = get_settings()
        agent, _ = get_agent()
        status = (
            f'<span class="sa-dot" style="color:#34d399">{escape(t("side.connected"))}</span>'
            if agent is not None
            else f'<span class="sa-dot" style="color:#f87171">{escape(t("side.no_key"))}</span>'
        )
        rows = [
            (t("side.status"), status),
            ("", f"<b>{escape(settings.llm_model)}</b>"),
            (t("side.reasoning"), f"<b>{escape(settings.llm_reasoning)}</b>"),
            (t("side.max_skills"), f"<b>{settings.max_skills_per_request}</b>"),
        ]
        body = "".join(f'<div class="sa-status-row"><span>{k}</span>{v}</div>' for k, v in rows)
        st.html(f'<div class="sa-status">{body}</div>')

        if st.button(t("side.new_chat"), icon=":material/add_comment:", width="stretch"):
            st.session_state.history = []
            st.rerun()
        st.html(f'<div class="sa-note">{escape(t("side.stateless"))}</div>')


if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"
if st.session_state.ui_lang is None:  # segmented control can be cleared by clicking again
    st.session_state.ui_lang = "en"

theme.apply(language())
sidebar()

page = st.navigation(
    [
        st.Page(
            chat_page.render,
            title=t("nav.chat"),
            icon=":material/forum:",
            url_path="chat",
            default=True,
        ),
        st.Page(
            architecture_page.render,
            title=t("nav.architecture"),
            icon=":material/account_tree:",
            url_path="architecture",
        ),
        st.Page(
            evaluation_page.render,
            title=t("nav.evaluation"),
            icon=":material/monitoring:",
            url_path="evaluation",
        ),
    ],
    position="top",
)
page.run()
