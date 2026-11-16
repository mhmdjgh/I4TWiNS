"""Public entry point used by the CLI, the dashboard and the evaluation script."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from skill_agent.config import Settings, get_settings
from skill_agent.graph import build_graph
from skill_agent.i18n import t
from skill_agent.llm import LLMClient, build_llm
from skill_agent.nodes.preprocess import preprocess
from skill_agent.nodes.router import Router
from skill_agent.routing import RoutingDecision
from skill_agent.skills import registry as default_registry
from skill_agent.skills.registry import SkillRegistry
from skill_agent.state import AgentState, SkillResult, TraceEvent
from skill_agent.text.persian import detect_language

log = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    prompt: str
    answer: str
    language: str
    decision: RoutingDecision | None = None
    results: list[SkillResult] = []
    trace: list[TraceEvent] = []
    elapsed_ms: float = 0.0
    error: str | None = None

    @property
    def tokens(self) -> tuple[int, int]:
        return (
            sum(e.input_tokens for e in self.trace),
            sum(e.output_tokens for e in self.trace),
        )


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        settings: Settings | None = None,
        registry: SkillRegistry = default_registry,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry
        self.router = Router(llm, registry, self.settings)
        self.graph = build_graph(llm, self.settings, registry)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Agent:
        settings = settings or get_settings()
        return cls(build_llm(settings), settings)

    def run(self, prompt: str) -> AgentResponse:
        start = perf_counter()
        try:
            state: dict[str, Any] = self.graph.invoke({"prompt": prompt})
        except Exception as exc:
            log.exception("agent run failed")
            language = detect_language(prompt)
            return AgentResponse(
                prompt=prompt,
                answer=t("agent.unavailable", language),
                language=language,
                elapsed_ms=(perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        return AgentResponse(
            prompt=prompt,
            answer=state.get("answer", ""),
            language=state.get("language", "unknown"),
            decision=state.get("decision"),
            results=sorted(state.get("results", []), key=lambda r: r.step),
            trace=state.get("trace", []),
            elapsed_ms=(perf_counter() - start) * 1000,
        )

    def route(self, prompt: str) -> RoutingDecision:
        """Run only preprocessing and routing (used to measure routing accuracy cheaply)."""
        state: AgentState = {"prompt": prompt}
        state.update(preprocess(state))  # type: ignore[typeddict-item]
        decision: RoutingDecision = self.router(state)["decision"]
        return decision

    def mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()
