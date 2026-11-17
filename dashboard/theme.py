"""Global styles. Streamlit's light theme comes from .streamlit/config.toml; styles/theme.css adds
the design system on top (typography, surfaces, steps, stats) and the responsive rules."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

STYLES = Path(__file__).parent / "styles"
# Vazirmatn renders Persian prompts and answers.
FONTS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
    "&family=Vazirmatn:wght@400;500;600;700"
    "&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400..600,0..1,0&display=swap"
)


def apply() -> None:
    css = (STYLES / "theme.css").read_text(encoding="utf-8")
    st.html(f"<style>@import url('{FONTS}');\n{css}</style>")
