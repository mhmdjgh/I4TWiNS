import json

import pytest

from skill_agent.config import Settings
from skill_agent.llm import LLMClient, reasoning_switch
from skill_agent.skills import SkillTask
from skill_agent.skills.calculator import Calculator, is_word_problem
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


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("یک مغازه ۱۲۰ عدد مداد دارد. اگر ۳۵ درصد آن‌ها را بفروشد و بعد ۲۰ عدد دیگر بخرد؟", True),
        ("A class has 30 students; 6 leave and then 4 join. How many now?", True),
        ("What is (17.5 * 42) / 3 + 2^10?", False),
        ("۲۵ درصد از ۸۴۰ هزار تومان چقدر میشه؟", False),
        ("what is 120 - 35 + 20?", False),
    ],
)
def test_word_problem_detection(prompt: str, expected: bool) -> None:
    assert is_word_problem(prompt) is expected


def test_word_problems_get_a_little_reasoning() -> None:
    plan = json.dumps({"problems": [{"label": "pencils", "expression": "120 - 42 + 20"}]})
    model = ScriptedChatModel(responder=replies(plan, plan))
    llm = LLMClient(model, reasoning_switch=reasoning_switch("openai"), reasoning_allowance=500)
    calculator = Calculator(llm, Settings(_env_file=None))

    def task(prompt: str) -> SkillTask:
        return SkillTask(step=0, skill="calculator", instruction="", prompt=prompt, language="en")

    calculator.run(task("A shop has 120 pencils, sells 42 and buys 20 more. How many now?"))
    calculator.run(task("What is 120 - 42 + 20?"))

    assert model.call_kwargs[0]["extra_body"] == {"reasoning_effort": "low"}
    assert "extra_body" not in model.call_kwargs[1]
