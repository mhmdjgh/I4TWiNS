from langchain_core.messages import BaseMessage

from skill_agent.config import Settings
from skill_agent.llm import LLMClient, reasoning_switch
from skill_agent.skills import SkillTask
from skill_agent.skills.general_chat import GeneralChat
from skill_agent.skills.summarizer import Summarizer
from tests.fakes import ScriptedChatModel, replies

SOURCE = (
    "Solar power has become one of the cheapest sources of electricity in the world. Falling "
    "panel prices and better batteries have led many countries to raise the share of "
    "renewables in their energy mix. Storing energy for nights and cloudy days is still a "
    "serious challenge, and experts believe smart grids could solve part of the problem."
)


def summarize(*model_replies: str) -> tuple[str, list[str], ScriptedChatModel]:
    model = ScriptedChatModel(responder=replies(*model_replies))
    task = SkillTask(
        step=0, skill="summarizer", instruction="", prompt=f"Summarize: {SOURCE}", language="en"
    )
    output = Summarizer(LLMClient(model), Settings(_env_file=None)).run(task)
    return output.text, output.notes, model


def test_overlong_summary_is_shortened_once() -> None:
    text, notes, model = summarize(SOURCE, "Solar is cheap; storage is the open problem.")
    assert text == "Solar is cheap; storage is the open problem."
    assert notes and notes[0].startswith("shortened after check")
    assert "Rewrite it in at most" in str(model.calls[1][-1].content)


def test_concise_summary_is_kept() -> None:
    _, notes, model = summarize("Solar is cheap, but storing energy is still hard.")
    assert len(model.calls) == 1 and notes == []


def test_general_chat_names_the_reply_language_and_reasons() -> None:
    def respond(messages: list[BaseMessage]) -> str:
        return "ok"

    model = ScriptedChatModel(responder=respond)
    llm = LLMClient(model, reasoning_switch=reasoning_switch("openai"), reasoning_allowance=500)
    task = SkillTask(
        step=0,
        skill="general_chat",
        instruction="",
        prompt="Write a short poem about the sea.",
        language="en",
        max_output_tokens=300,
    )
    GeneralChat(llm, Settings(_env_file=None)).run(task)

    assert "Reply in English" in str(model.calls[0][0].content)
    assert model.call_kwargs[0]["extra_body"] == {"reasoning_effort": "low"}
    assert model.call_kwargs[0]["max_tokens"] == 800


def test_reasoning_off_override_skips_padding() -> None:
    model = ScriptedChatModel(responder=replies("ok"))
    llm = LLMClient(
        model,
        reasoning_tokens=1000,
        reasoning_switch=reasoning_switch("openrouter"),
        reasoning_allowance=1000,
    )
    llm.complete("sys", "user", max_tokens=200, reasoning="off")
    assert model.call_kwargs[0]["extra_body"] == {"reasoning": {"enabled": False}}
    assert model.call_kwargs[0]["max_tokens"] == 200
