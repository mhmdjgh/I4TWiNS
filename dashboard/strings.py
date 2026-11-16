"""Interface text in English and Persian. The agent's own answers are not translated here."""

from __future__ import annotations

import streamlit as st

STRINGS: dict[str, dict[str, str]] = {
    "nav.chat": {"en": "Assistant", "fa": "دستیار"},
    "nav.architecture": {"en": "How it works", "fa": "معماری"},
    "nav.evaluation": {"en": "Evaluation", "fa": "ارزیابی"},
    "brand.tagline": {
        "en": "Summarize · Translate · Calculate · Chat",
        "fa": "خلاصه · ترجمه · محاسبه · گفت‌وگو",
    },
    "side.language": {"en": "Interface language", "fa": "زبان رابط"},
    "side.status": {"en": "Model", "fa": "مدل"},
    "side.connected": {"en": "Connected", "fa": "متصل"},
    "side.no_key": {"en": "No API key", "fa": "کلید API تنظیم نشده"},
    "side.reasoning": {"en": "Reasoning", "fa": "استدلال"},
    "side.max_skills": {"en": "Skills per request", "fa": "اسکیل در هر درخواست"},
    "side.new_chat": {"en": "New conversation", "fa": "گفت‌وگوی جدید"},
    "side.stateless": {
        "en": "Each message is handled on its own; the agent keeps no memory between messages.",
        "fa": "هر پیام جداگانه پردازش می‌شود و دستیار حافظه‌ای از پیام‌های قبلی ندارد.",
    },
    "chat.hero.title": {"en": "One prompt. The right skills.", "fa": "یک پیام، اسکیل‌های درست."},
    "chat.hero.subtitle": {
        "en": "Write in English or Persian. The agent decides whether to summarize, translate, "
        "calculate or chat, runs up to two skills, and shows you how it got there.",
        "fa": "به فارسی یا انگلیسی بنویسید. دستیار تشخیص می‌دهد باید خلاصه کند، ترجمه کند، "
        "محاسبه کند یا گفت‌وگو کند، تا دو اسکیل را اجرا می‌کند و مسیرش را نشان می‌دهد.",
    },
    "chat.try": {"en": "Try one of these", "fa": "یکی از این‌ها را امتحان کنید"},
    "chat.placeholder": {
        "en": "Ask anything, in English or Persian…",
        "fa": "هر چیزی بپرسید، به فارسی یا انگلیسی…",
    },
    "chat.thinking": {
        "en": "Routing and running skills…",
        "fa": "در حال مسیریابی و اجرای اسکیل‌ها…",
    },
    "chat.done": {"en": "Done", "fa": "انجام شد"},
    "chat.behind": {"en": "Behind the scenes", "fa": "پشت صحنه"},
    "chat.pipeline": {"en": "Pipeline", "fa": "مسیر اجرا"},
    "chat.routing": {"en": "Routing decision", "fa": "تصمیم مسیریاب"},
    "chat.tools": {"en": "Tool calls", "fa": "فراخوانی ابزار"},
    "chat.steps": {"en": "Intermediate results", "fa": "نتایج میانی"},
    "chat.raw": {"en": "Raw JSON", "fa": "JSON خام"},
    "chat.no_tools": {"en": "No tools were called.", "fa": "ابزاری فراخوانی نشد."},
    "chat.no_steps": {
        "en": "Single step: no intermediate results.",
        "fa": "تک‌مرحله‌ای؛ نتیجه‌ی میانی ندارد.",
    },
    "chat.clarify": {"en": "Clarification", "fa": "درخواست توضیح"},
    "chat.reasoning": {"en": "Why", "fa": "دلیل"},
    "chat.instruction": {"en": "Instruction", "fa": "دستور"},
    "chat.target": {"en": "Target language", "fa": "زبان مقصد"},
    "chat.span": {"en": "Works on", "fa": "روی این بخش"},
    "chat.no_key": {
        "en": "Add LLM_API_KEY to .env to start chatting. "
        "Everything else on this page works without it.",
        "fa": "برای شروع گفت‌وگو LLM_API_KEY را در فایل ‎.env‎ تنظیم کنید.",
    },
    "meta.mode.single": {"en": "single", "fa": "تکی"},
    "meta.mode.parallel": {"en": "parallel", "fa": "موازی"},
    "meta.mode.sequential": {"en": "sequential", "fa": "زنجیره‌ای"},
    "meta.confidence": {"en": "confidence", "fa": "اطمینان"},
    "meta.tokens": {"en": "tokens", "fa": "توکن"},
    "arch.title": {"en": "How it works", "fa": "معماری سیستم"},
    "arch.subtitle": {
        "en": "A LangGraph agent: one routing call decides the skills, skill nodes run in "
        "parallel or as a chain, and deterministic code handles fallbacks and checks.",
        "fa": "یک ایجنت LangGraph: یک فراخوانی مسیریاب اسکیل‌ها را انتخاب می‌کند، اسکیل‌ها موازی "
        "یا زنجیره‌ای اجرا می‌شوند و کد قطعی مسئول حالت‌های جایگزین و بررسی‌هاست.",
    },
    "arch.lifecycle": {"en": "Life of a request", "fa": "مسیر یک درخواست"},
    "arch.graph": {"en": "The graph", "fa": "گراف"},
    "arch.compiled": {"en": "Graph as compiled by LangGraph", "fa": "گراف کامپایل‌شده‌ی LangGraph"},
    "arch.skills": {"en": "Skills", "fa": "اسکیل‌ها"},
    "arch.skills.note": {
        "en": "The router only ever sees these cards. Full skill prompts load inside each node.",
        "fa": "مسیریاب فقط همین کارت‌ها را می‌بیند؛ "
        "پرامپت کامل هر اسکیل فقط داخل نود خودش بارگذاری می‌شود.",
    },
    "arch.when": {"en": "Use when", "fa": "کاربرد"},
    "arch.context": {"en": "Context protection", "fa": "محافظت از context"},
    "arch.context.note": {
        "en": "Every model call must fit its window as skills are added and run together.",
        "fa": "با اضافه شدن اسکیل‌ها و اجرای هم‌زمان آن‌ها، "
        "هر فراخوانی مدل باید در پنجره‌ی context جا شود.",
    },
    "eval.title": {"en": "Evaluation", "fa": "ارزیابی"},
    "eval.subtitle": {
        "en": "15 labelled prompts in English and Persian: clear, multi-skill, ambiguous and "
        "no-skill cases.",
        "fa": "۱۵ پرامپت برچسب‌خورده به فارسی و انگلیسی: حالت‌های واضح، چند اسکیلی، مبهم و بی‌ربط.",
    },
    "eval.accuracy": {"en": "Skill detection", "fa": "تشخیص اسکیل"},
    "eval.cases": {"en": "Cases", "fa": "نمونه‌ها"},
    "eval.latency": {"en": "Avg. latency", "fa": "میانگین زمان"},
    "eval.errors": {"en": "Provider errors", "fa": "خطای سرویس"},
    "eval.by_category": {"en": "By category", "fa": "به تفکیک دسته"},
    "eval.by_skill": {"en": "By skill", "fa": "به تفکیک اسکیل"},
    "eval.case_list": {"en": "Cases", "fa": "نمونه‌ها"},
    "eval.filter.all": {"en": "All", "fa": "همه"},
    "eval.filter.pass": {"en": "Passed", "fa": "درست"},
    "eval.filter.fail": {"en": "Missed", "fa": "خطا"},
    "eval.expected": {"en": "expected", "fa": "انتظار"},
    "eval.got": {"en": "got", "fa": "نتیجه"},
    "eval.answer": {"en": "Answer", "fa": "پاسخ"},
    "eval.show_answers": {"en": "Show answers", "fa": "نمایش پاسخ‌ها"},
    "eval.empty": {
        "en": "No evaluation results yet. Run `skill-agent eval` to create them.",
        "fa": "هنوز نتیجه‌ای ثبت نشده. برای ساختن آن `skill-agent eval` را اجرا کنید.",
    },
    "eval.source.official": {"en": "Committed results", "fa": "نتایج ثبت‌شده"},
    "eval.source.local": {"en": "Latest local run", "fa": "آخرین اجرای محلی"},
    "eval.rerun": {"en": "Run routing evaluation", "fa": "اجرای ارزیابی مسیریابی"},
    "eval.rerun.note": {
        "en": "Uses one request per case (15 in total). Saved as a local run; the committed "
        "results are never overwritten.",
        "fa": "به ازای هر نمونه یک درخواست مصرف می‌کند (جمعاً ۱۵) "
        "و به‌عنوان اجرای محلی ذخیره می‌شود؛ نتایج ثبت‌شده هرگز بازنویسی نمی‌شوند.",
    },
}


def language() -> str:
    lang = st.session_state.get("ui_lang", "en")
    return lang if lang in ("en", "fa") else "en"


def t(key: str) -> str:
    return STRINGS[key][language()]
