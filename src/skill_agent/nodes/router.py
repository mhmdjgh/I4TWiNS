from __future__ import annotations

from time import perf_counter
from typing import Any

from skill_agent.config import Settings
from skill_agent.context.shortlist import Shortlister
from skill_agent.context.tokens import excerpt
from skill_agent.i18n import t
from skill_agent.llm import LLMClient, StructuredOutputError, Usage
from skill_agent.prompts import load_prompt, render
from skill_agent.routing import RoutingDecision, SkillStep
from skill_agent.skills.base import SkillCard
from skill_agent.skills.registry import SkillRegistry
from skill_agent.state import AgentState, TraceEvent
from skill_agent.text.persian import detect_language


def _known_or_english(language: str) -> str:
    return language if language != "unknown" else "en"


class Router:
    """Routing node: one LLM call that returns a validated `RoutingDecision`.

    Deterministic policies are applied on top of the model's answer so that the fallback
    behaviour does not depend on the model following every rule in the prompt.
    """

    def __init__(self, llm: LLMClient, registry: SkillRegistry, settings: Settings) -> None:
        self.llm = llm
        self.registry = registry
        self.settings = settings
        self.shortlister = Shortlister(
            registry.cards(),
            registry.fallback,
            threshold=settings.shortlist_threshold,
            top_k=settings.shortlist_top_k,
        )

    def build_prompt(self, cards: list[SkillCard] | None = None) -> str:
        cards = self.registry.cards() if cards is None else cards
        return render(
            load_prompt("router"),
            skills="\n".join(card.render() for card in cards),
            skill_names=", ".join(card.name for card in cards),
            max_skills=self.settings.max_skills_per_request,
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        start = perf_counter()
        language = state.get("language", "en")
        text = state["text"]
        # Context control: only the relevant skill cards, and only the head/tail of long text.
        cards = self.shortlister.select(text)
        message = excerpt(text, self.settings.router_excerpt_tokens)
        usage = Usage()
        notes = [f"{len(cards)}/{len(self.registry)} skill cards"]
        if message is not text:
            notes.append("message excerpted")
        try:
            decision, usage = self.llm.structured(
                self.build_prompt(cards),
                f"Message:\n{message}",
                RoutingDecision,
                context={
                    "skills": [card.name for card in cards],
                    "max_skills": self.settings.max_skills_per_request,
                },
                max_tokens=500,
            )
        except StructuredOutputError as exc:
            decision = self.fallback_decision(language)
            notes.append(f"router output invalid, falling back: {exc}")

        decision = self.apply_policies(decision, language)
        event = TraceEvent(
            node="router",
            elapsed_ms=(perf_counter() - start) * 1000,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            detail="; ".join([self.describe(decision), *notes]),
        )
        return {"decision": decision, "trace": [event]}

    def fallback_decision(self, language: str) -> RoutingDecision:
        return RoutingDecision(
            reasoning="Router output was unusable; using the fallback skill.",
            skills=[self._fallback_step()],
            response_language=_known_or_english(language),
            confidence=0.0,
        )

    def _fallback_step(self) -> SkillStep:
        return SkillStep(skill=self.registry.fallback, instruction="reply to the user")

    def apply_policies(self, decision: RoutingDecision, language: str) -> RoutingDecision:
        if not decision.response_language:
            decision = decision.model_copy(
                update={"response_language": _known_or_english(language)}
            )
        reply_language = decision.response_language

        if decision.needs_clarification:
            question = decision.clarification_question
            # Small models sometimes write the question in English for a Persian message.
            wrong_language = reply_language in {"fa", "en"} and detect_language(
                question or ""
            ) not in {reply_language, "unknown"}
            if not question or wrong_language:
                question = t("clarify.generic", reply_language)
            return decision.model_copy(update={"skills": [], "clarification_question": question})

        if not decision.skills:
            return decision.model_copy(update={"skills": [self._fallback_step()], "mode": "single"})

        decision = self._split_summary_translation(decision)

        only_fallback = decision.skill_names == [self.registry.fallback]
        if decision.confidence < self.settings.clarify_below_confidence and not only_fallback:
            return decision.model_copy(
                update={
                    "skills": [],
                    "mode": "single",
                    "needs_clarification": True,
                    "clarification_question": t("clarify.generic", reply_language),
                }
            )
        return decision

    def _split_summary_translation(self, decision: RoutingDecision) -> RoutingDecision:
        """A summary in another language is summarizer -> translator, never one step.

        If the router puts a target language on a lone summarizer step ("TL;DR in French"), the
        change of language is handed to the translator, which has the checks for it.
        """
        steps = decision.skills
        if (
            len(steps) != 1
            or steps[0].skill != "summarizer"
            or not steps[0].target_language
            or "translator" not in self.registry
            or self.settings.max_skills_per_request < 2
        ):
            return decision
        target = steps[0].target_language
        summarize = steps[0].model_copy(update={"target_language": None})
        translate = SkillStep(
            skill="translator",
            instruction=f"translate the summary into {target}",
            target_language=target,
        )
        return decision.model_copy(update={"skills": [summarize, translate], "mode": "sequential"})

    @staticmethod
    def describe(decision: RoutingDecision) -> str:
        if decision.needs_clarification:
            return "needs clarification"
        skills = " -> " if decision.mode == "sequential" else " + "
        return f"{skills.join(decision.skill_names)} ({decision.mode}, conf={decision.confidence})"
