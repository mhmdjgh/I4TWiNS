import json

import pytest

from skill_agent.config import Settings
from skill_agent.llm import LLMClient
from skill_agent.skills import SkillTask
from skill_agent.skills.checks import translation_issues
from skill_agent.skills.summarizer import Summarizer
from skill_agent.skills.translator import Translator
from tests.fakes import ScriptedChatModel, replies

SOURCE = "The meeting has been moved to Thursday morning because the manager is travelling."


@pytest.mark.parametrize(
    ("source", "translation", "problem"),
    [
        (SOURCE, "جلسه به صبح جمعه منتقل شده است.", "«پنجشنبه»"),
        ("Pay 3,200 dollars by Monday.", "تا دوشنبه ۳۲۰ دلار بپردازید.", "3200"),
        ("جلسه پنج‌شنبه است.", "The meeting is on Friday.", "Thursday"),
        (SOURCE, "جلسه به صبح پنج‌شنبه postponed شده است.", "postponed"),
    ],
)
def test_detects_changed_facts(source: str, translation: str, problem: str) -> None:
    issues = translation_issues(source, translation)
    assert issues and problem in " ".join(issues)


@pytest.mark.parametrize(
    ("source", "translation"),
    [
        (SOURCE, "جلسه به صبح پنج‌شنبه منتقل شده است، چون مدیر در سفر است."),
        (SOURCE, "جلسه به صبح پنج شنبه منتقل شد."),
        ("Pay 3,200 dollars by Monday.", "تا دوشنبه ۳٬۲۰۰ دلار بپردازید."),
        ("جلسه شنبه و یکشنبه است.", "The meeting is on Saturday and Sunday."),
        ("Good morning!", "صبح بخیر!"),
        ("Rendez-vous jeudi.", "Meeting on Thursday."),
        ("Install Python from https://python.org", "پایتون را از https://python.org نصب کنید."),
        ("Ask Google about `pip install`.", "از Google درباره‌ی `pip install` بپرسید."),
    ],
)
def test_accepts_faithful_translations(source: str, translation: str) -> None:
    assert translation_issues(source, translation) == []


def test_translator_repairs_flagged_translation() -> None:
    model = ScriptedChatModel(
        responder=replies("جلسه به صبح جمعه منتقل شده است.", "جلسه به صبح پنج‌شنبه منتقل شده است.")
    )
    task = SkillTask(
        step=0,
        skill="translator",
        instruction="translate into Persian",
        prompt=f"Translate into Persian: {SOURCE}",
        language="en",
        target_language="Persian",
    )
    output = Translator(LLMClient(model), Settings(_env_file=None)).run(task)

    assert output.text == "جلسه به صبح پنج‌شنبه منتقل شده است."
    assert output.notes and "پنجشنبه" in output.notes[0]
    repair_message = str(model.calls[1][-1].content)
    assert "<translation>" in repair_message and "Thursday" in repair_message


def test_translator_skips_repair_when_clean() -> None:
    model = ScriptedChatModel(responder=replies("صبح بخیر!"))
    task = SkillTask(
        step=0, skill="translator", instruction="", prompt="Translate: Good morning!", language="en"
    )
    output = Translator(LLMClient(model), Settings(_env_file=None)).run(task)
    assert output.text == "صبح بخیر!" and len(model.calls) == 1 and output.notes == []


@pytest.mark.parametrize(
    ("prompt", "language", "expected"),
    [("اینو برام خلاصه کن", "fa", "لطفاً متنی"), ("summarize this", "en", "Please send")],
)
def test_summarizer_asks_for_missing_text(prompt: str, language: str, expected: str) -> None:
    model = ScriptedChatModel(responder=replies())
    task = SkillTask(step=0, skill="summarizer", instruction="", prompt=prompt, language=language)
    output = Summarizer(LLMClient(model), Settings(_env_file=None)).run(task)
    assert expected in output.text and model.calls == []


def test_report_counts_provider_errors_separately() -> None:
    from skill_agent.evaluation import CaseResult, EvalCase, EvalReport

    def result(correct: bool, error: str | None = None) -> CaseResult:
        case = EvalCase(id="c", category="clear", language="en", prompt="p", expected=["x"])
        return CaseResult(
            case=case,
            predicted=[],
            mode="single",
            confidence=0.0,
            correct=correct,
            mode_correct=None,
            latency_ms=1.0,
            error=error,
        )

    report = EvalReport(
        model="m", created_at="now", full_run=False, results=[result(True), result(False, "429")]
    )
    assert "accuracy on the 1 routed cases: 1/1 (100%)" in report.to_markdown()
    assert json.loads(report.model_dump_json())["results"][1]["error"] == "429"

    all_failed = EvalReport(
        model="m", created_at="now", full_run=False, results=[result(False, "400")]
    )
    assert "nothing was routed" in all_failed.to_markdown()
