"""Language codes and names as the router and the skills write them."""

from __future__ import annotations

_CODES = {
    "persian": "fa",
    "farsi": "fa",
    "fa": "fa",
    "فارسی": "fa",
    "english": "en",
    "en": "en",
    "انگلیسی": "en",
}
_NAMES = {"fa": "Persian", "en": "English", "fr": "French", "de": "German", "ar": "Arabic"}


def language_code(language: str) -> str | None:
    """The code for a Persian or English name or code ("Farsi", "فارسی", "fa"); None otherwise."""
    return _CODES.get(language.strip().lower())


def language_name(code: str) -> str | None:
    return _NAMES.get(code)
