import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from skill_agent.agent import Agent
from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from tests.fakes import ScriptedChatModel, replies

APP = str(Path(__file__).parent.parent / "dashboard" / "app.py")


@pytest.fixture
def scripted_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = json.dumps(
        {
            "skills": [{"skill": "calculator", "instruction": "compute"}],
            "confidence": 0.95,
            "response_language": "fa",
        }
    )
    plan = json.dumps({"problems": [{"label": "۲۵ درصد از ۸۴۰", "expression": "840 * 25 / 100"}]})

    def build(cls: type[Agent], settings: Settings | None = None) -> Agent:
        model = ScriptedChatModel(responder=replies(decision, plan))
        return Agent(LLMClient(model), Settings(_env_file=None))

    monkeypatch.setattr(Agent, "from_settings", classmethod(build))


def test_dashboard_runs_a_prompt(scripted_agent: None) -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Playground", "Architecture", "Evaluation"]

    app.text_area(key="prompt").input("۲۵ درصد از ۸۴۰ چند میشه؟").run()
    next(b for b in app.button if b.label == "Run").click().run()

    assert not app.exception
    assert any("**210**" in m.value for m in app.markdown)
    assert any(metric.label == "Skills" and metric.value == "calculator" for metric in app.metric)
