from __future__ import annotations

from dataclasses import dataclass

from skill_agent.config import Settings
from skill_agent.context.tokens import estimate_tokens

_MESSAGE_OVERHEAD = 200  # role markers, chat template, safety margin


@dataclass(frozen=True)
class ContextBudget:
    window: int
    max_output: int
    total_output: int

    @classmethod
    def from_settings(cls, settings: Settings) -> ContextBudget:
        return cls(
            settings.context_window, settings.max_output_tokens, settings.total_output_budget
        )

    def output_per_step(self, steps: int, *, chained: bool) -> int:
        """Output tokens each skill may use.

        Parallel results all end up in the final answer, so they share `total_output`.
        In a chain only the last output is returned and every intermediate output is bounded
        by `max_output`, so step N+1's input can never outgrow the window.
        """
        if chained or steps <= 1:
            return self.max_output
        return max(256, min(self.max_output, self.total_output // steps))

    def input_room(self, system_prompt: str, max_output: int) -> int:
        return self.window - estimate_tokens(system_prompt) - max_output - _MESSAGE_OVERHEAD

    def fits(self, system_prompt: str, message: str, max_output: int) -> bool:
        return estimate_tokens(message) <= self.input_room(system_prompt, max_output)
