import json

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.skills import SkillTask
from skill_agent.skills.calculator import Calculator
from tests.fakes import ScriptedChatModel, replies


def run_calculator(plan: dict[str, object], prompt: str, language: str = "en") -> tuple[str, list]:
    llm = LLMClient(ScriptedChatModel(responder=replies(json.dumps(plan, ensure_ascii=False))))
    skill = Calculator(llm, Settings(_env_file=None))
    task = SkillTask(step=0, skill="calculator", instruction="", prompt=prompt, language=language)
    output = skill.run(task)
    return output.text, output.tool_calls


def test_result_comes_from_tool_not_model() -> None:
    plan = {"problems": [{"label": "17% of 2,350", "expression": "2350 * 17 / 100"}]}
    text, calls = run_calculator(plan, "what is 17% of 2,350?")
    assert "**399.5**" in text
    assert [(c.name, c.arguments, c.output, c.ok) for c in calls] == [
        ("calculate", {"expression": "2350 * 17 / 100"}, "399.5", True)
    ]


def test_multiple_problems_and_tool_errors() -> None:
    plan = {
        "problems": [
            {"label": "جذر ۱۴۴", "expression": "sqrt(144)"},
            {"label": "تقسیم بر صفر", "expression": "1 / 0"},
        ]
    }
    text, calls = run_calculator(plan, "جذر ۱۴۴ و یک تقسیم بر صفر", language="fa")
    assert "**12**" in text
    assert "محاسبه ممکن نشد" in text
    assert [c.ok for c in calls] == [True, False]


def test_nothing_to_calculate() -> None:
    text, calls = run_calculator({"problems": [], "note": "No numbers given."}, "hello")
    assert "couldn't find a calculation" in text and "No numbers given." in text
    assert calls == []
