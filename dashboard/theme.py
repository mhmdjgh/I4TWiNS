"""Global styles. Streamlit's dark theme comes from .streamlit/config.toml; styles/theme.css adds
the design system on top (typography, surfaces, chips, pipeline view) and styles/rtl.css switches
the layout to right-to-left for the Persian interface."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

STYLES = Path(__file__).parent / "styles"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
    "&family=Vazirmatn:wght@400;500;600;700;800"
    "&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400..600,0..1,0&display=swap"
)


def _css(name: str) -> str:
    return (STYLES / name).read_text(encoding="utf-8")


def apply(language: str) -> None:
    st.html(f"<style>@import url('{FONTS}');\n{_css('theme.css')}</style>")
    if language == "fa":
        st.html(f"<style>{_css('rtl.css')}</style>")
