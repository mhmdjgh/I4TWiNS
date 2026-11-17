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


def test_password_gate(scripted_agent: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import access

    settings = Settings(_env_file=None, dashboard_password="open-sesame")
    monkeypatch.setattr(access, "get_settings", lambda: settings)

    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert len(app.chat_input) == 0  # nothing usable before signing in

    # Form fields are submitted together with the button, so fill in and click in one run.
    app.text_input[0].input("wrong")
    app.button[0].click().run()
    assert app.error and len(app.chat_input) == 0

    app.text_input[0].input("open-sesame")
    app.button[0].click().run()
    assert not app.exception
    assert len(app.chat_input) == 1


def test_no_password_means_no_gate(scripted_agent: None) -> None:
    import access

    assert access.password_ok("same", "same")
    assert not access.password_ok("same", "other")
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert len(app.chat_input) == 1


@pytest.mark.parametrize(("language", "direction"), [("fa", "rtl"), ("en", "ltr")])
def test_answer_direction_follows_answer_language(language: str, direction: str) -> None:
    from chat_page import answer_direction

    from skill_agent.agent import AgentResponse
    from skill_agent.routing import RoutingDecision

    decision = RoutingDecision(response_language=language)
    response = AgentResponse(prompt="p", answer="a", language="en", decision=decision)
    assert answer_direction(response) == direction


@pytest.mark.parametrize(
    ("page", "expected"), [("architecture_page", "sa-flow"), ("evaluation_page", "sa-case")]
)
def test_pages_render(scripted_agent: None, page: str, expected: str) -> None:
    def script(module: str) -> None:
        import importlib

        import theme

        theme.apply()
        importlib.import_module(module).render()

    app = AppTest.from_function(script, args=(page,), default_timeout=30).run()
    assert not app.exception
    html = " ".join(str(getattr(block, "value", "")) for block in app.get("html"))
    assert expected in html
