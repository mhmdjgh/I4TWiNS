from __future__ import annotations

from time import perf_counter
from typing import Any

from skill_agent.state import AgentState, TraceEvent
from skill_agent.text.persian import detect_language, normalize_text


def preprocess(state: AgentState) -> dict[str, Any]:
    start = perf_counter()
    text = normalize_text(state["prompt"])
    language = detect_language(text)
    event = TraceEvent(
        node="preprocess",
        elapsed_ms=(perf_counter() - start) * 1000,
        detail=f"language={language}, chars={len(text)}",
    )
    return {"text": text, "language": language, "trace": [event]}
