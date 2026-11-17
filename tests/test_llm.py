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


class LengthFinishReasonError(Exception):
    """Stand-in with the same name as the OpenAI SDK exception."""


def test_truncated_reply_is_retried_with_larger_budget() -> None:
    attempts = iter([LengthFinishReasonError("cut off"), '{"x": 1, "y": 2}'])

    def respond(_messages: object) -> str:
        outcome = next(attempts)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    model = ScriptedChatModel(responder=respond)
    point, _ = LLMClient(model).structured("sys", "user", Point, max_tokens=100)
    assert point == Point(x=1, y=2)
    assert [kw["max_tokens"] for kw in model.call_kwargs] == [100, 200]


def test_other_provider_errors_propagate() -> None:
    def respond(_messages: object) -> str:
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        LLMClient(ScriptedChatModel(responder=respond)).structured("sys", "user", Point)


def test_reasoning_allowance_pads_max_tokens() -> None:
    model = ScriptedChatModel(responder=replies("ok"))
    LLMClient(model, reasoning_tokens=1000).complete("sys", "user", max_tokens=200)
    assert model.call_kwargs[0]["max_tokens"] == 1200


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


@pytest.mark.parametrize(
    ("param", "level", "extra_body", "padding"),
    [
        ("openrouter", "off", {"reasoning": {"enabled": False}}, 0),
        ("openrouter", "low", {"reasoning": {"effort": "low"}}, 1024),
        ("openai", "off", {"reasoning_effort": "none"}, 0),
        ("openai", "high", {"reasoning_effort": "high"}, 1024),
        ("none", "off", None, 1024),
    ],
)
def test_reasoning_switch_per_provider(
    param: str, level: str, extra_body: object, padding: int
) -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_fallback_model=None,
        llm_reasoning=level,
        llm_reasoning_param=param,
    )
    client = build_llm(settings)
    assert client._model.extra_body == extra_body  # type: ignore[attr-defined]
    assert client._reasoning_tokens == padding


def test_empty_truncated_completion_is_retried() -> None:
    from langchain_core.messages import AIMessage

    from tests.fakes import ScriptedChatModel as Base

    class Truncating(Base):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
            result = super()._generate(messages, stop, run_manager, **kwargs)
            message = result.generations[0].message
            if not message.content:
                result.generations[0].message = AIMessage(
                    "", response_metadata={"finish_reason": "length"}
                )
            return result

    model = Truncating(responder=replies("", "جلسه به پنجشنبه منتقل شد."))
    completion = LLMClient(model).complete("sys", "user", max_tokens=300)
    assert completion.text == "جلسه به پنجشنبه منتقل شد."
    assert [kw["max_tokens"] for kw in model.call_kwargs] == [300, 600]


def test_blank_values_in_env_mean_unset() -> None:
    settings = Settings(
        _env_file=None, llm_api_key="  ", dashboard_password="", llm_fallback_model=""
    )
    assert settings.llm_api_key is None
    assert settings.dashboard_password is None
    assert settings.llm_fallback_model is None
    with pytest.raises(ConfigurationError):
        build_llm(settings)


def test_build_llm_requires_key() -> None:
    with pytest.raises(ConfigurationError):
        build_llm(Settings(_env_file=None, llm_api_key=None))
