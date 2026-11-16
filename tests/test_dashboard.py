import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from skill_agent.agent import Agent
from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from tests.fakes import ScriptedChatModel, replies

DASHBOARD = Path(__file__).parent.parent / "dashboard"
APP = str(DASHBOARD / "app.py")
sys.path.insert(0, str(DASHBOARD))  # the dashboard's modules import each other by name


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


def test_chat_answers_and_shows_the_pipeline(scripted_agent: None) -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert any("One prompt" in block.value for block in app.get("html") if hasattr(block, "value"))

    app.chat_input[0].set_value("۲۵ درصد از ۸۴۰ چند میشه؟").run()

    assert not app.exception
    assert any("**210**" in m.value for m in app.markdown)
    html = " ".join(str(getattr(block, "value", "")) for block in app.get("html"))
    assert "sa-steps" in html and "Calculator" in html


def test_persian_interface_switches_to_rtl(scripted_agent: None) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["ui_lang"] = "fa"
    app.run()
    assert not app.exception
    html = " ".join(str(getattr(block, "value", "")) for block in app.get("html"))
    assert "direction: rtl" in html
    assert "یک پیام، اسکیل‌های درست." in html


@pytest.mark.parametrize(
    ("page", "expected"), [("architecture_page", "sa-flow"), ("evaluation_page", "sa-case")]
)
def test_pages_render(scripted_agent: None, page: str, expected: str) -> None:
    def script(module: str) -> None:
        import importlib

        import theme

        theme.apply("en")
        importlib.import_module(module).render()

    app = AppTest.from_function(script, args=(page,), default_timeout=30).run()
    assert not app.exception
    html = " ".join(str(getattr(block, "value", "")) for block in app.get("html"))
    assert expected in html
