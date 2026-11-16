"""Evaluation results: headline numbers, breakdowns and every case with its answer."""

from __future__ import annotations

from html import escape

import altair as alt
import pandas as pd
import streamlit as st
from components import chip, icon, kpi, ring_kpi, section
from services import DATASET, LOCAL_RUN, RESULTS, get_agent
from strings import t

from skill_agent.evaluation import CaseResult, EvalReport, evaluate, load_cases

CATEGORY_LABELS = {
    "clear": ("Clear", "واضح"),
    "multi": ("Multi-skill", "چند اسکیلی"),
    "ambiguous": ("Ambiguous", "مبهم"),
    "no_skill": ("No skill", "بی‌ربط"),
}


def _label(category: str) -> str:
    en, fa = CATEGORY_LABELS.get(category, (category, category))
    return fa if st.session_state.get("ui_lang") == "fa" else en


def _flow(labels: list[str], mode: str) -> str:
    arrow = '<span class="material-symbols-rounded sa-arrow">arrow_forward</span>'
    joiner = arrow if mode == "sequential" else ""
    return joiner.join(chip(label) for label in labels) or chip("clarify")


def _case_row(result: CaseResult) -> str:
    mark = (
        f'<span class="ok">{icon("check_circle")}</span>'
        if result.correct
        else f'<span class="bad">{icon("cancel")}</span>'
    )
    expected_mode = result.case.mode or "single"
    predicted = (
        _flow(result.predicted, result.mode) if result.predicted else escape(result.error or "-")
    )
    return (
        f'<div class="sa-case">{mark}<div style="min-width:0">'
        f'<div class="sa-case-id">{escape(result.case.id)}</div>'
        f'<div class="sa-case-prompt">{escape(result.case.prompt.strip())}</div></div>'
        f'<div class="sa-case-flow"><span class="sa-mini">{escape(t("eval.expected"))}</span>'
        f"{_flow(result.case.expected, expected_mode)}"
        f'<span class="sa-mini" style="margin-inline-start:8px">{escape(t("eval.got"))}</span>'
        f"{predicted}</div></div>"
    )


def _charts(report: EvalReport) -> None:
    left, right = st.columns(2)
    with left:
        st.html(section("category", t("eval.by_category")))
        rows = [
            {"category": _label(c), "share": hit / total, "label": f"{hit}/{total}"}
            for c, (hit, total) in report.by_category().items()
        ]
        data = pd.DataFrame(rows)
        bars = (
            alt.Chart(data)
            .mark_bar(cornerRadiusEnd=6, height=22)
            .encode(
                x=alt.X(
                    "share:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", title=None)
                ),
                y=alt.Y("category:N", sort=None, title=None),
                color=alt.Color(
                    "share:Q",
                    scale=alt.Scale(domain=[0.5, 1], range=["#f87171", "#34d399"]),
                    legend=None,
                ),
            )
        )
        text = bars.mark_text(align="left", dx=6, color="#e7eaf3").encode(text="label:N")
        st.altair_chart((bars + text).properties(height=200), width="stretch")
    with right:
        st.html(section("donut_large", t("eval.by_skill")))
        metric_rows = "".join(
            f'<div class="sa-metric-row"><div>{chip(skill)}</div>'
            f"{_bar('precision', precision, '#8b9bff')}{_bar('recall', recall, '#4dd4e6')}</div>"
            for skill, (precision, recall, _) in report.per_label().items()
        )
        st.html(f'<div class="sa-card">{metric_rows}</div>')


def _bar(name: str, value: float, color: str) -> str:
    return (
        f'<div class="sa-bar"><span>{name}</span><div class="sa-bar-track">'
        f'<div class="sa-bar-fill" style="width:{value * 100:.0f}%;background:{color}"></div></div>'
        f"<b>{value:.0%}</b></div>"
    )


def render() -> None:
    st.html(
        f'<div class="sa-hero" style="padding-top:1.2rem"><h1>{escape(t("eval.title"))}</h1>'
        f"<p>{escape(t('eval.subtitle'))}</p></div>"
    )
    sources = {t("eval.source.official"): RESULTS}
    if LOCAL_RUN.exists():
        sources[t("eval.source.local")] = LOCAL_RUN
    available = {label: path for label, path in sources.items() if path.exists()}
    if not available:
        st.info(t("eval.empty"), icon=":material/info:")
        return
    source = next(iter(available))
    if len(available) > 1:
        source = (
            st.segmented_control(
                "source", list(available), default=source, label_visibility="collapsed"
            )
            or source
        )

    report = EvalReport.model_validate_json(available[source].read_text(encoding="utf-8"))
    results = report.results
    correct = sum(r.correct for r in results)
    latency = sum(r.latency_ms for r in results) / max(len(results), 1) / 1000
    errors = sum(1 for r in results if r.error)

    columns = st.columns(4)
    columns[0].html(ring_kpi(report.accuracy, f"{correct}/{len(results)}", t("eval.accuracy")))
    columns[1].html(kpi(str(len(results)), t("eval.cases"), "fact_check", "#8b9bff"))
    columns[2].html(kpi(f"{latency:.1f}s", t("eval.latency"), "timer", "#4dd4e6"))
    columns[3].html(kpi(str(errors), t("eval.errors"), "error", "#f87171" if errors else "#34d399"))
    st.caption(f"`{report.model}` · {report.created_at}")

    _charts(report)

    st.html(section("list_alt", t("eval.case_list")))
    filters, toggle = st.columns([3, 1], vertical_alignment="center")
    choice = filters.segmented_control(
        "filter",
        [t("eval.filter.all"), t("eval.filter.pass"), t("eval.filter.fail")],
        default=t("eval.filter.all"),
        label_visibility="collapsed",
    )
    with_answers = toggle.toggle(t("eval.show_answers"), disabled=not report.full_run)
    shown = [
        r
        for r in results
        if choice in (None, t("eval.filter.all")) or (choice == t("eval.filter.pass")) == r.correct
    ]
    for result in shown:
        st.html(_case_row(result))
        if with_answers and (result.answer or result.notes):
            with st.container(key=f"case-answer-{result.case.id}"):
                for note in result.notes:
                    st.caption(note)
                st.markdown(result.answer or "")

    agent, _ = get_agent()
    st.divider()
    st.caption(t("eval.rerun.note"))
    if st.button(t("eval.rerun"), icon=":material/replay:", disabled=agent is None):
        assert agent is not None
        cases = load_cases(DATASET)
        progress = st.progress(0.0)
        done: list[int] = []

        def tick(_: object) -> None:
            done.append(1)
            progress.progress(len(done) / len(cases))

        fresh = evaluate(agent, cases, delay_s=3.0, on_result=tick)
        # Saved next to, never over, the committed results (evals/runs/ is git-ignored).
        LOCAL_RUN.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_RUN.write_text(fresh.model_dump_json(indent=2), encoding="utf-8", newline="\n")
        st.rerun()
