from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Offline chat model whose reply is computed from the incoming messages."""

    responder: Callable[[list[BaseMessage]], str]
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    call_kwargs: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        self.call_kwargs.append(kwargs)
        message = AIMessage(
            self.responder(messages),
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def replies(*texts: str) -> Callable[[list[BaseMessage]], str]:
    """Responder that returns the given texts in order."""
    queue = list(texts)
    return lambda _messages: queue.pop(0)
