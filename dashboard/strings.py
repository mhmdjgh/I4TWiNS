"""Interface text. The interface is English; the agent itself still reads and answers Persian."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    "auth.prompt": "Enter the password to use this dashboard.",
    "auth.label": "Password",
    "auth.button": "Sign in",
    "auth.wrong": "That password isn't right. Try again.",
    "nav.chat": "Assistant",
    "nav.architecture": "How it works",
    "nav.evaluation": "Evaluation",
    "brand.tagline": "Summarize · Translate · Calculate · Chat",
    "side.status": "Model",
    "side.connected": "Connected",
    "side.no_key": "No API key",
    "side.reasoning": "Reasoning",
    "side.max_skills": "Skills per request",
    "side.new_chat": "New conversation",
    "side.stateless": (
        "Each message is handled on its own; the agent keeps no memory between messages."
    ),
    "chat.hero.title": "One prompt. The right skills.",
    "chat.hero.subtitle": (
        "Write in English or Persian. The agent decides whether to summarize, translate, "
        "calculate or chat, runs up to two skills, and shows you how it got there."
    ),
    "chat.try": "Try one of these",
    "chat.placeholder": "Ask anything, in English or Persian…",
    "chat.thinking": "Routing and running skills…",
    "chat.done": "Done",
    "chat.behind": "Behind the scenes",
    "chat.pipeline": "Pipeline",
    "chat.routing": "Routing decision",
    "chat.tools": "Tool calls",
    "chat.steps": "Intermediate results",
    "chat.raw": "Raw JSON",
    "chat.no_tools": "No tools were called.",
    "chat.no_steps": "Single step: no intermediate results.",
    "chat.clarify": "Clarification",
    "chat.reasoning": "Why",
    "chat.instruction": "Instruction",
    "chat.target": "Target language",
    "chat.span": "Works on",
    "chat.no_key": (
        "Add LLM_API_KEY to .env to start chatting. Everything else on this page works without it."
    ),
    "meta.mode.single": "single",
    "meta.mode.parallel": "parallel",
    "meta.mode.sequential": "sequential",
    "meta.confidence": "confidence",
    "meta.tokens": "tokens",
    "arch.title": "How it works",
    "arch.subtitle": (
        "A LangGraph agent: one routing call decides the skills, skill nodes run in parallel or "
        "as a chain, and deterministic code handles fallbacks and checks."
    ),
    "arch.lifecycle": "Life of a request",
    "arch.graph": "The graph",
    "arch.compiled": "Graph as compiled by LangGraph",
    "arch.skills": "Skills",
    "arch.skills.note": (
        "The router only ever sees these cards. Full skill prompts load inside each node."
    ),
    "arch.when": "Use when",
    "arch.context": "Context protection",
    "arch.context.note": (
        "Every model call must fit its window as skills are added and run together."
    ),
    "eval.title": "Evaluation",
    "eval.subtitle": (
        "15 labelled prompts in English and Persian: clear, multi-skill, ambiguous and no-skill "
        "cases."
    ),
    "eval.accuracy": "Skill detection",
    "eval.cases": "Cases",
    "eval.latency": "Avg. latency",
    "eval.errors": "Provider errors",
    "eval.by_category": "By category",
    "eval.by_skill": "By skill",
    "eval.case_list": "Cases",
    "eval.filter.all": "All",
    "eval.filter.pass": "Passed",
    "eval.filter.fail": "Missed",
    "eval.expected": "expected",
    "eval.got": "got",
    "eval.answer": "Answer",
    "eval.show_answers": "Show answers",
    "eval.empty": "No evaluation results yet. Run `skill-agent eval` to create them.",
    "eval.source.official": "Committed results",
    "eval.source.local": "Latest local run",
    "eval.rerun": "Run routing evaluation",
    "eval.rerun.note": (
        "Uses one request per case (15 in total). Saved as a local run; the committed results are"
        " never overwritten."
    ),
}


def t(key: str) -> str:
    return STRINGS[key]
