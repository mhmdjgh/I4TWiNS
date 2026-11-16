"""Small HTML building blocks used by the pages. All user-provided text is escaped."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from strings import language, t

from skill_agent.agent import AgentResponse


@dataclass(frozen=True)
class Look:
    icon: str
    color: str
    en: str
    fa: str

    @property
    def label(self) -> str:
        return self.fa if language() == "fa" else self.en


LOOKS: dict[str, Look] = {
    "summarizer": Look("notes", "#a78bfa", "Summarizer", "خلاصه‌ساز"),
    "translator": Look("translate", "#38bdf8", "Translator", "مترجم"),
    "calculator": Look("calculate", "#fbbf24", "Calculator", "ماشین‌حساب"),
    "general_chat": Look("forum", "#34d399", "Chat", "گفت‌وگو"),
    "clarify": Look("help", "#94a3b8", "Clarify", "درخواست توضیح"),
    "preprocess": Look("tune", "#93a0b8", "Preprocess", "پیش‌پردازش"),
    "router": Look("alt_route", "#8b9bff", "Router", "مسیریاب"),
    "compose": Look("merge", "#4dd4e6", "Compose", "ترکیب"),
}


def look(name: str) -> Look:
    return LOOKS.get(name, Look("extension", "#8b9bff", name, name))


def icon(name: str, extra: str = "") -> str:
    return f'<span class="material-symbols-rounded {extra}">{name}</span>'


def chip(name: str) -> str:
    item = look(name)
    body = f"{icon(item.icon)}{escape(item.label)}"
    return f'<span class="sa-chip" style="--c:{item.color}">{body}</span>'


def pill(icon_name: str, text: str) -> str:
    return f'<span class="sa-pill">{icon(icon_name)}{escape(text)}</span>'


def section(icon_name: str, title: str, subtitle: str = "") -> str:
    sub = f'<div class="sa-section-sub">{escape(subtitle)}</div>' if subtitle else ""
    return f'<div class="sa-section-title">{icon(icon_name)}{escape(title)}</div>{sub}'


def meta_row(response: AgentResponse) -> str:
    decision = response.decision
    parts: list[str] = []
    if decision is None:
        parts.append(chip("general_chat"))
    elif decision.needs_clarification:
        parts.append(chip("clarify"))
    else:
        arrow = '<span class="material-symbols-rounded sa-arrow">arrow_forward</span>'
        separator = arrow if decision.mode == "sequential" else ""
        parts.append(separator.join(chip(step.skill) for step in decision.skills))
        parts.append(pill("account_tree", t(f"meta.mode.{decision.mode}")))
    if decision is not None:
        parts.append(pill("verified", f"{t('meta.confidence')} {decision.confidence:.0%}"))
    tokens_in, tokens_out = response.tokens
    parts.append(pill("timer", f"{response.elapsed_ms / 1000:.1f}s"))
    parts.append(pill("token", f"{tokens_in + tokens_out:,} {t('meta.tokens')}"))
    return f'<div class="sa-meta">{"".join(parts)}</div>'


def _node(name: str, elapsed_ms: float, tokens: int, detail: str, failed: bool = False) -> str:
    item = look(name)
    stats = [f"{elapsed_ms / 1000:.2f}s"] if elapsed_ms >= 1 else ["<0.01s"]
    if tokens:
        stats.append(f"{tokens:,} tok")
    detail_html = f'<div class="sa-node-detail">{escape(detail)}</div>' if detail else ""
    stats_html = "".join(f"<span>{s}</span>" for s in stats)
    css = "sa-node failed" if failed else "sa-node"
    return (
        f'<div class="{css}" style="--c:{item.color}">'
        f'<div class="sa-node-head">{icon(item.icon)}{escape(item.label)}</div>'
        f'<div class="sa-node-stats">{stats_html}</div>'
        f"{detail_html}</div>"
    )


def pipeline(response: AgentResponse) -> str:
    """Trace as a left-to-right flow; parallel skills are stacked in one stage."""
    decision = response.decision
    skills = set(decision.skill_names) if decision else set()
    parallel = decision is not None and decision.mode == "parallel"

    stages: list[list[str]] = []
    skill_stage: list[str] = []
    for event in response.trace:
        failed = event.detail.startswith("failed")
        detail = "" if event.node in {"preprocess", "compose"} else event.detail
        if event.node in skills and len(detail) > 90:
            detail = detail[:87] + "…"
        html_node = _node(
            event.node, event.elapsed_ms, event.input_tokens + event.output_tokens, detail, failed
        )
        if parallel and event.node in skills:
            if not skill_stage:
                stages.append(skill_stage)
            skill_stage.append(html_node)
        else:
            stages.append([html_node])

    link = '<div class="sa-link"></div>'
    body = link.join(f'<div class="sa-stage">{"".join(stage)}</div>' for stage in stages)
    return f'<div class="sa-pipeline">{body}</div>'


def kpi(value: str, label: str, icon_name: str, color: str = "#8b9bff") -> str:
    return (
        f'<div class="sa-kpi"><div class="sa-icon-tile" style="--c:{color};margin:0">'
        f'{icon(icon_name)}</div><div><div class="sa-kpi-value">{escape(value)}</div>'
        f'<div class="sa-kpi-label">{escape(label)}</div></div></div>'
    )


def ring_kpi(share: float, value: str, label: str) -> str:
    color = "#34d399" if share >= 0.9 else "#fbbf24" if share >= 0.7 else "#f87171"
    return (
        f'<div class="sa-kpi"><div class="sa-ring" style="--p:{share * 100:.0f};--c:{color}">'
        f'<span>{share:.0%}</span></div><div><div class="sa-kpi-value">{escape(value)}</div>'
        f'<div class="sa-kpi-label">{escape(label)}</div></div></div>'
    )
