"""Deterministic checks on translations.

Small models occasionally swap facts that look alike, e.g. translating "Thursday" as «جمعه»
(Friday) or dropping a digit. These are cheap to detect without a model, so the translator
verifies them and asks the model for one targeted correction when something is off.
"""

from __future__ import annotations

import re

from skill_agent.text.persian import ZWNJ, detect_language, to_ascii_digits

WEEKDAYS = {
    "saturday": "شنبه",
    "sunday": "یکشنبه",
    "monday": "دوشنبه",
    "tuesday": "سه‌شنبه",
    "wednesday": "چهارشنبه",
    "thursday": "پنجشنبه",
    "friday": "جمعه",
}
_NUMBER = re.compile(r"\d+(?:[.,٫٬]\d+)*")
_ENGLISH_WEEKDAY = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b", re.IGNORECASE)


def _numbers(text: str) -> set[str]:
    found = _NUMBER.findall(to_ascii_digits(text))
    return {re.sub(r"[,٬]", "", n).replace("٫", ".") for n in found}


def _english_weekdays(text: str) -> set[str]:
    return {m.lower() for m in _ENGLISH_WEEKDAY.findall(text)}


_SPLIT_WEEKDAY = re.compile(rf"(یک|دو|سه|چهار|پنج)[\s{ZWNJ}]*شنبه")
_PERSIAN_WEEKDAY = {
    english: re.compile(rf"(?<!\w){persian.replace(ZWNJ, '')}(?!\w)")
    for english, persian in WEEKDAYS.items()
}


def _persian_weekdays(text: str) -> set[str]:
    # «پنج‌شنبه», «پنج شنبه» and «پنجشنبه» are all common; join them before matching whole words
    # (whole words matter: «شنبه» is also the end of «یکشنبه»).
    joined = _SPLIT_WEEKDAY.sub(r"\1شنبه", text)
    return {english for english, pattern in _PERSIAN_WEEKDAY.items() if pattern.search(joined)}


def translation_issues(source: str, translation: str, *, check_numbers: bool = True) -> list[str]:
    """Facts from the source that are missing or changed in the translation.

    Set `check_numbers=False` when the source may include text that is not being translated
    (e.g. a calculation handled by another skill in the same prompt).
    """
    issues = []
    missing = sorted(_numbers(source) - _numbers(translation)) if check_numbers else []
    if missing:
        issues.append(f"numbers missing or changed: {', '.join(missing)}")

    target = detect_language(translation)
    if target == "fa":
        expected, present = _english_weekdays(source), _persian_weekdays(translation)
        issues += [
            f'"{day.title()}" must be translated as «{WEEKDAYS[day]}»'
            for day in sorted(expected - present)
        ]
    elif target == "en":
        expected, present = _persian_weekdays(source), _english_weekdays(translation)
        issues += [
            f"«{WEEKDAYS[day]}» must be translated as {day.title()}"
            for day in sorted(expected - present)
        ]
    return issues
