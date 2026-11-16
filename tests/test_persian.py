import pytest

from skill_agent.text.persian import ZWNJ, detect_language, is_rtl, normalize_text, to_ascii_digits


def test_arabic_letters_become_persian() -> None:
    assert normalize_text("كتاب علي") == "کتاب علی"


def test_tatweel_and_spaces_removed() -> None:
    assert normalize_text("  سـلام   دنیا  ") == "سلام دنیا"


def test_zwnj_is_tidied_not_removed() -> None:
    assert normalize_text(f"می{ZWNJ}{ZWNJ}شود") == f"می{ZWNJ}شود"
    assert normalize_text(f"کتاب {ZWNJ}ها") == "کتاب ها"
    assert ZWNJ in normalize_text(f"کتاب{ZWNJ}ها")


def test_line_breaks_and_digits_preserved() -> None:
    assert normalize_text("خط ۱\nخط ۲") == "خط ۱\nخط ۲"


def test_ascii_digits() -> None:
    assert to_ascii_digits("۱۲۳ و ٤٥٦") == "123 و 456"


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("سلام، حالت چطوره؟", "fa"),
        ("Hello there", "en"),
        ("این متن را ترجمه کن: Hello world", "fa"),
        ("Translate to English: سلام", "en"),
        ("2 + 2 = ?", "unknown"),
    ],
)
def test_detect_language(text: str, language: str) -> None:
    assert detect_language(text) == language


def test_rtl() -> None:
    assert is_rtl("fa") and not is_rtl("en")
