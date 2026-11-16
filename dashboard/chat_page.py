"""Assistant page: a quiet chat. Technical details stay folded under each answer."""

from __future__ import annotations

import json
from html import escape

import streamlit as st
from components import meta_line, steps
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


def _welcome() -> None:
    st.html(
        f'<div class="sa-welcome"><h1>{escape(t("chat.hero.title"))}</h1>'
        f"<p>{escape(t('chat.hero.subtitle'))}</p></div>"
    )
    fa = language() == "fa"
    with st.container(horizontal=True, wrap=True, gap="small", key="suggestions"):
        for i, (label_en, label_fa, prompt) in enumerate(SUGGESTIONS):
            if st.button(label_fa if fa else label_en, key=f"suggest-{i}", help=prompt):
                st.session_state.pending = prompt


def _details(response: AgentResponse) -> None:
    """Steps, routing decision and raw JSON, folded away by default."""
    decision = response.decision
    with st.expander(t("chat.behind")):
        st.html(steps(response))
        if decision is not None and (decision.reasoning or decision.skills):
            lines = (
                [f"**{t('chat.reasoning')}:** {decision.reasoning}"] if decision.reasoning else []
            )
            for i, step in enumerate(decision.skills, 1):
                line = f"{i}. `{step.skill}` · {step.instruction}"
                if step.target_language:
                    line += f" · {t('chat.target')}: {step.target_language}"
                if step.input:
                    line += f" · {t('chat.span')}: «{step.input}»"
                lines.append(line)
            st.markdown("  \n".join(lines))
        calls = [c for r in response.results if r.output for c in r.output.tool_calls]
        for call in calls:
            argument = call.arguments.get("expression", call.arguments)
            st.markdown(f"`{call.name}({argument})` → **{call.output}**")
        if len(response.results) > 1:
            for result in response.results:
                st.caption(f"{result.step + 1}. {result.skill}")
                st.markdown(result.output.text if result.output else f"⚠️ {result.error}")
        with st.popover(t("chat.raw"), icon=":material/data_object:"):
            st.json(json.loads(response.model_dump_json()), expanded=False)


def _exchange(response: AgentResponse, index: int) -> None:
    with st.chat_message("user", avatar=":material/person:"):
        st.html(f'<div class="sa-user">{escape(response.prompt)}</div>')
    with st.chat_message("assistant", avatar=":material/hub:"):
        decision = response.decision
        answer_language = decision.response_language if decision else response.language
        # The answer keeps its own direction whatever the interface language is.
        direction = "rtl" if is_rtl(answer_language) else "ltr"
        with st.container(key=f"answer-{index}-{direction}"):
            st.markdown(response.answer)
            if response.error:
                st.caption(f"⚠️ {response.error}")
        st.html(meta_line(response))
        _details(response)


def render() -> None:
    agent, _ = get_agent()
    history = _history()

    if not history:
        _welcome()
    for i, response in enumerate(history):
        _exchange(response, i)

    if agent is None:
        st.info(t("chat.no_key"), icon=":material/key:")
    prompt = st.chat_input(t("chat.placeholder"), disabled=agent is None)
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt and agent is not None:
        with st.chat_message("user", avatar=":material/person:"):
            st.html(f'<div class="sa-user">{escape(prompt)}</div>')
        with (
            st.chat_message("assistant", avatar=":material/hub:"),
            st.spinner(t("chat.thinking")),
        ):
            response = agent.run(prompt)
        history.append(response)
        st.rerun()
