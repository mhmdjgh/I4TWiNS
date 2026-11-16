from __future__ import annotations

from pathlib import Path

import streamlit as st

from skill_agent.agent import Agent
from skill_agent.llm import ConfigurationError

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results.json"
DATASET = ROOT / "evals" / "dataset.yaml"
LOCAL_RUN = ROOT / "evals" / "runs" / "dashboard-latest.json"


@st.cache_resource(show_spinner=False)
def _load_agent() -> Agent:
    return Agent.from_settings()


def get_agent() -> tuple[Agent | None, str | None]:
    """The agent, or the reason it could not be created (usually a missing API key)."""
    try:
        return _load_agent(), None
    except ConfigurationError as exc:
        return None, str(exc)
