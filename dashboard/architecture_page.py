"""How the agent works: lifecycle, graph, skill cards and context protection."""

from __future__ import annotations

from html import escape

import streamlit as st
from components import icon, look, section
from services import get_agent
from strings import language, t

from skill_agent.config import get_settings
from skill_agent.skills import registry

GRAPH = """
flowchart LR
    U([prompt]) --> P[preprocess]
    P --> R{{router}}
    R -- clarify --> C[clarify]
    R -- "Send ×n (parallel)" --> A[skill A]
    R -. parallel .-> B[skill B]
    A -- "output → input (sequential)" --> B
    A --> M[compose]
    B --> M
    A -. calculator .-> T[(calculate tool)]
    C --> E([answer])
    M --> E
    classDef router fill:#1b2350,stroke:#8b9bff,color:#e7eaf3
    classDef skill fill:#131b30,stroke:#4dd4e6,color:#e7eaf3
    classDef tool fill:#2a2212,stroke:#fbbf24,color:#fde68a
    class R router
    class A,B skill
    class T tool
"""

LIFECYCLE = [
    ("Preprocess", "پیش‌پردازش",
     "Normalize Persian letters and half-spaces, guess the language.",
     "یکسان‌سازی حروف و نیم‌فاصله‌ی فارسی و تشخیص زبان."),
    ("Route", "مسیریابی",
     "One LLM call returns validated JSON: skills, mode, language, confidence.",
     "یک فراخوانی LLM خروجی JSON معتبر می‌دهد: اسکیل‌ها، حالت، زبان، اطمینان."),
    ("Apply policies", "اعمال قواعد",
     "Code handles fallback, clarification and low confidence.",
     "حالت جایگزین، درخواست توضیح و اطمینان پایین با کد مدیریت می‌شود."),
    ("Run skills", "اجرای اسکیل‌ها",
     "Parallel with Send, or chained; each skill gets only its share.",
     "موازی با Send یا زنجیره‌ای؛ هر اسکیل فقط سهم خودش را می‌گیرد."),
    ("Check & compose", "بررسی و ترکیب",
     "Deterministic checks repair outputs; results are joined without an LLM.",
     "بررسی‌های قطعی خروجی را اصلاح می‌کنند و نتایج بدون LLM ترکیب می‌شوند."),
]  # fmt: skip

CONTEXT = [
    ("dashboard_customize", "More skills", "اسکیل‌های بیشتر",
     "Compact cards; a lexical shortlister keeps the top-k above a threshold.",
     "کارت‌های فشرده؛ بالاتر از آستانه فقط k کارت مرتبط‌تر انتخاب می‌شود.", "shortlist"),
    ("short_text", "Long messages", "پیام‌های طولانی",
     "The router reads only the head and tail of a long message.",
     "مسیریاب فقط ابتدا و انتهای پیام طولانی را می‌بیند.", "excerpt"),
    ("call_split", "Several skills", "چند اسکیل هم‌زمان",
     "Parallel skills share an output budget; chained outputs are capped.",
     "اسکیل‌های موازی بودجه‌ی خروجی مشترک دارند و خروجی زنجیره سقف دارد.", "budget"),
    ("link", "Chains", "زنجیره‌ها",
     "The next step gets the previous output and the instruction only.",
     "مرحله‌ی بعد فقط خروجی قبلی و دستور کاربر را می‌گیرد.", "handoff"),
    ("library_books", "Huge texts", "متن‌های خیلی بلند",
     "Map-reduce summaries and chunked translation, every call inside the window.",
     "خلاصه‌سازی map-reduce و ترجمه‌ی تکه‌تکه؛ هر فراخوانی داخل پنجره.", "chunks"),
    ("psychology", "Hidden reasoning", "استدلال پنهان",
     "Reasoning off by default, per-skill opt-in, empty answers retried.",
     "استدلال به‌طور پیش‌فرض خاموش، قابل فعال‌سازی برای هر اسکیل، تکرار پاسخ خالی.", "reasoning"),
]  # fmt: skip


# Persian descriptions for the interface. The router keeps reading the English cards.
SKILL_TEXT_FA = {
    "summarizer": (
        "متن داده‌شده را به خلاصه‌ای کوتاه‌تر تبدیل می‌کند.",
        "کاربر متنی داده و خلاصه، چکیده یا نکات کلیدی آن را می‌خواهد.",
    ),
    "translator": (
        "متن را بین زبان‌ها (فارسی، انگلیسی و دیگر زبان‌ها) ترجمه می‌کند.",
        "کاربر متنی داده و آن را به زبان دیگری می‌خواهد، یا معادل عبارتی را می‌پرسد.",
    ),
    "calculator": (
        "محاسبات ریاضی را با یک ابزار واقعی و امن انجام می‌دهد.",
        "کاربر نتیجه‌ی عددی می‌خواهد: حساب، درصد، توان، ریشه، مثلثات یا مسئله‌ی متنی.",
    ),
    "general_chat": (
        "سلام و احوال‌پرسی، گفت‌وگوی روزمره و پرسش‌های عمومی.",
        "پیام گفت‌وگویی یا پرسش عمومی است، یا هیچ اسکیل دیگری مناسب نیست.",
    ),
}


def _setting(kind: str) -> str:
    s = get_settings()
    return {
        "shortlist": f"threshold {s.shortlist_threshold} · top-k {s.shortlist_top_k}",
        "excerpt": f"{s.router_excerpt_tokens} tokens",
        "budget": f"total {s.total_output_budget} · step ≤ {s.max_output_tokens}",
        "handoff": f"≤ {s.max_output_tokens} tokens",
        "chunks": f"chunk {s.chunk_tokens} tokens",
        "reasoning": f"{s.llm_reasoning} · {s.llm_reasoning_param}",
    }[kind]


def _mermaid(diagram: str, height: int) -> None:
    st.iframe(
        f"""
        <div class="mermaid" style="display:flex;justify-content:center">{diagram}</div>
        <script type="module">
          import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";
          mermaid.initialize({{ startOnLoad: false, theme: "dark",
            themeVariables: {{ background: "#0a0f1e", primaryColor: "#131b30",
              primaryBorderColor: "#4dd4e6", lineColor: "#8b9bff", primaryTextColor: "#e7eaf3",
              fontFamily: "Inter, Vazirmatn, sans-serif" }} }});
          const node = document.querySelector(".mermaid");
          new IntersectionObserver((entries, observer) => {{
            if (entries.some((e) => e.isIntersecting)) {{
              observer.disconnect();
              mermaid.run({{ nodes: [node] }});
            }}
          }}).observe(node);
        </script>
        <style>body {{ margin: 0; background: transparent; }}</style>
        """,
        height=height,
    )


def render() -> None:
    fa = language() == "fa"
    st.html(
        f'<div class="sa-hero" style="padding-top:1.2rem"><h1>{escape(t("arch.title"))}</h1>'
        f"<p>{escape(t('arch.subtitle'))}</p></div>"
    )

    st.html(section("route", t("arch.lifecycle")))
    steps = "".join(
        f'<div class="sa-step"><div class="sa-step-num">{i}</div>'
        f"<b>{escape(fa_t if fa else en_t)}</b>"
        f"<p>{escape(fa_d if fa else en_d)}</p></div>"
        for i, (en_t, fa_t, en_d, fa_d) in enumerate(LIFECYCLE, 1)
    )
    st.html(f'<div class="sa-steps">{steps}</div>')

    st.html(section("account_tree", t("arch.graph")))
    with st.container(border=True):
        _mermaid(GRAPH, 330)
    agent, _ = get_agent()
    if agent is not None:
        with st.expander(t("arch.compiled"), icon=":material/schema:"):
            _mermaid(agent.mermaid(), 620)

    st.html(section("extension", t("arch.skills"), t("arch.skills.note")))
    cards = registry.cards()
    columns = st.columns(2)
    for i, card in enumerate(cards):
        item = look(card.name)
        examples = "".join(f'<span class="sa-example">{escape(e)}</span>' for e in card.examples)
        summary, use_when = card.summary, card.use_when
        if fa and card.name in SKILL_TEXT_FA:
            summary, use_when = SKILL_TEXT_FA[card.name]
        columns[i % 2].html(
            f'<div class="sa-card"><div class="sa-icon-tile" style="--c:{item.color}">'
            f"{icon(item.icon)}</div><h4>{escape(item.label)} "
            f'<code style="font-size:0.72rem;color:#63708a">{card.name}</code></h4>'
            f"<p>{escape(summary)}</p>"
            f'<div class="sa-label">{escape(t("arch.when"))}</div><p>{escape(use_when)}</p>'
            f'<div class="sa-examples">{examples}</div></div>'
        )

    st.html(section("shield", t("arch.context"), t("arch.context.note")))
    context_columns = st.columns(3)
    for i, (icon_name, en_t, fa_t, en_d, fa_d, kind) in enumerate(CONTEXT):
        context_columns[i % 3].html(
            f'<div class="sa-card"><div class="sa-icon-tile">{icon(icon_name)}</div>'
            f"<h4>{escape(fa_t if fa else en_t)}</h4><p>{escape(fa_d if fa else en_d)}</p>"
            f'<div class="sa-kv"><span>config</span>'
            f"<code>{escape(_setting(kind))}</code></div></div>"
        )
