import pytest

from skill_agent.config import Settings
from skill_agent.prompts import render
from skill_agent.skills import (
    Skill,
    SkillCard,
    SkillOutput,
    SkillRegistry,
    SkillTask,
    UnknownSkillError,
)
from tests.fakes import ScriptedChatModel, replies


def make_skill(name: str) -> type[Skill]:
    class _Echo(Skill):
        card = SkillCard(name=name, summary=f"{name} skill", use_when="testing")

        def run(self, task: SkillTask) -> SkillOutput:
            return SkillOutput(text=task.prompt)

    return _Echo


def test_register_and_lookup() -> None:
    reg = SkillRegistry(fallback="echo")
    skill_cls = reg.register(make_skill("echo"))
    assert reg.get("echo") is skill_cls
    assert "echo" in reg and len(reg) == 1
    assert reg.names == ("echo",)
    assert [card.name for card in reg.cards()] == ["echo"]


def test_duplicate_and_invalid_names_rejected() -> None:
    reg = SkillRegistry()
    reg.register(make_skill("echo"))
    with pytest.raises(ValueError, match="already registered"):
        reg.register(make_skill("echo"))
    with pytest.raises(ValueError, match="snake_case"):
        reg.register(make_skill("Bad-Name"))


def test_unknown_skill() -> None:
    with pytest.raises(UnknownSkillError):
        SkillRegistry().get("nope")


def test_instantiate_requires_fallback() -> None:
    from skill_agent.llm import LLMClient

    reg = SkillRegistry(fallback="general_chat")
    reg.register(make_skill("echo"))
    llm = LLMClient(ScriptedChatModel(responder=replies()))
    with pytest.raises(ValueError, match="fallback"):
        reg.instantiate(llm, Settings(_env_file=None))


def test_card_render_and_titles() -> None:
    card = SkillCard(
        name="summarizer",
        summary="Condenses text.",
        use_when="the user wants a shorter version",
        examples=("summarize this", "خلاصه کن", "tl;dr", "fourth"),
        titles={"en": "Summary", "fa": "خلاصه"},
    )
    rendered = card.render()
    assert rendered.startswith("- summarizer: Condenses text.")
    assert "fourth" not in rendered
    assert card.title("fa") == "خلاصه"
    assert card.title("de") == "Summary"


def test_render_placeholders() -> None:
    assert render('{"a": 1} {{ name }}', name="x") == '{"a": 1} x'
    with pytest.raises(KeyError):
        render("{{missing}}")
