"""Thin wrapper around a LangChain chat model.

Everything in the agent talks to the model through `LLMClient`, which gives us one place for
provider quirks (no system role, JSON mode), token accounting, and validated structured output.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from skill_agent.config import Settings

M = TypeVar("M", bound=BaseModel)

_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ConfigurationError(RuntimeError):
    pass


class StructuredOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


@dataclass(frozen=True)
class Completion:
    text: str
    usage: Usage


def extract_json(text: str) -> str:
    """Pull the first JSON object out of a model reply (tolerates code fences and chatter)."""
    fenced = _CODE_FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the reply")
    return text[start : end + 1]


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = [block.get("text", "") if isinstance(block, dict) else str(block) for block in content]
    return "".join(parts).strip()


ReasoningSwitch = Callable[[str], dict[str, Any] | None]


def reasoning_switch(param: str) -> ReasoningSwitch:
    """Request fields that set a reasoning level ("off", "low", ...), per provider dialect.

    OpenRouter takes a `reasoning` object, OpenAI-style gateways take `reasoning_effort`, and
    some reject both ("none": send nothing and leave the model at its default).
    """

    def body(level: str) -> dict[str, Any] | None:
        if param == "openrouter":
            return {"reasoning": {"enabled": False} if level == "off" else {"effort": level}}
        if param == "openai":
            return {"reasoning_effort": "none" if level == "off" else level}
        return None

    return body


def _is_truncation(exc: Exception) -> bool:
    # openai.LengthFinishReasonError, raised when a JSON-mode reply hits max_tokens. Matched by
    # name so this module does not depend on a specific provider SDK.
    return type(exc).__name__ == "LengthFinishReasonError"


def _usage_of(message: BaseMessage) -> Usage:
    meta = getattr(message, "usage_metadata", None) or {}
    return Usage(int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0)))


class LLMClient:
    def __init__(
        self,
        model: Runnable[LanguageModelInput, BaseMessage],
        *,
        system_role: bool = True,
        json_mode: bool = False,
        max_repairs: int = 1,
        reasoning_tokens: int = 0,
        reasoning_switch: ReasoningSwitch | None = None,
        reasoning_allowance: int = 1_024,
    ) -> None:
        self._model = model
        self._system_role = system_role
        self._json_mode = json_mode
        self._max_repairs = max_repairs
        # Reasoning models spend hidden tokens before answering, and those count against
        # max_tokens. Callers size max_tokens for the visible answer; this pads it.
        self._reasoning_tokens = reasoning_tokens
        self._reasoning_switch = reasoning_switch
        self._reasoning_allowance = reasoning_allowance

    def _messages(self, system: str, user: str) -> list[BaseMessage]:
        if self._system_role:
            return [SystemMessage(system), HumanMessage(user)]
        return [HumanMessage(f"{system}\n\n---\n\n{user}")]

    def _invoke(
        self, messages: list[BaseMessage], reasoning: str | None = None, **kwargs: Any
    ) -> AIMessage | BaseMessage:
        padding = self._reasoning_tokens
        if reasoning is not None and self._reasoning_switch is not None:
            body = self._reasoning_switch(reasoning)
            if body is not None:
                kwargs["extra_body"] = body
            switched_off = reasoning == "off" and body is not None
            padding = 0 if switched_off else self._reasoning_allowance
        if kwargs.get("max_tokens"):
            kwargs["max_tokens"] += padding
        return self._model.invoke(messages, **{k: v for k, v in kwargs.items() if v is not None})

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: str | None = None,
    ) -> Completion:
        """Plain completion. `reasoning` overrides the default reasoning level for this call."""
        messages = self._messages(system, user)
        options: dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": reasoning,
        }
        reply = self._invoke(messages, **options)
        usage = _usage_of(reply)
        text = _message_text(reply)
        if not text and max_tokens and reply.response_metadata.get("finish_reason") == "length":
            # A reasoning model can spend the whole allowance thinking and return nothing.
            reply = self._invoke(messages, **(options | {"max_tokens": max_tokens * 2}))
            usage += _usage_of(reply)
            text = _message_text(reply)
        return Completion(text, usage)

    def structured(
        self,
        system: str,
        user: str,
        schema: type[M],
        *,
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        reasoning: str | None = None,
    ) -> tuple[M, Usage]:
        """Ask for a JSON object and validate it against `schema`.

        On a parse/validation failure the error is sent back to the model once so it can repair
        its own answer; small models fix most formatting slips this way. A reply cut off by the
        token limit is retried with twice the limit instead.
        """
        messages = self._messages(system, user)
        extra: dict[str, Any] = (
            {"response_format": {"type": "json_object"}} if self._json_mode else {}
        )
        extra["reasoning"] = reasoning
        usage = Usage()
        error: Exception | None = None

        for _ in range(self._max_repairs + 1):
            try:
                reply = self._invoke(messages, max_tokens=max_tokens, temperature=0.0, **extra)
            except Exception as exc:
                if not _is_truncation(exc):
                    raise
                error, max_tokens = exc, max_tokens * 2 if max_tokens else None
                continue
            usage += _usage_of(reply)
            text = _message_text(reply)
            if reply.response_metadata.get("finish_reason") == "length" and max_tokens:
                max_tokens *= 2
            try:
                return schema.model_validate_json(extract_json(text), context=context), usage
            except ValueError as exc:  # pydantic's ValidationError is a ValueError too
                error = exc
                messages += [
                    AIMessage(text),
                    HumanMessage(
                        f"Your reply could not be used: {exc}\n"
                        "Answer again with only the corrected JSON object."
                    ),
                ]

        raise StructuredOutputError(f"model did not return valid {schema.__name__}: {error}")


def build_llm(settings: Settings) -> LLMClient:
    from langchain_openai import ChatOpenAI

    if settings.llm_api_key is None:
        raise ConfigurationError(
            "No API key configured. Set LLM_API_KEY (or OPENROUTER_API_KEY) in .env."
        )

    switch = reasoning_switch(settings.llm_reasoning_param)
    level = settings.llm_reasoning
    extra_body = switch(level)

    def chat_model(name: str) -> BaseChatModel:
        return ChatOpenAI(
            model=name,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            extra_body=extra_body,
            default_headers={
                "HTTP-Referer": "https://github.com/mhmdjgh/I4TWiNS",
                "X-Title": "skill-agent",
            },
        )

    model: Runnable[LanguageModelInput, BaseMessage] = chat_model(settings.llm_model)
    if settings.llm_fallback_model:
        model = model.with_fallbacks([chat_model(settings.llm_fallback_model)])

    # Without a way to switch reasoning off, budget for it as if it were on.
    reasoning_off = level == "off" and settings.llm_reasoning_param != "none"
    return LLMClient(
        model,
        system_role=settings.llm_system_role,
        json_mode=settings.llm_json_mode,
        reasoning_tokens=0 if reasoning_off else settings.reasoning_allowance,
        reasoning_switch=switch,
        reasoning_allowance=settings.reasoning_allowance,
    )
