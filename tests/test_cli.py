import json

import pytest
from typer.testing import CliRunner

from skill_agent import cli
from skill_agent.agent import Agent
from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from tests.fakes import ScriptedChatModel, replies

runner = CliRunner()


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = json.dumps({"skills": [{"skill": "general_chat"}], "confidence": 0.9})
    model = ScriptedChatModel(responder=replies(decision, "Hello there!"))
    agent = Agent(LLMClient(model), Settings(_env_file=None))
    monkeypatch.setattr(cli, "_agent", lambda: agent)


def test_skills_lists_registry() -> None:
    result = runner.invoke(cli.app, ["skills"])
    assert result.exit_code == 0
    for name in ("summarizer", "translator", "calculator", "general_chat"):
        assert name in result.output


def test_ask_prints_answer_and_trace(fake_agent: None) -> None:
    result = runner.invoke(cli.app, ["ask", "hi"])
    assert result.exit_code == 0
    assert "Hello there!" in result.output
    assert "general_chat" in result.output and "router" in result.output


def test_ask_json(fake_agent: None) -> None:
    result = runner.invoke(cli.app, ["ask", "hi", "--json"])
    payload = json.loads(result.output)
    assert payload["answer"] == "Hello there!"
    assert payload["decision"]["skills"][0]["skill"] == "general_chat"


def test_missing_key_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, llm_api_key=None)
    monkeypatch.setattr("skill_agent.agent.get_settings", lambda: settings)
    result = runner.invoke(cli.app, ["ask", "hi"])
    assert result.exit_code == 2
    assert "No API key configured" in result.output


def test_config_masks_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, llm_api_key="sk-secret-value")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    result = runner.invoke(cli.app, ["config"])
    assert result.exit_code == 0
    assert "llm_model" in result.output
    assert "sk-secret-value" not in result.output
