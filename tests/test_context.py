from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import BaseMessage

from skill_agent.config import Settings
from skill_agent.context.budget import ContextBudget
from skill_agent.context.chunking import chunk_text, split_instruction
from skill_agent.context.shortlist import Shortlister
from skill_agent.context.tokens import estimate_tokens, excerpt
from skill_agent.llm import LLMClient
from skill_agent.nodes.router import Router
from skill_agent.skills import Skill, SkillCard, SkillOutput, SkillRegistry, SkillTask, registry
from skill_agent.skills.summarizer import Summarizer
from skill_agent.skills.translator import Translator
from tests.fakes import ScriptedChatModel, replies

PERSIAN_SENTENCE = "هوش مصنوعی در سال‌های اخیر پیشرفت چشمگیری داشته است. "
ENGLISH_SENTENCE = "Artificial intelligence has advanced remarkably in recent years. "


class TestTokens:
    def test_persian_costs_more_per_character(self) -> None:
        assert estimate_tokens("abcd" * 10) == 10
        assert estimate_tokens("سلام" * 10) == 20

    def test_short_text_is_untouched(self) -> None:
        text = "translate: hello"
        assert excerpt(text, 100) is text

    def test_long_text_keeps_head_and_tail(self) -> None:
        text = "INSTRUCTION " + ENGLISH_SENTENCE * 200 + " END"
        cut = excerpt(text, 200)
        assert cut.startswith("INSTRUCTION") and cut.endswith("END")
        assert "tokens omitted" in cut
        assert estimate_tokens(cut) <= 220


class TestChunking:
    @pytest.mark.parametrize("sentence", [PERSIAN_SENTENCE, ENGLISH_SENTENCE])
    def test_chunks_respect_budget_and_keep_content(self, sentence: str) -> None:
        text = "\n\n".join(sentence * 8 for _ in range(6))
        chunks = chunk_text(text, 150)
        assert len(chunks) > 1
        assert all(estimate_tokens(c) <= 150 for c in chunks)
        assert "".join(text.split()) == "".join("".join(chunks).split())

    def test_chunks_end_on_sentence_boundaries(self) -> None:
        text = ("آیا این جمله پرسشی است؟ بله همین‌طور است. " * 40).strip()
        for chunk in chunk_text(text, 60)[:-1]:
            assert chunk.endswith(("؟", "."))

    def test_unpunctuated_run_is_split_by_words(self) -> None:
        chunks = chunk_text("word " * 500, 50)
        assert all(estimate_tokens(c) <= 50 for c in chunks)

    @pytest.mark.parametrize(
        ("prompt", "expected"),
        [
            ("Summarize this: long text here", ("Summarize this", "long text here")),
            ("این متن را خلاصه کن:\nمتن طولانی", ("این متن را خلاصه کن", "متن طولانی")),
            ("just a sentence without separator", ("", "just a sentence without separator")),
            ("ends with colon:", ("", "ends with colon:")),
        ],
    )
    def test_split_instruction(self, prompt: str, expected: tuple[str, str]) -> None:
        assert split_instruction(prompt) == expected


class TestBudget:
    def test_parallel_steps_share_the_output_budget(self) -> None:
        budget = ContextBudget(window=16_000, max_output=1_200, total_output=2_000)
        assert budget.output_per_step(1, chained=False) == 1_200
        assert budget.output_per_step(2, chained=False) == 1_000
        assert budget.output_per_step(2, chained=True) == 1_200
        assert budget.output_per_step(10, chained=False) == 256

    def test_fits(self) -> None:
        budget = ContextBudget(window=2_000, max_output=500, total_output=1_000)
        assert budget.fits("system", "short", 500)
        assert not budget.fits("system", ENGLISH_SENTENCE * 200, 500)


def synthetic_skill(i: int) -> type[Skill]:
    topics = ["weather", "stocks", "recipes", "flights", "music", "movies", "sports", "news"]
    topic = topics[i % len(topics)]

    class Synthetic(Skill):
        card = SkillCard(
            name=f"{topic}_{i}",
            summary=f"Answers questions about {topic} (variant {i}).",
            use_when=f"the user asks about {topic}",
            examples=(f"tell me about {topic}",),
            keywords=(topic,),
        )

        def run(self, task: SkillTask) -> SkillOutput:
            return SkillOutput(text=topic)

    return Synthetic


def big_registry(n_extra: int) -> SkillRegistry:
    big = SkillRegistry()
    for skill_cls in registry:
        big.register(skill_cls)
    for i in range(n_extra):
        big.register(synthetic_skill(i))
    return big


class TestShortlist:
    def test_small_catalogue_is_not_filtered(self) -> None:
        shortlister = Shortlister(registry.cards(), "general_chat", threshold=8, top_k=3)
        assert len(shortlister.select("anything")) == len(registry)

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("please translate this into English: سلام", "translator"),
            ("این متن را خلاصه کن: ...", "summarizer"),
            ("۲۵ درصد از ۸۴۰ چند میشه؟", "calculator"),
            ("what's the weather like?", "weather_0"),
        ],
    )
    def test_relevant_skill_survives_in_large_catalogue(self, query: str, expected: str) -> None:
        cards = big_registry(50).cards()
        selected = Shortlister(cards, "general_chat", threshold=8, top_k=6).select(query)
        names = [card.name for card in selected]
        assert expected in names and "general_chat" in names
        assert len(selected) <= 7

    def test_router_prompt_size_is_bounded(self) -> None:
        settings = Settings(_env_file=None, shortlist_threshold=8, shortlist_top_k=6)
        llm = LLMClient(ScriptedChatModel(responder=replies()))
        sizes = []
        for extra in (10, 50, 200):
            router = Router(llm, big_registry(extra), settings)
            cards = router.shortlister.select("translate this to English: سلام")
            sizes.append(estimate_tokens(router.build_prompt(cards)))
        assert max(sizes) - min(sizes) < 100  # grows with top_k, not with the catalogue


def recording_model() -> tuple[ScriptedChatModel, list[str]]:
    seen: list[str] = []

    def respond(messages: list[BaseMessage]) -> str:
        seen.append(str(messages[-1].content))
        return f"part-{len(seen)}"

    return ScriptedChatModel(responder=respond), seen


def long_task(skill: str, **extra: Any) -> SkillTask:
    body = ("\n\n".join(ENGLISH_SENTENCE * 10 for _ in range(30))).strip()
    fields = {
        "step": 0,
        "skill": skill,
        "instruction": "",
        "prompt": f"Process this text:\n{body}",
        "language": "en",
        "max_output_tokens": 300,
    }
    return SkillTask.model_validate(fields | extra)


SMALL_WINDOW = {"context_window": 2_000, "chunk_tokens": 400, "max_output_tokens": 300}


def test_long_text_is_summarized_with_map_reduce() -> None:
    model, seen = recording_model()
    settings = Settings(_env_file=None, **SMALL_WINDOW)
    output = Summarizer(LLMClient(model), settings).run(long_task("summarizer"))

    assert output.notes and output.notes[0].startswith("map-reduce over")
    assert len(seen) >= 3
    assert all(estimate_tokens(message) < settings.context_window for message in seen)
    assert "Merge them into a single summary" in seen[-1]
    assert output.text == f"part-{len(seen)}"


def test_long_text_is_translated_in_order() -> None:
    model, seen = recording_model()
    settings = Settings(_env_file=None, **SMALL_WINDOW)
    output = Translator(LLMClient(model), settings).run(long_task("translator"))

    pieces = output.text.split("\n\n")
    assert pieces == [f"part-{i}" for i in range(1, len(seen) + 1)]
    assert "part 1 of" in seen[0]


def test_short_text_takes_single_call() -> None:
    model, seen = recording_model()
    task = SkillTask(
        step=0,
        skill="summarizer",
        instruction="",
        prompt=f"Summarize: {ENGLISH_SENTENCE * 2}",
        language="en",
    )
    Summarizer(LLMClient(model), Settings(_env_file=None)).run(task)
    assert len(seen) == 1
