from __future__ import annotations

import re
import unicodedata

ZWNJ = "‌"

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": None})
_ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")
_REPEATED_ZWNJ = re.compile(f"{ZWNJ}{{2,}}")
_STRAY_ZWNJ = re.compile(rf"{ZWNJ}(?=\s)|(?<=\s){ZWNJ}|^{ZWNJ}|{ZWNJ}$", re.MULTILINE)
_SPACES = re.compile(r"[ \t ]+")


def to_ascii_digits(text: str) -> str:
    """Map Persian (U+06F0..) and Arabic-Indic (U+0660..) digits to ASCII."""
    return text.translate(_DIGITS)


def normalize_text(text: str) -> str:
    """Light, meaning-preserving cleanup for Persian (and mixed) input.

    Arabic yeh/kaf become their Persian forms, tatweel is dropped and ZWNJ is tidied, so the same
    word always looks the same to the router and the shortlister. Digits and line breaks are left
    alone: the translator and summarizer should see the text as the user wrote it.
    """
    text = unicodedata.normalize("NFC", text).translate(_LETTERS)
    text = _REPEATED_ZWNJ.sub(ZWNJ, text)
    text = _STRAY_ZWNJ.sub("", text)
    text = _SPACES.sub(" ", text)
    return "\n".join(line.strip() for line in text.strip().splitlines())


def detect_language(text: str) -> str:
    """Rough script-based guess: "fa", "en", or "unknown" when there are no letters.

    It is only a default; the router decides the response language from the full message.
    """
    persian = len(_ARABIC_SCRIPT.findall(text))
    latin = len(_LATIN.findall(text))
    if persian == latin == 0:
        return "unknown"
    return "fa" if persian >= latin else "en"


def is_rtl(language: str) -> bool:
    return language in {"fa", "ar", "ur", "he", "ps", "ckb"}
