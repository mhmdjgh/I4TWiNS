from __future__ import annotations

import re
from collections.abc import Iterator

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.skills.base import Skill, SkillCard

_VALID_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class UnknownSkillError(KeyError):
    pass


class SkillRegistry:
    """Catalogue of available skills.

    The graph, the router's prompt and the router's output validation are all generated from
    the registry, so a new skill is one new module with a `@register_skill` class.
    """

    def __init__(self, fallback: str = "general_chat") -> None:
        self.fallback = fallback
        self._skills: dict[str, type[Skill]] = {}

    def register(self, skill_cls: type[Skill]) -> type[Skill]:
        name = skill_cls.card.name
        if not _VALID_NAME.match(name):
            raise ValueError(f"skill name must be snake_case: {name!r}")
        if name in self._skills:
            raise ValueError(f"skill {name!r} is already registered")
        self._skills[name] = skill_cls
        return skill_cls

    def get(self, name: str) -> type[Skill]:
        try:
            return self._skills[name]
        except KeyError:
            raise UnknownSkillError(name) from None

    def __contains__(self, name: object) -> bool:
        return name in self._skills

    def __iter__(self) -> Iterator[type[Skill]]:
        return iter(self._skills.values())

    def __len__(self) -> int:
        return len(self._skills)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._skills)

    def cards(self) -> list[SkillCard]:
        return [skill.card for skill in self._skills.values()]

    def instantiate(self, llm: LLMClient, settings: Settings) -> dict[str, Skill]:
        if self.fallback not in self._skills:
            raise ValueError(f"fallback skill {self.fallback!r} is not registered")
        return {name: cls(llm, settings) for name, cls in self._skills.items()}


registry = SkillRegistry()


def register_skill(skill_cls: type[Skill]) -> type[Skill]:
    return registry.register(skill_cls)
