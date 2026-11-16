from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel

from skill_agent.routing import RoutingDecision
from skill_agent.skills.base import SkillOutput


class TraceEvent(BaseModel):
    node: str
    elapsed_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    detail: str = ""


class SkillResult(BaseModel):
    step: int
    skill: str
    output: SkillOutput | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.output is not None


class AgentState(TypedDict, total=False):
    prompt: str
    text: str
    language: str
    decision: RoutingDecision
    results: Annotated[list[SkillResult], operator.add]
    trace: Annotated[list[TraceEvent], operator.add]
    answer: str
