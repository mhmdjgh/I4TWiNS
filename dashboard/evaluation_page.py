"""Evaluation results: headline numbers, breakdowns and every case."""

from __future__ import annotations

from html import escape

import streamlit as st
from components import heading, icon, meter, skill, stat, subheading
from services import DATASET, LOCAL_RUN, RESULTS, get_agent
from strings import t

from skill_agent.evaluation import (
    EVAL_DELAY_S,
    CaseResult,
    Category,
    EvalReport,
    evaluate,
    load_cases,
)

CATEGORY_LABELS: dict[Category, str] = {
    "clear": "Clear",
    "multi": "Multi-skill",
    "ambiguous": "Ambiguous",
    "no_skill": "No skill",
}


def _category(name: Category) -> str:
    return CATEGORY_LABELS.get(name, name)


def _labels(labels: list[str], mode: str) -> str:
    joiner = " → " if mode == "sequential" else " + "
    return joiner.join(skill(label) for label in labels) or skill("clarify")


def _case(result: CaseResult, with_answer: bool) -> str:
    mark = (
        f'<span class="mark ok">{icon("check_circle")}</span>'
        if result.correct
        else f'<span class="mark bad">{icon("cancel")}</span>'
    )
    expected = _labels(result.case.expected, result.case.mode or "")
    got = (
        _labels(result.predicted, result.mode) if result.predicted else escape(result.error or "-")
    )
    meta = (
        f"<span>{escape(t('eval.expected'))}: {expected}</span>"
        f"<span>{escape(t('eval.got'))}: {got}</span>"
        f"<code>{escape(result.case.id)}</code>"
    )
    answer = ""
    if with_answer and result.answer:
        answer = f'<div class="answer">{escape(result.answer)}</div>'
    prompt = escape(result.case.prompt.strip())
    return (
        f'<div class="sa-case">{mark}<div><div class="prompt">{prompt}</div>'
        f'<div class="meta">{meta}</div>{answer}</div></div>'
    )


def _load() -> EvalReport | None:
    sources = {t("eval.source.official"): RESULTS, t("eval.source.local"): LOCAL_RUN}
    available = {label: path for label, path in sources.items() if path.exists()}
    if not available:
        return None
    source = next(iter(available))
    if len(available) > 1:
        source = (
            st.segmented_control(
                "source", list(available), default=source, label_visibility="collapsed"
            )
            or source
        )
    return EvalReport.model_validate_json(available[source].read_text(encoding="utf-8"))


def render() -> None:
    cases = load_cases(DATASET)
    st.html(heading(t("eval.title"), t("eval.subtitle", count=len(cases))))
    report = _load()
    if report is None:
        st.info(t("eval.empty"), icon=":material/info:")
        return

    results = report.results
    correct = sum(r.correct for r in results)
    latency = sum(r.latency_ms for r in results) / max(len(results), 1) / 1000
    errors = sum(1 for r in results if r.error)
    st.html(
        '<div class="sa-stats">'
        + stat(f"{report.accuracy:.0%}", f"{t('eval.accuracy')} ({correct}/{len(results)})")
        + stat(str(len(results)), t("eval.cases"))
        + stat(f"{latency:.1f}s", t("eval.latency"))
        + stat(str(errors), t("eval.errors"))
        + "</div>"
    )
    st.caption(f"`{report.model}` · {report.created_at}")

    st.html(subheading(t("eval.by_category")))
    meters = "".join(
        meter(_category(name), hit / total, f"{hit}/{total}")
        for name, (hit, total) in report.by_category().items()
    )
    st.html(f'<div class="sa-panel">{meters}</div>')

    st.html(subheading(t("eval.by_skill")))
    rows = "".join(
        f'<div class="sa-row"><div>{skill(name)}</div><p>precision {precision:.0%} · '
        f"recall {recall:.0%} · {support} {escape(t('eval.cases').lower())}</p></div>"
        for name, (precision, recall, support) in report.per_label().items()
    )
    st.html(f'<div class="sa-panel">{rows}</div>')

    st.html(subheading(t("eval.case_list")))
    with st.container(horizontal=True, wrap=True, vertical_alignment="center"):
        choice = st.segmented_control(
            "filter",
            [t("eval.filter.all"), t("eval.filter.pass"), t("eval.filter.fail")],
            default=t("eval.filter.all"),
            label_visibility="collapsed",
        )
        with_answers = st.toggle(t("eval.show_answers"), disabled=not report.full_run)
    shown = [
        r
        for r in results
        if choice in (None, t("eval.filter.all")) or (choice == t("eval.filter.pass")) == r.correct
    ]
    st.html(f'<div class="sa-panel">{"".join(_case(r, with_answers) for r in shown)}</div>')

    agent = get_agent()
    st.html(subheading(t("eval.rerun"), t("eval.rerun.note", count=len(cases))))
    if st.button(t("eval.rerun"), icon=":material/replay:", disabled=agent is None):
        assert agent is not None
        progress = st.progress(0.0)
        done: list[int] = []

        def tick(_: object) -> None:
            done.append(1)
            progress.progress(len(done) / len(cases))

        fresh = evaluate(agent, cases, delay_s=EVAL_DELAY_S, on_result=tick)
        # Saved next to, never over, the committed results (evals/runs/ is git-ignored).
        LOCAL_RUN.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_RUN.write_text(fresh.model_dump_json(indent=2), encoding="utf-8", newline="\n")
        st.rerun()
