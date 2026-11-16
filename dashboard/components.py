"""Small HTML building blocks used by the pages. All user-provided text is escaped."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from strings import language, t

from skill_agent.agent import AgentResponse


@dataclass(frozen=True)
class Look:
    color: str
    en: str
    fa: str

    @property
    def label(self) -> str:
        return self.fa if language() == "fa" else self.en


LOOKS: dict[str, Look] = {
    "summarizer": Look("#8b5cf6", "Summarizer", "خلاصه‌ساز"),
    "translator": Look("#0ea5e9", "Translator", "مترجم"),
    "calculator": Look("#f59e0b", "Calculator", "ماشین‌حساب"),
    "general_chat": Look("#10b981", "Chat", "گفت‌وگو"),
    "clarify": Look("#a8a29e", "Clarification", "درخواست توضیح"),
    "preprocess": Look("#a8a29e", "Preprocess", "پیش‌پردازش"),
    "router": Look("#4f46e5", "Router", "مسیریاب"),
    "compose": Look("#57534e", "Compose", "ترکیب"),
}


def look(name: str) -> Look:
    return LOOKS.get(name, Look("#4f46e5", name, name))


def icon(name: str) -> str:
    return f'<span class="material-symbols-rounded">{name}</span>'


def skill(name: str) -> str:
    item = look(name)
    return f'<span class="sa-skill" style="--c:{item.color}">{escape(item.label)}</span>'


def heading(title: str, subtitle: str = "") -> str:
    sub = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    return f'<div class="sa-head"><h1>{escape(title)}</h1>{sub}</div>'


def subheading(title: str, subtitle: str = "") -> str:
    sub = f'<div class="sa-sub">{escape(subtitle)}</div>' if subtitle else ""
    return f'<div class="sa-h2">{escape(title)}</div>{sub}'


def meta_line(response: AgentResponse) -> str:
    """One quiet line under an answer: skills, mode, time."""
    decision = response.decision
    sep = '<span class="sep">·</span>'
    if decision is None or decision.needs_clarification:
        skills = skill("clarify" if decision else "general_chat")
        mode = ""
    else:
        joiner = " → " if decision.mode == "sequential" else " + "
        skills = joiner.join(skill(step.skill) for step in decision.skills)
        mode = t(f"meta.mode.{decision.mode}") if len(decision.skills) > 1 else ""
    parts = [skills, mode, f"{response.elapsed_ms / 1000:.1f}s"]
    return f'<div class="sa-meta">{sep.join(p for p in parts if p)}</div>'


def steps(response: AgentResponse) -> str:
    """Execution trace as a vertical list; works the same on phones and desktops."""
    decision = response.decision
    parallel = decision is not None and decision.mode == "parallel"
    skill_names = set(decision.skill_names) if decision else set()
    rows = []
    for event in response.trace:
        item = look(event.node)
        detail = "" if event.node in {"preprocess", "compose"} else event.detail
        tokens = event.input_tokens + event.output_tokens
        if tokens:
            detail = f"{detail} · {tokens:,} tokens" if detail else f"{tokens:,} tokens"
        classes = ["sa-step"]
        if parallel and event.node in skill_names:
            classes.append("parallel")
        if event.detail.startswith("failed"):
            classes.append("failed")
        seconds = f"{event.elapsed_ms / 1000:.2f}s" if event.elapsed_ms >= 10 else "—"
        rows.append(
            f'<div class="{" ".join(classes)}" style="--c:{item.color}"><span class="dot"></span>'
            f"<div><b>{escape(item.label)}</b><small>{escape(detail)}</small></div>"
            f'<span class="time">{seconds}</span></div>'
        )
    return f'<div class="sa-steps">{"".join(rows)}</div>'


def stat(value: str, label: str) -> str:
    body = f'<div class="v">{escape(value)}</div><div class="l">{escape(label)}</div>'
    return f'<div class="sa-stat">{body}</div>'


def meter(label: str, share: float, text: str) -> str:
    warn = " warn" if share < 0.9 else ""
    return (
        f'<div class="sa-meter"><span>{label}</span><div class="track">'
        f'<div class="fill{warn}" style="width:{share * 100:.0f}%"></div></div>'
        f"<span>{escape(text)}</span></div>"
    )
