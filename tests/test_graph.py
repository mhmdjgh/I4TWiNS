"""End-to-end graph runs against a scripted model (no network).

The fake model answers based on which prompt it receives, so parallel branches can run in any
order and still get the right reply.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import BaseMessage

from skill_agent.agent import Agent
from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from tests.fakes import ScriptedChatModel


def routing(*skills: dict[str, Any], mode: str = "single", **extra: Any) -> str:
    body = {"skills": list(skills), "mode": mode, "confidence": 0.9, **extra}
    return json.dumps(body, ensure_ascii=False)


def step(skill: str, instruction: str = "", **extra: Any) -> dict[str, Any]:
    return {"skill": skill, "instruction": instruction or f"run {skill}", **extra}


def scripted(router_reply: str, **skill_replies: str | Callable[[str], str]) -> ScriptedChatModel:
    prompts = {
        "router of a multi-skill assistant": "router",
        "math-extraction step": "calculator",
        "You summarize texts": "summarizer",
        "professional translator": "translator",
        "conversational part of an assistant": "general_chat",
    }

    def respond(messages: list[BaseMessage]) -> str:
        system, user = str(messages[0].content), str(messages[-1].content)
        role = next(name for marker, name in prompts.items() if marker in system)
        if role == "router":
            return router_reply
        reply = skill_replies[role]
        return reply(user) if callable(reply) else reply

    return ScriptedChatModel(responder=respond)


def make_agent(model: ScriptedChatModel) -> Agent:
    return Agent(LLMClient(model), Settings(_env_file=None))


def test_single_skill() -> None:
    agent = make_agent(scripted(routing(step("general_chat")), general_chat="سلام! خوبم."))
    response = agent.run("سلام، خوبی؟")
    assert response.answer == "سلام! خوبم."
    assert response.language == "fa"
    assert [e.node for e in response.trace] == ["preprocess", "router", "general_chat", "compose"]


def test_calculator_uses_tool_result() -> None:
    plan = json.dumps({"problems": [{"label": "2^16", "expression": "2 ** 16"}]})
    agent = make_agent(scripted(routing(step("calculator")), calculator=plan))
    response = agent.run("what is 2 to the power of 16?")
    assert "**65536**" in response.answer
    assert response.results[0].output is not None
    assert response.results[0].output.tool_calls[0].output == "65536"


def test_sequential_chain_feeds_previous_output() -> None:
    seen: dict[str, str] = {}

    def translate(user: str) -> str:
        seen["translator_input"] = user
        return "AI is changing the world."

    decision = routing(
        step("summarizer"),
        step("translator", target_language="English"),
        mode="sequential",
        response_language="fa",
    )
    agent = make_agent(
        scripted(decision, summarizer="هوش مصنوعی جهان را تغییر می‌دهد.", translator=translate)
    )
    response = agent.run(
        "این متن را خلاصه کن و به انگلیسی ترجمه کن: هوش مصنوعی در چند سال گذشته شیوه‌ی کار، "
        "آموزش و ارتباط میلیون‌ها نفر را در سراسر جهان تغییر داده است."
    )

    assert response.answer == "AI is changing the world."
    assert "<text>\nهوش مصنوعی جهان را تغییر می‌دهد.\n</text>" in seen["translator_input"]
    # The second step sees the instruction, not the original text it should not translate.
    assert "میلیون‌ها نفر" not in seen["translator_input"]
    assert "این متن را خلاصه کن و به انگلیسی ترجمه کن" in seen["translator_input"]
    assert "Target language: English" in seen["translator_input"]
    assert [r.skill for r in response.results] == ["summarizer", "translator"]


def test_parallel_results_are_sectioned() -> None:
    plan = json.dumps({"problems": [{"label": "15% of 320", "expression": "320 * 15 / 100"}]})
    decision = routing(
        step("translator", target_language="Persian"), step("calculator"), mode="parallel"
    )
    agent = make_agent(scripted(decision, translator="صبح بخیر", calculator=plan))
    response = agent.run('Translate "good morning" into Persian, and what is 15% of 320?')

    assert response.answer.index("**Translation**") < response.answer.index("**Calculation**")
    assert "صبح بخیر" in response.answer and "**48**" in response.answer
    assert {e.node for e in response.trace} >= {"translator", "calculator", "compose"}


def test_parallel_steps_get_their_own_span() -> None:
    seen: dict[str, str] = {}

    def translate(user: str) -> str:
        seen["translator"] = user
        return "در امتحانت موفق باشی"

    plan = json.dumps({"problems": [{"label": "15% of 3200", "expression": "3200 * 15 / 100"}]})
    decision = routing(
        step("translator", target_language="Persian", input="good luck with your exam"),
        step("calculator", input="what 15% of 3,200 is"),
        mode="parallel",
    )
    agent = make_agent(scripted(decision, translator=translate, calculator=plan))
    agent.run(
        "Translate 'good luck with your exam' into Persian, and also tell me what 15% of 3,200 is."
    )
    assert "<text>\ngood luck with your exam\n</text>" in seen["translator"]


def test_invented_span_is_ignored() -> None:
    seen: dict[str, str] = {}

    def translate(user: str) -> str:
        seen["translator"] = user
        return "سلام"

    decision = routing(step("translator", input="text that is not in the prompt"))
    agent = make_agent(scripted(decision, translator=translate))
    agent.run("Translate into Persian: hello")
    assert "<text>" not in seen["translator"]


def test_parallel_failure_is_isolated() -> None:
    def broken(_: str) -> str:
        raise RuntimeError("provider timeout")

    decision = routing(step("general_chat"), step("translator"), mode="parallel")
    agent = make_agent(scripted(decision, general_chat="Hi!", translator=broken))
    response = agent.run("hi, and translate 'merci'")
    assert "Hi!" in response.answer
    assert "could not be completed: provider timeout" in response.answer


def test_sequential_stops_after_failure() -> None:
    def broken(_: str) -> str:
        raise RuntimeError("boom")

    decision = routing(step("summarizer"), step("translator"), mode="sequential")
    agent = make_agent(scripted(decision, summarizer=broken, translator="unused"))
    response = agent.run(
        "summarize and translate: The council approved the new budget after a long debate "
        "about housing, transport and the future of the old harbour district."
    )
    assert [r.skill for r in response.results] == ["summarizer"]
    assert "boom" in response.answer


def test_clarification_ends_without_skills() -> None:
    decision = routing(
        needs_clarification=True,
        clarification_question="Which text should I translate?",
    )
    agent = make_agent(scripted(decision))
    response = agent.run("translate this")
    assert response.answer == "Which text should I translate?"
    assert response.results == []
    assert response.trace[-1].node == "clarify"


def test_invalid_router_output_falls_back_to_chat() -> None:
    agent = make_agent(scripted("I think you want chat", general_chat="Hello!"))
    response = agent.run("hello")
    assert response.answer == "Hello!"
    assert response.decision is not None and response.decision.skill_names == ["general_chat"]


def test_provider_failure_returns_friendly_error() -> None:
    def down(_: list[BaseMessage]) -> str:
        raise ConnectionError("network unreachable")

    agent = make_agent(ScriptedChatModel(responder=down))
    response = agent.run("سلام")
    assert response.error is not None and "network unreachable" in response.error
    assert "دسترسی ندارم" in response.answer


def test_route_only() -> None:
    agent = make_agent(scripted(routing(step("calculator"))))
    assert agent.route("2+2").skill_names == ["calculator"]


def test_mermaid_lists_every_node() -> None:
    diagram = make_agent(scripted(routing())).mermaid()
    for node in ("preprocess", "router", "summarizer", "translator", "calculator", "compose"):
        assert node in diagram
