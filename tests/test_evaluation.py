import json
from pathlib import Path

from langchain_core.messages import BaseMessage

from skill_agent.agent import Agent
from skill_agent.config import Settings
from skill_agent.evaluation import EvalCase, evaluate, is_correct, load_cases
from skill_agent.llm import LLMClient
from tests.fakes import ScriptedChatModel

DATASET = Path(__file__).parent.parent / "evals" / "dataset.yaml"


def case(**fields: object) -> EvalCase:
    base = {"id": "x", "category": "clear", "language": "en", "prompt": "p", "expected": []}
    return EvalCase.model_validate(base | fields)


def test_dataset_is_valid_and_varied() -> None:
    cases = load_cases(DATASET)
    assert 10 <= len(cases) <= 15
    assert len({c.id for c in cases}) == len(cases)
    assert {c.category for c in cases} == {"clear", "multi", "ambiguous", "no_skill"}
    assert {c.language for c in cases} == {"en", "fa"}
    known = {"summarizer", "translator", "calculator", "general_chat", "clarify"}
    assert all(set(c.expected) <= known for c in cases)


def test_correctness_ignores_order_and_honours_alternatives() -> None:
    multi = case(expected=["general_chat", "calculator"], accept=[["calculator"]])
    assert is_correct(multi, ["calculator", "general_chat"])
    assert is_correct(multi, ["calculator"])
    assert not is_correct(multi, ["general_chat"])


def test_report_metrics() -> None:
    routes = {
        "hi": {"skills": [{"skill": "general_chat"}]},
        "2+2": {"skills": [{"skill": "general_chat"}]},
        "sum and tr": {
            "skills": [{"skill": "summarizer"}, {"skill": "translator"}],
            "mode": "parallel",
        },
    }

    def respond(messages: list[BaseMessage]) -> str:
        prompt = str(messages[-1].content).removeprefix("Message:\n")
        return json.dumps(routes[prompt] | {"confidence": 0.9})

    agent = Agent(LLMClient(ScriptedChatModel(responder=respond)), Settings(_env_file=None))
    cases = [
        case(id="a", prompt="hi", expected=["general_chat"]),
        case(id="b", prompt="2+2", expected=["calculator"]),
        case(
            id="c",
            category="multi",
            prompt="sum and tr",
            expected=["summarizer", "translator"],
            mode="sequential",
        ),
    ]
    report = evaluate(agent, cases)

    assert [r.correct for r in report.results] == [True, False, True]
    assert report.results[2].mode_correct is False
    assert round(report.accuracy, 2) == 0.67
    assert report.by_category() == {"clear": (1, 2), "multi": (1, 1)}
    precision, recall, _ = report.per_label()["general_chat"]
    assert (precision, recall) == (0.5, 1.0)
    markdown = report.to_markdown()
    assert "Skill-detection accuracy: 67%" in markdown and "`b`" in markdown
