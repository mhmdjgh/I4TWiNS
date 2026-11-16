"""The few fixed strings the agent writes itself (everything else comes from the model)."""

from __future__ import annotations

_MESSAGES: dict[str, dict[str, str]] = {
    "clarify.generic": {
        "en": "I'm not sure what you'd like me to do. Should I summarize, translate, calculate, "
        "or just chat? Please add a bit more detail.",
        "fa": "مطمئن نیستم دقیقاً چه کاری می‌خواهید. خلاصه کنم، ترجمه کنم، محاسبه کنم یا فقط "
        "گفت‌وگو کنیم؟ لطفاً کمی بیشتر توضیح دهید.",
    },
    "clarify.need_text": {
        "en": "Sure. Please send the text you would like me to summarize.",
        "fa": "حتماً. لطفاً متنی را که می‌خواهید خلاصه کنم بفرستید.",
    },
    "skill.failed": {
        "en": "This part could not be completed: {error}",
        "fa": "این بخش انجام نشد: {error}",
    },
    "agent.unavailable": {
        "en": "Sorry, the language model is not reachable right now. Please try again shortly.",
        "fa": "متأسفم، در حال حاضر به مدل زبانی دسترسی ندارم. لطفاً کمی بعد دوباره تلاش کنید.",
    },
}


def t(key: str, language: str, **values: object) -> str:
    variants = _MESSAGES[key]
    return variants.get(language, variants["en"]).format(**values)
