from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from skill_agent.config import Settings
from skill_agent.llm import LLMClient, Usage


@dataclass(frozen=True)
class SkillCard:
    """What the router knows about a skill.

    Cards are deliberately small: the router only ever sees cards, never a skill's full prompt,
    so adding a skill costs the router a few lines of context instead of a whole system prompt.
    """

    name: str
    summary: str
    use_when: str
    examples: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    titles: Mapping[str, str] = field(default_factory=dict)

    def title(self, language: str) -> str:
        return self.titles.get(language) or self.titles.get("en") or self.name

    def render(self) -> str:
        lines = [f"- {self.name}: {self.summary}", f"  Use when: {self.use_when}"]
        if self.examples:
            lines.append("  Examples: " + " | ".join(self.examples[:3]))
        return "\n".join(lines)


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    arguments: dict[str, Any]
    output: str
    ok: bool = True


class SkillTask(BaseModel):
    """Input of a skill execution node."""

    model_config = ConfigDict(frozen=True)

    step: int
    skill: str
    instruction: str
    prompt: str
    language: str
    target_language: str | None = None
    input_text: str | None = None
    max_output_tokens: int = 1_000


class SkillOutput(BaseModel):
    text: str
    usage: Usage = Usage()
    tool_calls: list[ToolCall] = []
    notes: list[str] = []


class Skill(ABC):
    card: ClassVar[SkillCard]

    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings

    @property
    def name(self) -> str:
        return self.card.name

    @abstractmethod
    def run(self, task: SkillTask) -> SkillOutput: ...
