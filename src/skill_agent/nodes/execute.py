"""Skill execution nodes and the edges that schedule them.

Two-skill requests run in one of two shapes, chosen by the router:

* parallel   - independent tasks; both nodes are started in the same step with `Send`, each with
               its own isolated input, and their results are merged by the `results` reducer.
* sequential - the second skill works on the first one's output; after the first node finishes,
               `after_skill` sends only that output (not the whole state) to the next node.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from time import perf_counter
from typing import Any, TypedDict

from langgraph.types import Send

from skill_agent.config import Settings
from skill_agent.context.budget import ContextBudget
from skill_agent.context.chunking import split_instruction
from skill_agent.context.tokens import excerpt
from skill_agent.skills.base import Skill, SkillTask
from skill_agent.state import AgentState, SkillResult, TraceEvent

log = logging.getLogger(__name__)

COMPOSE = "compose"
CLARIFY = "clarify"


class SkillInput(TypedDict):
    task: SkillTask


def make_skill_node(skill: Skill) -> Callable[[SkillInput], dict[str, Any]]:
    def run_skill(payload: SkillInput) -> dict[str, Any]:
        task = payload["task"]
        start = perf_counter()
        try:
            output = skill.run(task)
        except Exception as exc:
            # One failing skill must not take down the other branch or the whole request.
            log.warning(
                "skill %s failed: %s", skill.name, exc, exc_info=log.isEnabledFor(logging.DEBUG)
            )
            result = SkillResult(step=task.step, skill=skill.name, error=str(exc) or repr(exc))
            usage_in = usage_out = 0
            detail = f"failed: {result.error}"
        else:
            result = SkillResult(step=task.step, skill=skill.name, output=output)
            usage_in, usage_out = output.usage.input_tokens, output.usage.output_tokens
            detail = "; ".join(
                [
                    f"step {task.step + 1}",
                    *output.notes,
                    *(f"tool {c.name}" for c in output.tool_calls),
                ]
            )
        event = TraceEvent(
            node=skill.name,
            elapsed_ms=(perf_counter() - start) * 1000,
            input_tokens=usage_in,
            output_tokens=usage_out,
            detail=detail,
        )
        return {"results": [result], "trace": [event]}

    run_skill.__name__ = f"run_{skill.name}"
    return run_skill


def _verbatim_in(span: str, text: str) -> bool:
    def squash(value: str) -> str:
        return " ".join(value.split()).strip(" \"'«»“”")

    return bool(squash(span)) and squash(span) in " ".join(text.split())


_QUOTED = re.compile(r"«([^»]+)»|“([^”]+)”|\"([^\"]+)\"|(?<!\w)'([^']+)'(?!\w)")


def _quoted(text: str) -> str | None:
    """The first quoted passage of a message, if there is exactly one."""
    spans = [next(g for g in match.groups() if g) for match in _QUOTED.finditer(text)]
    return spans[0].strip() if len(spans) == 1 and spans[0].strip() else None


class Scheduler:
    def __init__(self, settings: Settings) -> None:
        self.budget = ContextBudget.from_settings(settings)

    def task(self, state: AgentState, step: int, input_text: str | None = None) -> SkillTask:
        decision = state["decision"]
        planned = decision.skills[step]
        max_output = self.budget.output_per_step(
            len(decision.skills), chained=decision.mode == "sequential"
        )
        prompt = state["text"]
        if input_text is not None:
            # A chained step gets the previous output plus the user's instruction only. With the
            # original text also present, a small model may work on that instead.
            instruction, _ = split_instruction(prompt)
            prompt = instruction or excerpt(prompt, 200)
        else:
            if planned.input and _verbatim_in(planned.input, prompt):
                # The router pinned the part of a multi-task prompt that belongs to this skill.
                # It is used only if it really occurs in the message, so it cannot be invented.
                input_text = planned.input
            elif decision.mode == "parallel" and planned.skill == "translator":
                # The router does not always pin the span. "Translate 'X' ..., and ..." quotes
                # the text to translate; without that boundary the rest gets translated too.
                input_text = _quoted(prompt)
            if input_text is not None:
                # With its own span, a skill sees its instruction instead of the whole message;
                # otherwise a small model also works on the other task's part of the prompt.
                prompt = planned.instruction or excerpt(prompt, 200)
        return SkillTask(
            step=step,
            skill=planned.skill,
            instruction=planned.instruction,
            prompt=prompt,
            language=decision.response_language,
            target_language=planned.target_language,
            input_text=input_text,
            max_output_tokens=max_output,
        )

    def dispatch(self, state: AgentState) -> str | list[Send]:
        decision = state["decision"]
        if decision.needs_clarification:
            return CLARIFY
        if decision.mode == "sequential":
            return [Send(decision.skills[0].skill, {"task": self.task(state, 0)})]
        return [
            Send(step.skill, {"task": self.task(state, i)})
            for i, step in enumerate(decision.skills)
        ]

    def after_skill(self, state: AgentState) -> str | list[Send]:
        decision = state["decision"]
        results = sorted(state.get("results", []), key=lambda r: r.step)
        if decision.mode != "sequential" or len(results) >= len(decision.skills):
            return COMPOSE
        last = results[-1]
        if not last.ok or last.output is None:
            return COMPOSE
        nxt = len(results)
        task = self.task(state, nxt, input_text=last.output.text)
        return [Send(decision.skills[nxt].skill, {"task": task})]
