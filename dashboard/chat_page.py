"""Conversation view: suggestions, answers and a "behind the scenes" panel per answer."""

from __future__ import annotations

import json
from html import escape

import streamlit as st
from components import meta_row, pipeline, section
from services import get_agent
from strings import language, t

from skill_agent.agent import AgentResponse
from skill_agent.text.persian import is_rtl

# (English label, Persian label, prompt). Deliberately different from the evaluation prompts.
SUGGESTIONS: list[tuple[str, str, str]] = [
    (
        "Summarize, then translate",
        "خلاصه، بعد ترجمه",
        "این متن را خلاصه کن و خلاصه‌اش را به انگلیسی ترجمه کن: "
        "شیراز با باغ ارم، آرامگاه حافظ و سعدی و بازار وکیل هر سال میزبان هزاران گردشگر است. "
        "فصل بهار و جشنواره‌های فرهنگی بیشترین مسافر را به این شهر می‌آورد، "
        "اما کمبود هتل در ایام نوروز همچنان یک مشکل جدی است.",
    ),
    (
        "Two tasks at once",
        "دو کار هم‌زمان",
        "Translate 'see you tomorrow' into Persian, and what is 18% of 2,450?",
    ),
    (
        "Word problem",
        "مسئله‌ی محاسباتی",
        "سه تا کتاب ۸۵ هزار تومنی و دو تا خودکار ۱۲ هزار تومنی خریدم، جمعش چقدر میشه؟",
    ),
    ("Translate", "ترجمه", "Translate into Persian: The workshop starts on Monday at 9 a.m."),
    ("Small talk", "گفت‌وگو", "سلام! تو چه کارهایی می‌تونی برام انجام بدی؟"),
    ("Ambiguous", "مبهم", "translate this please"),
]


def _history() -> list[AgentResponse]:
    history: list[AgentResponse] = st.session_state.setdefault("history", [])
    return history


def _hero() -> None:
    st.html(
        f"""
        <div class="sa-hero">
          <span class="sa-eyebrow"><span class="material-symbols-rounded">bolt</span>
          LangGraph · Pydantic · {"فارسی" if language() == "fa" else "English & فارسی"}</span>
          <h1>{escape(t("chat.hero.title"))}</h1>
          <p>{escape(t("chat.hero.subtitle"))}</p>
        </div>
        """
    )
    st.html(section("auto_awesome", t("chat.try")))
    with st.container(key="suggestions"):
        columns = st.columns(3)
        for i, (label_en, label_fa, prompt) in enumerate(SUGGESTIONS):
            label = label_fa if language() == "fa" else label_en
            preview = prompt if len(prompt) < 95 else prompt[:92] + "…"
            if columns[i % 3].button(
                f"**{label}**  \n{preview}", key=f"suggest-{i}", width="stretch"
            ):
                st.session_state.pending = prompt


def _behind_the_scenes(response: AgentResponse) -> None:
    decision = response.decision
    with st.expander(t("chat.behind"), icon=":material/visibility:"):
        tabs = st.tabs(
            [t("chat.pipeline"), t("chat.routing"), t("chat.tools"), t("chat.steps"), t("chat.raw")]
        )
        with tabs[0]:
            st.html(pipeline(response))
        with tabs[1]:
            if decision is None:
                st.caption(response.error or "-")
            else:
                if decision.reasoning:
                    st.markdown(f"**{t('chat.reasoning')}:** {decision.reasoning}")
                if decision.needs_clarification:
                    st.markdown(f"**{t('chat.clarify')}:** {decision.clarification_question}")
                for i, step in enumerate(decision.skills, 1):
                    lines = [
                        f"**{i}. `{step.skill}`** · {t('chat.instruction')}: {step.instruction}"
                    ]
                    if step.target_language:
                        lines.append(f"{t('chat.target')}: {step.target_language}")
                    if step.input:
                        lines.append(f"{t('chat.span')}: «{step.input}»")
                    st.markdown("  \n".join(lines))
        with tabs[2]:
            calls = [c for r in response.results if r.output for c in r.output.tool_calls]
            if not calls:
                st.caption(t("chat.no_tools"))
            for call in calls:
                status = "✅" if call.ok else "⚠️"
                argument = call.arguments.get("expression", call.arguments)
                st.markdown(f"{status} `{call.name}({argument})` → **{call.output}**")
        with tabs[3]:
            if len(response.results) < 2:
                st.caption(t("chat.no_steps"))
            for result in response.results:
                if len(response.results) < 2:
                    break
                st.markdown(f"**{result.step + 1}. `{result.skill}`**")
                st.markdown(result.output.text if result.output else f"⚠️ {result.error}")
        with tabs[4]:
            st.json(json.loads(response.model_dump_json()), expanded=False)


def _exchange(response: AgentResponse, index: int) -> None:
    with st.chat_message("user", avatar=":material/person:"):
        st.html(f'<div class="sa-user-bubble">{escape(response.prompt)}</div>')
    with st.chat_message("assistant", avatar=":material/hub:"):
        st.html(meta_row(response))
        decision = response.decision
        answer_language = decision.response_language if decision else response.language
        # The answer keeps its own direction whatever the interface language is.
        direction = "rtl" if is_rtl(answer_language) else "ltr"
        with st.container(key=f"answer-{index}-{direction}"):
            st.markdown(response.answer)
            if response.error:
                st.caption(f"⚠️ {response.error}")
        _behind_the_scenes(response)


def render() -> None:
    agent, _ = get_agent()
    history = _history()

    if not history:
        _hero()
    for i, response in enumerate(history):
        _exchange(response, i)

    if agent is None:
        st.warning(t("chat.no_key"), icon=":material/key:")
    prompt = st.chat_input(t("chat.placeholder"), disabled=agent is None)
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt and agent is not None:
        with st.chat_message("user", avatar=":material/person:"):
            st.html(f'<div class="sa-user-bubble">{escape(prompt)}</div>')
        with (
            st.chat_message("assistant", avatar=":material/hub:"),
            st.status(t("chat.thinking"), expanded=False) as status,
        ):
            response = agent.run(prompt)
            status.update(label=t("chat.done"), state="complete")
        history.append(response)
        st.rerun()
