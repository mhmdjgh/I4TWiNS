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


_VERBATIM = re.compile(r"`[^`]*`|https?://\S+|\S+@\S+\.\w+")
_LOWERCASE_LATIN_WORD = re.compile(r"\b[a-z]{3,}\b")


def _latin_leftovers(persian_text: str) -> list[str]:
    """Lower-case Latin-script words inside a Persian translation («…postponed شده است»).

    Capitalized words are left alone because names and brands are often kept in Latin script,
    and code, URLs and e-mail addresses are skipped because they must stay unchanged.
    """
    prose = _VERBATIM.sub(" ", persian_text)
    return sorted(set(_LOWERCASE_LATIN_WORD.findall(prose)))


_LANGUAGE_CODES = {
    "persian": "fa",
    "farsi": "fa",
    "fa": "fa",
    "فارسی": "fa",
    "english": "en",
    "en": "en",
    "انگلیسی": "en",
}


def target_code(target_language: str | None, source: str) -> str | None:
    """Language code the translation should be in, when it can be known without the output.

    Guessing from the output itself fails exactly when the output is wrong: «ببینمت tomorrow»
    has more Latin than Persian letters and would look like an English translation.
    """
    if target_language is None:
        return "en" if detect_language(source) == "fa" else "fa"
    return _LANGUAGE_CODES.get(target_language.strip().lower())


def translation_issues(
    source: str,
    translation: str,
    *,
    check_numbers: bool = True,
    target: str | None = None,
) -> list[str]:
    """Facts from the source that are missing or changed in the translation.

    Set `check_numbers=False` when the source may include text that is not being translated
    (e.g. a calculation handled by another skill in the same prompt). `target` is the expected
    language code; without it the language is guessed from the translation.
    """
    issues = []
    missing = sorted(_numbers(source) - _numbers(translation)) if check_numbers else []
    if missing:
        issues.append(f"numbers missing or changed: {', '.join(missing)}")

    target = target or detect_language(translation)
    if target == "fa":
        expected, present = _english_weekdays(source), _persian_weekdays(translation)
        issues += [
            f'"{day.title()}" must be translated as «{WEEKDAYS[day]}»'
            for day in sorted(expected - present)
        ]
        leftovers = _latin_leftovers(translation)
        if leftovers:
            issues.append(
                "words in Latin script left in the Persian text (write them in Persian): "
                + ", ".join(leftovers)
            )
    elif target == "en":
        expected, present = _persian_weekdays(source), _english_weekdays(translation)
        issues += [
            f"«{WEEKDAYS[day]}» must be translated as {day.title()}"
            for day in sorted(expected - present)
        ]
    return issues
