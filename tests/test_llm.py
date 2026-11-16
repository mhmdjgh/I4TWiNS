import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from skill_agent.config import Settings
from skill_agent.llm import (
    ConfigurationError,
    LLMClient,
    StructuredOutputError,
    build_llm,
    extract_json,
)
from tests.fakes import ScriptedChatModel, replies


class Point(BaseModel):
    x: int
    y: int


@pytest.mark.parametrize(
    "text",
    [
        '{"x": 1, "y": 2}',
        'Sure!\n```json\n{"x": 1, "y": 2}\n```',
        'Here you go: {"x": 1, "y": 2} -- done',
    ],
)
def test_extract_json_tolerates_wrapping(text: str) -> None:
    assert Point.model_validate_json(extract_json(text)) == Point(x=1, y=2)


def test_extract_json_without_object() -> None:
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_complete_returns_text_and_usage() -> None:
    client = LLMClient(ScriptedChatModel(responder=replies(" hello ")))
    result = client.complete("sys", "hi")
    assert result.text == "hello"
    assert result.usage.input_tokens == 10


def test_structured_repairs_invalid_reply_once() -> None:
    model = ScriptedChatModel(responder=replies('{"x": "oops"}', '{"x": 3, "y": 4}'))
    point, usage = LLMClient(model).structured("sys", "give me a point", Point)
    assert point == Point(x=3, y=4)
    assert usage.output_tokens == 10
    assert "could not be used" in str(model.calls[1][-1].content)


def test_structured_gives_up_after_repairs() -> None:
    model = ScriptedChatModel(responder=replies("nope", "still nope"))
    with pytest.raises(StructuredOutputError):
        LLMClient(model).structured("sys", "user", Point)


def test_json_mode_sends_response_format() -> None:
    model = ScriptedChatModel(responder=replies('{"x": 1, "y": 1}'))
    LLMClient(model, json_mode=True).structured("sys", "user", Point)
    assert model.call_kwargs[0]["response_format"] == {"type": "json_object"}


def test_system_prompt_folded_when_role_unsupported() -> None:
    model = ScriptedChatModel(responder=replies("ok"))
    LLMClient(model, system_role=False).complete("RULES", "question")
    (message,) = model.calls[0]
    assert isinstance(message, HumanMessage)
    assert "RULES" in str(message.content) and "question" in str(message.content)


def test_system_role_used_by_default() -> None:
    model = ScriptedChatModel(responder=replies("ok"))
    LLMClient(model).complete("RULES", "question")
    assert isinstance(model.calls[0][0], SystemMessage)


def test_build_llm_requires_key() -> None:
    with pytest.raises(ConfigurationError):
        build_llm(Settings(_env_file=None, llm_api_key=None))
