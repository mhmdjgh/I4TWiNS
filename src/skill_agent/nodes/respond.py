"""Terminal nodes. Neither calls the LLM: composing results is deterministic formatting, which
keeps the final step cheap and means outputs are never re-sent to the model just to be joined."""

from __future__ import annotations

from typing import Any

from skill_agent.i18n import t
from skill_agent.skills.registry import SkillRegistry
from skill_agent.state import AgentState, SkillResult, TraceEvent


def clarify(state: AgentState) -> dict[str, Any]:
    decision = state["decision"]
    question = decision.clarification_question or t("clarify.generic", decision.response_language)
    event = TraceEvent(node="clarify", elapsed_ms=0.0, detail="asked the user to clarify")
    return {"answer": question, "trace": [event]}


class Composer:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def _text(self, result: SkillResult, language: str) -> str:
        if result.ok and result.output is not None:
            return result.output.text
        return t("skill.failed", language, error=result.error or "unknown error")

    def _section(self, result: SkillResult, language: str) -> str:
        title = self.registry.get(result.skill).card.title(language)
        return f"**{title}**\n\n{self._text(result, language)}"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        decision = state["decision"]
        language = decision.response_language
        results = sorted(state.get("results", []), key=lambda r: r.step)

        if len(results) == 1:
            answer = self._text(results[0], language)
        elif decision.mode == "sequential" and all(r.ok for r in results):
            # The user asked for the chained result (e.g. the translated summary).
            answer = self._text(results[-1], language)
        else:
            answer = "\n\n".join(self._section(r, language) for r in results)

        event = TraceEvent(node="compose", elapsed_ms=0.0, detail=f"{len(results)} result(s)")
        return {"answer": answer, "trace": [event]}
