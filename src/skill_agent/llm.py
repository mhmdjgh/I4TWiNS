"""Thin wrapper around a LangChain chat model.

Everything in the agent talks to the model through `LLMClient`, which gives us one place for
provider quirks (no system role, JSON mode), token accounting, and validated structured output.
"""

from __future__ import annotations

import re
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
    ) -> None:
        self._model = model
        self._system_role = system_role
        self._json_mode = json_mode
        self._max_repairs = max_repairs

    def _messages(self, system: str, user: str) -> list[BaseMessage]:
        if self._system_role:
            return [SystemMessage(system), HumanMessage(user)]
        return [HumanMessage(f"{system}\n\n---\n\n{user}")]

    def _invoke(self, messages: list[BaseMessage], **kwargs: Any) -> AIMessage | BaseMessage:
        return self._model.invoke(messages, **{k: v for k, v in kwargs.items() if v is not None})

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Completion:
        reply = self._invoke(
            self._messages(system, user), max_tokens=max_tokens, temperature=temperature
        )
        return Completion(_message_text(reply), _usage_of(reply))

    def structured(
        self,
        system: str,
        user: str,
        schema: type[M],
        *,
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> tuple[M, Usage]:
        """Ask for a JSON object and validate it against `schema`.

        On a parse/validation failure the error is sent back to the model once so it can repair
        its own answer; small models fix most formatting slips this way.
        """
        messages = self._messages(system, user)
        extra = {"response_format": {"type": "json_object"}} if self._json_mode else {}
        usage = Usage()
        error: Exception | None = None

        for _ in range(self._max_repairs + 1):
            reply = self._invoke(messages, max_tokens=max_tokens, temperature=0.0, **extra)
            usage += _usage_of(reply)
            text = _message_text(reply)
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

    def chat_model(name: str) -> BaseChatModel:
        return ChatOpenAI(
            model=name,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            default_headers={
                "HTTP-Referer": "https://github.com/mhmdjgh/I4TWiNS",
                "X-Title": "skill-agent",
            },
        )

    model: Runnable[LanguageModelInput, BaseMessage] = chat_model(settings.llm_model)
    if settings.llm_fallback_model:
        model = model.with_fallbacks([chat_model(settings.llm_fallback_model)])

    return LLMClient(model, system_role=settings.llm_system_role, json_mode=settings.llm_json_mode)
