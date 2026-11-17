from __future__ import annotations

import re

from pydantic import BaseModel, Field

from skill_agent.context.tokens import excerpt
from skill_agent.prompts import load_prompt, render
from skill_agent.skills.base import Skill, SkillCard, SkillOutput, SkillTask, ToolCall
from skill_agent.skills.registry import register_skill
from skill_agent.tools import FUNCTIONS, CalculationError, calculate
from skill_agent.tools.math_eval import MAX_EXPRESSION_CHARS


class MathProblem(BaseModel):
    label: str = Field(max_length=200)
    expression: str = Field(min_length=1, max_length=MAX_EXPRESSION_CHARS)


class MathPlan(BaseModel):
    problems: list[MathProblem] = Field(default_factory=list, max_length=5)
    note: str | None = None


_NUMBER = re.compile(r"[0-9۰-۹٠-٩]+(?:[.,٫٬][0-9۰-۹٠-٩]+)*")
_OPERATOR = re.compile(r"[+*/^×÷=]|\d\s*-\s*\d")


def is_word_problem(text: str) -> bool:
    """Three or more numbers and no math symbols: a story the model has to turn into math.

    Without reasoning the model got the sign of a step wrong in such stories ("then buys 20
    more" became "- 20"). Written expressions and "X% of Y" don't need it and stay fast.
    """
    return len(_NUMBER.findall(text)) >= 3 and not _OPERATOR.search(text)


_MESSAGES = {
    "en": {"failed": "could not compute", "nothing": "I couldn't find a calculation to perform."},
    "fa": {"failed": "محاسبه ممکن نشد", "nothing": "محاسبه‌ای در درخواست پیدا نکردم."},
}


@register_skill
class Calculator(Skill):
    """The LLM only translates the request into expressions; the `calculate` tool does the math.

    Splitting it this way means a number in the answer can only ever come from the tool, never
    from the model's guess, and it works with free models that lack native tool calling.
    """

    card = SkillCard(
        name="calculator",
        summary="Evaluates arithmetic and math with a real calculator tool.",
        use_when="the user asks for a numeric result: arithmetic, percentages, powers, roots, "
        "trigonometry, or a word problem that needs computing.",
        examples=("what is 15% of 240?", "جذر ۱۴۴ به علاوه ۲ به توان ۵", "(3+4)*12/7"),
        keywords=(
            "calculate",
            "compute",
            "math",
            "sum",
            "percent",
            "plus",
            "minus",
            "times",
            "divided",
            "sqrt",
            "root",
            "power",
            "equals",
            "how much",
            "حساب",
            "محاسبه",
            "جمع",
            "تفریق",
            "ضرب",
            "تقسیم",
            "درصد",
            "جذر",
            "توان",
            "چند میشه",
            "چقدر میشه",
        ),
        titles={"en": "Calculation", "fa": "محاسبه"},
    )

    def run(self, task: SkillTask) -> SkillOutput:
        system = render(load_prompt("calculator"), functions=", ".join(FUNCTIONS))
        text = excerpt(task.input_text or task.prompt, self.budget.input_room(system, 600))
        user = f"{text}\n\n(Focus: {task.instruction})" if task.instruction else text
        # Decided on the user's words only: the router's instruction may add symbols ("120 - 35%").
        reasoning = "low" if is_word_problem(text) else None
        plan, usage = self.llm.structured(
            system, user, MathPlan, max_tokens=600, reasoning=reasoning
        )
        messages = _MESSAGES["fa" if task.language == "fa" else "en"]
        if not plan.problems:
            text = messages["nothing"] + (f" {plan.note}" if plan.note else "")
            return SkillOutput(text=text, usage=usage)

        calls: list[ToolCall] = []
        lines: list[str] = []
        for problem in plan.problems:
            args = {"expression": problem.expression}
            try:
                result = calculate.invoke(args)
            except CalculationError as exc:
                calls.append(
                    ToolCall(name=calculate.name, arguments=args, output=str(exc), ok=False)
                )
                lines.append(f"- {problem.label}: {messages['failed']} ({exc})")
                continue
            calls.append(ToolCall(name=calculate.name, arguments=args, output=result))
            lines.append(f"- {problem.label}: `{problem.expression}` = **{result}**")

        return SkillOutput(text="\n".join(lines), usage=usage, tool_calls=calls)
