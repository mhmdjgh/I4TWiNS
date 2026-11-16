"""Web dashboard for the agent.

A second, thin interface next to the CLI: it calls the same `Agent` in-process (there is no web
API layer) and makes the internals visible - routing decision, execution trace, tool calls and
the evaluation results.

    uv run --extra dashboard streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from skill_agent.agent import Agent, AgentResponse
from skill_agent.config import get_settings
from skill_agent.evaluation import EvalReport, evaluate, load_cases
from skill_agent.llm import ConfigurationError
from skill_agent.skills import registry

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results.json"
DATASET = ROOT / "evals" / "dataset.yaml"

EXAMPLES = {
    "سلام، خوبی؟ چه خبر؟": "Persian small talk",
    "۲۵ درصد از ۸۴۰ هزار تومان چقدر میشه؟": "Persian calculation",
    "Translate into Persian: The meeting has been moved to Thursday morning.": "EN → FA",
    "این متن را خلاصه کن و خلاصه‌اش را به انگلیسی ترجمه کن: شهر اصفهان با پل‌های تاریخی، "
    "میدان نقش جهان و معماری دوره‌ی صفوی یکی از مهم‌ترین مقصدهای گردشگری ایران است. خشک شدن "
    "زاینده‌رود در سال‌های اخیر اما به کسب‌وکارهای وابسته به گردشگری آسیب زده است.": "Sequential",
    "Translate 'good luck with your exam' into Persian, and what is 15% of 3,200?": "Parallel",
    "translate this please": "Ambiguous",
}

ARCHITECTURE = """
flowchart TB
    U([User prompt]) --> P[preprocess<br/><small>normalize Persian · detect language</small>]
    P --> R{{router<br/><small>shortlisted skill cards · JSON → Pydantic</small>}}
    R -- needs clarification --> C[clarify]
    R -- "Send ×N (parallel)" --> S1[skill A]
    R -- "Send (sequential)" --> S1
    R -. parallel .-> S2[skill B]
    S1 -- "output → input (sequential)" --> S2
    S1 --> M[compose]
    S2 --> M
    S1 -. calculator .-> T[(calculate tool<br/><small>safe AST evaluator</small>)]
    C --> E([answer])
    M --> E
"""

st.set_page_config(page_title="Skill Agent", page_icon="🧭", layout="wide")
st.markdown(
    """
    <style>
      /* Each paragraph takes the direction of its first strong character: Persian renders RTL,
         English LTR, mixed answers stay readable. */
      [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
      textarea { unicode-bidi: plaintext; text-align: start; }
      .answer { border: 1px solid rgba(128,128,128,.25); border-radius: 12px;
                padding: 1rem 1.25rem; background: rgba(46, 125, 50, .06); }
      .chip { display: inline-block; padding: 2px 10px; margin: 0 6px 6px 0; border-radius: 999px;
              background: rgba(25, 118, 210, .12); font-size: .85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_agent() -> Agent:
    return Agent.from_settings()


def mermaid(diagram: str, height: int = 420) -> None:
    st.iframe(
        f"""
        <div class="mermaid">{diagram}</div>
        <script type="module">
          import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";
          const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
          mermaid.initialize({{ startOnLoad: false, theme: dark ? "dark" : "neutral" }});
          // Streamlit mounts inactive tabs hidden; Mermaid cannot measure text there, so draw
          // the diagram the first time it becomes visible.
          const node = document.querySelector(".mermaid");
          new IntersectionObserver((entries, observer) => {{
            if (entries.some((e) => e.isIntersecting)) {{
              observer.disconnect();
              mermaid.run({{ nodes: [node] }});
            }}
          }}).observe(node);
        </script>
        """,
        height=height,
    )


def sidebar() -> Agent | None:
    settings = get_settings()
    st.sidebar.title("🧭 Skill Agent")
    st.sidebar.caption("Summarize · Translate · Calculate · Chat — English & فارسی")
    try:
        agent = load_agent()
        st.sidebar.success("LLM configured", icon="✅")
    except ConfigurationError as exc:
        agent = None
        st.sidebar.error(str(exc), icon="🔑")
    st.sidebar.markdown(
        f"**Model** `{settings.llm_model}`  \n"
        f"**Fallback** `{settings.llm_fallback_model or '-'}`  \n"
        f"**Endpoint** `{settings.llm_base_url}`  \n"
        f"**Reasoning** `{settings.llm_reasoning}`  \n"
        f"**Max skills / request** `{settings.max_skills_per_request}`"
    )
    st.sidebar.divider()
    st.sidebar.caption("Every request is independent: there is no conversation memory.")
    return agent


def show_response(response: AgentResponse) -> None:
    decision = response.decision
    st.markdown(f'<div class="answer">\n\n{response.answer}\n\n</div>', unsafe_allow_html=True)
    if response.error:
        st.error(response.error)

    tokens_in, tokens_out = response.tokens
    cols = st.columns(5)
    cols[0].metric(
        "Skills", " → ".join(decision.skill_names) if decision and decision.skills else "clarify"
    )
    cols[1].metric("Mode", decision.mode if decision else "-")
    cols[2].metric("Confidence", f"{decision.confidence:.2f}" if decision else "-")
    cols[3].metric("Latency", f"{response.elapsed_ms / 1000:.1f}s")
    cols[4].metric("Tokens in / out", f"{tokens_in} / {tokens_out}")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Execution trace")
        trace = pd.DataFrame([e.model_dump() for e in response.trace])
        if not trace.empty:
            st.bar_chart(trace, x="node", y="elapsed_ms", height=220)
            st.dataframe(trace, hide_index=True, width="stretch")
    with right:
        st.subheader("Routing decision")
        if decision:
            chips = "".join(f'<span class="chip">{s.skill}</span>' for s in decision.skills)
            st.markdown(chips or '<span class="chip">clarify</span>', unsafe_allow_html=True)
            st.caption(decision.reasoning or "")
            steps = [s.model_dump() for s in decision.skills]
            if steps:
                st.dataframe(pd.DataFrame(steps), hide_index=True, width="stretch")

    calls = [
        {"skill": r.skill, **c.model_dump()}
        for r in response.results
        for c in (r.output.tool_calls if r.output else [])
    ]
    if calls:
        st.subheader("Tool calls")
        st.dataframe(pd.DataFrame(calls), hide_index=True, width="stretch")

    if len(response.results) > 1:
        with st.expander("Intermediate results"):
            for result in response.results:
                st.markdown(f"**Step {result.step + 1} · {result.skill}**")
                st.markdown(result.output.text if result.output else f"❌ {result.error}")
    with st.expander("Raw response (JSON)"):
        st.json(json.loads(response.model_dump_json()))


def playground(agent: Agent | None) -> None:
    st.subheader("Ask anything")
    st.caption("Try an example:")
    example_cols = st.columns(3)
    for i, (prompt, label) in enumerate(EXAMPLES.items()):
        if example_cols[i % 3].button(label, width="stretch", key=f"ex{i}"):
            st.session_state.prompt = prompt

    prompt = st.text_area("Prompt", key="prompt", height=130, placeholder="یک درخواست بنویسید…")
    if st.button("Run", type="primary", disabled=agent is None or not prompt.strip()):
        assert agent is not None
        with st.spinner("Routing and running skills…"):
            st.session_state.last = agent.run(prompt)
    if "last" in st.session_state:
        st.divider()
        show_response(st.session_state.last)


def architecture(agent: Agent | None) -> None:
    st.subheader("Graph")
    mermaid(ARCHITECTURE, height=620)
    if agent is not None:
        with st.expander("Graph as compiled by LangGraph"):
            mermaid(agent.mermaid(), height=640)

    st.subheader("Registered skills")
    st.caption("The router only ever sees these cards; full skill prompts load inside each node.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "skill": c.name,
                    "summary": c.summary,
                    "use when": c.use_when,
                    "examples": " | ".join(c.examples),
                }
                for c in registry.cards()
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Context protection")
    settings = get_settings()
    rows = [
        (
            "Router prompt grows with the number of skills",
            "Compact cards; shortlist top-k above a threshold",
            f"threshold {settings.shortlist_threshold}, top-k {settings.shortlist_top_k}",
        ),
        (
            "Long message sent to the router",
            "Head/tail excerpt",
            f"{settings.router_excerpt_tokens} tokens",
        ),
        (
            "Several skills in one answer",
            "Parallel steps share the output budget; chained outputs are capped",
            f"total {settings.total_output_budget}, per step ≤ {settings.max_output_tokens}",
        ),
        (
            "Long text to summarize / translate",
            "Map-reduce / chunked translation",
            f"chunk {settings.chunk_tokens} tokens",
        ),
    ]
    st.dataframe(
        pd.DataFrame(rows, columns=["Risk", "Mechanism", "Setting"]),
        hide_index=True,
        width="stretch",
    )


def evaluation(agent: Agent | None) -> None:
    if RESULTS.exists():
        report = EvalReport.model_validate_json(RESULTS.read_text(encoding="utf-8"))
        routed = [r for r in report.results if not r.error]
        cols = st.columns(4)
        cols[0].metric("Accuracy (strict)", f"{report.accuracy:.0%}")
        if routed:
            cols[1].metric(
                "Accuracy (routed cases)", f"{sum(r.correct for r in routed) / len(routed):.0%}"
            )
        cols[2].metric("Cases", len(report.results))
        cols[3].metric("Provider errors", sum(1 for r in report.results if r.error))
        st.caption(f"Model `{report.model}` · {report.created_at}")

        by_category = pd.DataFrame(
            [
                {"category": c, "correct": h, "total": t}
                for c, (h, t) in report.by_category().items()
            ]
        )
        per_label = pd.DataFrame(
            [
                {"label": k, "precision": p, "recall": r, "support": n}
                for k, (p, r, n) in report.per_label().items()
            ]
        )
        left, right = st.columns(2)
        left.dataframe(by_category, hide_index=True, width="stretch")
        right.dataframe(per_label, hide_index=True, width="stretch")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "": "✅" if r.correct else "❌",
                        "id": r.case.id,
                        "prompt": r.case.prompt[:90],
                        "expected": " → ".join(r.case.expected),
                        "predicted": " → ".join(r.predicted) or (r.error or "-")[:60],
                        "mode": r.mode,
                        "confidence": r.confidence,
                    }
                    for r in report.results
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No evaluation results yet. Run `skill-agent eval` or use the button below.")

    st.divider()
    st.caption(
        "Re-running uses one request per case (15 in total). The free tier allows 50 requests "
        "per day."
    )
    if st.button("Run routing evaluation", disabled=agent is None):
        assert agent is not None
        cases = load_cases(DATASET)
        progress = st.progress(0.0)
        done: list[int] = []

        def tick(_: object) -> None:
            done.append(1)
            progress.progress(len(done) / len(cases))

        report = evaluate(agent, cases, delay_s=3.0, on_result=tick)
        RESULTS.write_text(report.model_dump_json(indent=2), encoding="utf-8", newline="\n")
        (RESULTS.parent / "report.md").write_text(
            report.to_markdown(), encoding="utf-8", newline="\n"
        )
        st.rerun()


agent = sidebar()
tab_play, tab_arch, tab_eval = st.tabs(["Playground", "Architecture", "Evaluation"])
with tab_play:
    playground(agent)
with tab_arch:
    architecture(agent)
with tab_eval:
    evaluation(agent)
