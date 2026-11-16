"""Structured output of the routing node."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

_ALIASES = {
    "chat": "general_chat",
    "general": "general_chat",
    "generalchat": "general_chat",
    "translate": "translator",
    "translation": "translator",
    "summarize": "summarizer",
    "summarise": "summarizer",
    "summary": "summarizer",
    "calculate": "calculator",
    "calc": "calculator",
    "math": "calculator",
}

Mode = Literal["single", "parallel", "sequential"]


class SkillStep(BaseModel):
    skill: str
    instruction: str = Field(default="", max_length=400)
    target_language: str | None = Field(default=None, max_length=40)
    # For prompts with several tasks: the exact part of the message this skill must work on.
    input: str | None = None

    @field_validator("skill", mode="before")
    @classmethod
    def _canonical_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        name = value.strip().lower().replace("-", "_").replace(" ", "_")
        return _ALIASES.get(name, name)

    @field_validator("input", mode="before")
    @classmethod
    def _blank_input_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
            return None
        return value

    @field_validator("target_language", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "auto"}:
            return None
        return value


class RoutingDecision(BaseModel):
    """Which skills to run and how.

    Validation is context-aware: `model_validate_json(..., context={"skills": [...],
    "max_skills": n})` checks the names against the live registry, so the schema never needs to
    change when a skill is added. Errors are phrased for the model, which gets one chance to fix
    its own answer.
    """

    reasoning: str = Field(default="", max_length=600)
    skills: list[SkillStep] = Field(default_factory=list)
    mode: Mode = "single"
    response_language: str = Field(default="", max_length=20)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarification_question: str | None = None

    @field_validator("response_language", mode="before")
    @classmethod
    def _language_code(cls, value: object) -> object:
        names = {"persian": "fa", "farsi": "fa", "english": "en"}
        if isinstance(value, str):
            value = value.strip().lower()
            return names.get(value, value)
        return value

    @model_validator(mode="after")
    def _check_skills(self, info: ValidationInfo) -> RoutingDecision:
        context = info.context or {}
        allowed: list[str] | None = context.get("skills")
        max_skills: int | None = context.get("max_skills")

        if allowed is not None:
            unknown = [s.skill for s in self.skills if s.skill not in allowed]
            if unknown:
                raise ValueError(f"unknown skill name(s) {unknown}; use only: {', '.join(allowed)}")
        if max_skills is not None and len(self.skills) > max_skills:
            raise ValueError(
                f"{len(self.skills)} skills selected but at most {max_skills} are allowed; "
                "keep the ones the user asked for most explicitly"
            )

        if len(self.skills) <= 1:
            self.mode = "single"
        elif self.mode == "single":
            self.mode = "parallel"
        return self

    @property
    def skill_names(self) -> list[str]:
        return [step.skill for step in self.skills]
