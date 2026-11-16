from langchain_core.messages import BaseMessage

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.skills import SkillTask
from skill_agent.skills.base import task_message
from skill_agent.skills.general_chat import GeneralChat
from skill_agent.skills.summarizer import Summarizer
from skill_agent.skills.translator import Translator
from tests.fakes import ScriptedChatModel


def echo_user(messages: list[BaseMessage]) -> str:
    return str(messages[-1].content)


def make_task(**overrides: object) -> SkillTask:
    fields: dict[str, object] = {
        "step": 0,
        "skill": "translator",
        "instruction": "translate the text to English",
        "prompt": "ترجمه کن: سلام دنیا",
        "language": "fa",
    }
    return SkillTask.model_validate(fields | overrides)


def test_task_message_fences_content() -> None:
    message = task_message(make_task(target_language="English"))
    assert message.startswith("<request>\nترجمه کن: سلام دنیا\n</request>")
    assert "Task: translate the text to English" in message
    assert "Target language: English" in message
    assert "<text>" not in message


def test_task_message_includes_previous_output() -> None:
    message = task_message(make_task(input_text="a short summary"))
    assert "<text>\na short summary\n</text>" in message


def test_text_skills_pass_output_budget() -> None:
    for skill_cls in (Summarizer, Translator, GeneralChat):
        model = ScriptedChatModel(responder=echo_user)
        skill = skill_cls(LLMClient(model), Settings(_env_file=None))
        output = skill.run(make_task(max_output_tokens=321))
        assert output.text
        assert model.call_kwargs[0]["max_tokens"] == 321


def test_general_chat_sends_raw_prompt() -> None:
    model = ScriptedChatModel(responder=echo_user)
    output = GeneralChat(LLMClient(model), Settings(_env_file=None)).run(make_task())
    assert output.text == "ترجمه کن: سلام دنیا"
