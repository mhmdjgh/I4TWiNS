"""How the agent works: lifecycle, graph, skills and context protection."""

from __future__ import annotations

from html import escape

import streamlit as st
from components import heading, skill, subheading
from services import get_agent
from strings import t

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
    ("Preprocess", "Normalize Persian letters and half-spaces, guess the language."),
    ("Route", "One LLM call returns validated JSON: skills, mode, language, confidence."),
    ("Apply policies", "Code handles fallback, clarification and low confidence."),
    ("Run skills", "In parallel, or chained; each skill gets only its share of the message."),
    ("Check & compose", "Deterministic checks repair outputs; results are joined without an LLM."),
]

CONTEXT = [
    ("More skills",
     "The router reads compact cards; above a threshold only the top-k most relevant.",
     "shortlist"),
    ("Long messages", "The router reads only the beginning and end of a long message.", "excerpt"),
    ("Several skills",
     "Parallel skills share one output budget; chained outputs are capped.", "budget"),
    ("Chains",
     "The next step receives only the previous output and the user's instruction.", "handoff"),
    ("Very long texts",
     "Map-reduce summaries and chunked translation keep every call inside the window.", "chunks"),
    ("Hidden reasoning",
     "Off by default, opt-in per skill; an empty answer is retried once.", "reasoning"),
]  # fmt: skip


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
    st.html(heading(t("arch.title"), t("arch.subtitle")))

    st.html(subheading(t("arch.lifecycle")))
    flow = "".join(
        f"<div><b>{escape(title)}</b><p>{escape(text)}</p></div>" for title, text in LIFECYCLE
    )
    st.html(f'<div class="sa-flow">{flow}</div>')

    st.html(subheading(t("arch.graph")))
    with st.container(border=True):
        _mermaid(GRAPH, 300)
    agent = get_agent()
    if agent is not None:
        with st.expander(t("arch.compiled")):
            _mermaid(agent.mermaid(), 560)

    st.html(subheading(t("arch.skills"), t("arch.skills.note")))
    rows = []
    for card in registry.cards():
        examples = "".join(f'<span class="sa-example">{escape(e)}</span>' for e in card.examples)
        rows.append(
            f'<div class="sa-row"><div>{skill(card.name)}<br><code>{card.name}</code></div>'
            f"<div><p>{escape(card.summary)}</p>"
            f"<p>{escape(t('arch.when'))}: {escape(card.use_when)}</p>"
            f'<div class="sa-examples">{examples}</div></div></div>'
        )
    st.html(f'<div class="sa-panel">{"".join(rows)}</div>')

    st.html(subheading(t("arch.context"), t("arch.context.note")))
    rows = [
        f'<div class="sa-row"><b>{escape(title)}</b><div><p>{escape(text)}</p>'
        f"<code>{escape(_setting(kind))}</code></div></div>"
        for title, text, kind in CONTEXT
    ]
    st.html(f'<div class="sa-panel">{"".join(rows)}</div>')
