"""How the agent works: lifecycle, graph, skills and context protection."""

from __future__ import annotations

from html import escape

import streamlit as st
from components import heading, skill, subheading
from services import get_agent
from strings import language, t

from skill_agent.config import get_settings
from skill_agent.skills import registry

GRAPH = """
flowchart LR
    U([prompt]) --> P[preprocess]
    P --> R{{router}}
    R -- clarify --> C[clarify]
    R -- "parallel" --> A[skill A]
    R -. parallel .-> B[skill B]
    A -- "sequential" --> B
    A --> M[compose]
    B --> M
    A -. calculator .-> T[(calculate tool)]
    C --> E([answer])
    M --> E
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
     "In parallel, or chained; each skill gets only its share of the message.",
     "موازی یا زنجیره‌ای؛ هر اسکیل فقط سهم خودش از پیام را می‌گیرد."),
    ("Check & compose", "بررسی و ترکیب",
     "Deterministic checks repair outputs; results are joined without an LLM.",
     "بررسی‌های قطعی خروجی را اصلاح می‌کنند و نتایج بدون LLM ترکیب می‌شوند."),
]  # fmt: skip

CONTEXT = [
    ("More skills", "اسکیل‌های بیشتر",
     "The router reads compact cards; above a threshold only the top-k most relevant.",
     "مسیریاب فقط کارت‌های کوتاه را می‌بیند و بالاتر از آستانه، فقط k کارت مرتبط‌تر را.",
     "shortlist"),
    ("Long messages", "پیام‌های طولانی",
     "The router reads only the beginning and end of a long message.",
     "مسیریاب فقط ابتدا و انتهای پیام طولانی را می‌خواند.", "excerpt"),
    ("Several skills", "چند اسکیل هم‌زمان",
     "Parallel skills share one output budget; chained outputs are capped.",
     "اسکیل‌های موازی یک بودجه‌ی خروجی مشترک دارند و خروجی زنجیره سقف دارد.", "budget"),
    ("Chains", "زنجیره‌ها",
     "The next step receives only the previous output and the user's instruction.",
     "مرحله‌ی بعد فقط خروجی قبلی و دستور کاربر را می‌گیرد.", "handoff"),
    ("Very long texts", "متن‌های خیلی بلند",
     "Map-reduce summaries and chunked translation keep every call inside the window.",
     "خلاصه‌سازی map-reduce و ترجمه‌ی تکه‌تکه، هر فراخوانی را داخل پنجره نگه می‌دارد.",
     "chunks"),
    ("Hidden reasoning", "استدلال پنهان",
     "Off by default, opt-in per skill; an empty answer is retried once.",
     "به‌طور پیش‌فرض خاموش، قابل فعال‌سازی برای هر اسکیل؛ پاسخ خالی یک بار تکرار می‌شود.",
     "reasoning"),
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
          mermaid.initialize({{ startOnLoad: false, theme: "base",
            themeVariables: {{ background: "#ffffff", primaryColor: "#ffffff",
              primaryBorderColor: "#d6d3d1", primaryTextColor: "#1c1917", lineColor: "#a8a29e",
              tertiaryColor: "#f3f3f1", fontFamily: "Inter, Vazirmatn, sans-serif",
              fontSize: "14px" }} }});
          const node = document.querySelector(".mermaid");
          new IntersectionObserver((entries, observer) => {{
            if (entries.some((e) => e.isIntersecting)) {{
              observer.disconnect();
              mermaid.run({{ nodes: [node] }});
            }}
          }}).observe(node);
        </script>
        <style>
          body {{ margin: 0; background: #ffffff; }}
          svg {{ max-width: 100%; height: auto; }}
        </style>
        """,
        height=height,
    )


def render() -> None:
    fa = language() == "fa"
    st.html(heading(t("arch.title"), t("arch.subtitle")))

    st.html(subheading(t("arch.lifecycle")))
    flow = "".join(
        f"<div><b>{escape(fa_t if fa else en_t)}</b><p>{escape(fa_d if fa else en_d)}</p></div>"
        for en_t, fa_t, en_d, fa_d in LIFECYCLE
    )
    st.html(f'<div class="sa-flow">{flow}</div>')

    st.html(subheading(t("arch.graph")))
    with st.container(border=True):
        _mermaid(GRAPH, 300)
    agent, _ = get_agent()
    if agent is not None:
        with st.expander(t("arch.compiled")):
            _mermaid(agent.mermaid(), 560)

    st.html(subheading(t("arch.skills"), t("arch.skills.note")))
    rows = []
    for card in registry.cards():
        summary, use_when = card.summary, card.use_when
        if fa and card.name in SKILL_TEXT_FA:
            summary, use_when = SKILL_TEXT_FA[card.name]
        examples = "".join(f'<span class="sa-example">{escape(e)}</span>' for e in card.examples)
        rows.append(
            f'<div class="sa-row"><div>{skill(card.name)}<br><code>{card.name}</code></div>'
            f"<div><p>{escape(summary)}</p><p>{escape(t('arch.when'))}: {escape(use_when)}</p>"
            f'<div class="sa-examples">{examples}</div></div></div>'
        )
    st.html(f'<div class="sa-panel">{"".join(rows)}</div>')

    st.html(subheading(t("arch.context"), t("arch.context.note")))
    rows = [
        f'<div class="sa-row"><b>{escape(fa_t if fa else en_t)}</b>'
        f"<div><p>{escape(fa_d if fa else en_d)}</p>"
        f"<code>{escape(_setting(kind))}</code></div></div>"
        for en_t, fa_t, en_d, fa_d, kind in CONTEXT
    ]
    st.html(f'<div class="sa-panel">{"".join(rows)}</div>')
