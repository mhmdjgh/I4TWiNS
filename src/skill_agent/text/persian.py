from __future__ import annotations

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_ascii_digits(text: str) -> str:
    """Map Persian (U+06F0..) and Arabic-Indic (U+0660..) digits to ASCII."""
    return text.translate(_DIGITS)
