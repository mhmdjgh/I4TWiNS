import json
from typing import Any

import pytest
from pydantic import ValidationError

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.nodes.router import Router
from skill_agent.routing import RoutingDecision
from skill_agent.skills import registry
from tests.fakes import ScriptedChatModel, replies

CONTEXT = {"skills": ["summarizer", "translator", "calculator", "general_chat"], "max_skills": 2}


def decision(**fields: Any) -> str:
    return json.dumps(fields, ensure_ascii=False)


def step(skill: str, **extra: Any) -> dict[str, Any]:
    return {"skill": skill, "instruction": f"run {skill}", **extra}


class TestRoutingSchema:
    def test_aliases_and_language_names(self) -> None:
        parsed = RoutingDecision.model_validate_json(
            decision(
                skills=[step("Translate", target_language="none")], response_language="Persian"
            ),
            context=CONTEXT,
        )
        assert parsed.skill_names == ["translator"]
        assert parsed.skills[0].target_language is None
        assert parsed.response_language == "fa"

    def test_unknown_skill_rejected_with_actionable_message(self) -> None:
        with pytest.raises(ValidationError, match="use only: summarizer"):
            RoutingDecision.model_validate_json(decision(skills=[step("poet")]), context=CONTEXT)

    def test_too_many_skills_rejected(self) -> None:
        body = decision(skills=[step("summarizer"), step("translator"), step("calculator")])
        with pytest.raises(ValidationError, match="at most 2"):
            RoutingDecision.model_validate_json(body, context=CONTEXT)

    def test_mode_made_consistent(self) -> None:
        one = RoutingDecision.model_validate_json(
            decision(skills=[step("calculator")], mode="parallel"), context=CONTEXT
        )
        two = RoutingDecision.model_validate_json(
            decision(skills=[step("calculator"), step("translator")], mode="single"),
            context=CONTEXT,
        )
        assert (one.mode, two.mode) == ("single", "parallel")

    def test_validation_without_context_is_permissive(self) -> None:
        parsed = RoutingDecision.model_validate_json(decision(skills=[step("anything")]))
        assert parsed.skill_names == ["anything"]


def make_router(*responses: str, **settings: Any) -> tuple[Router, ScriptedChatModel]:
    model = ScriptedChatModel(responder=replies(*responses))
    router = Router(LLMClient(model), registry, Settings(_env_file=None, **settings))
    return router, model


def route(router: Router, text: str, language: str = "en") -> RoutingDecision:
    return router({"text": text, "language": language})["decision"]


class TestRouterNode:
    def test_prompt_is_generated_from_registry(self) -> None:
        prompt = make_router()[0].build_prompt()
        for name in registry.names:
            assert f"- {name}:" in prompt
        assert "{{" not in prompt

    def test_happy_path(self) -> None:
        body = decision(
            skills=[step("summarizer"), step("translator", target_language="English")],
            mode="sequential",
            response_language="fa",
            confidence=0.9,
        )
        router, _ = make_router(body)
        result = route(router, "خلاصه کن و ترجمه کن: ...", "fa")
        assert result.skill_names == ["summarizer", "translator"]
        assert result.mode == "sequential"

    def test_repairs_unknown_skill(self) -> None:
        router, model = make_router(
            decision(skills=[step("poet")]), decision(skills=[step("general_chat")])
        )
        assert route(router, "write a poem").skill_names == ["general_chat"]
        assert "unknown skill" in str(model.calls[1][-1].content)

    def test_invalid_output_falls_back_to_chat(self) -> None:
        router, _ = make_router("not json", "still not json")
        result = route(router, "سلام", "fa")
        assert result.skill_names == ["general_chat"]
        assert result.response_language == "fa"

    def test_empty_selection_falls_back_to_chat(self) -> None:
        router, _ = make_router(decision(skills=[]))
        assert route(router, "hmm").skill_names == ["general_chat"]

    def test_clarification_gets_default_question(self) -> None:
        router, _ = make_router(decision(skills=[], needs_clarification=True))
        result = route(router, "ترجمه کن", "fa")
        assert result.needs_clarification and result.skills == []
        assert "مطمئن نیستم" in (result.clarification_question or "")

    def test_low_confidence_turns_into_clarification(self) -> None:
        router, _ = make_router(decision(skills=[step("calculator")], confidence=0.2))
        assert route(router, "do the thing").needs_clarification

    def test_low_confidence_chat_is_kept(self) -> None:
        router, _ = make_router(decision(skills=[step("general_chat")], confidence=0.2))
        result = route(router, "hmm")
        assert not result.needs_clarification and result.skill_names == ["general_chat"]

    def test_response_language_defaults_to_detected(self) -> None:
        router, _ = make_router(decision(skills=[step("general_chat")]))
        assert route(router, "سلام", "fa").response_language == "fa"
