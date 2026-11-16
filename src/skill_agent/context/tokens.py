from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Cheap, provider-independent token estimate.

    Roughly 4 characters per token for ASCII and 2 for other scripts. Persian is split into
    noticeably more tokens than English by most tokenizers, so the estimate errs on the high
    side for it, which is the safe direction for a budget.
    """
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    return math.ceil(ascii_chars / 4 + (len(text) - ascii_chars) / 2)


def excerpt(text: str, max_tokens: int) -> str:
    """Keep the head and tail of a long text and mark what was cut.

    Used for routing: the request is almost always at the start or the end of a message, while
    the long middle is the document to process, which the router does not need to read.
    """
    total = estimate_tokens(text)
    if total <= max_tokens:
        return text
    chars_per_token = len(text) / total
    head = int(max_tokens * 0.65 * chars_per_token)
    tail = int(max_tokens * 0.3 * chars_per_token)
    omitted = total - max_tokens
    return f"{text[:head]}\n[... about {omitted} tokens omitted ...]\n{text[-tail:]}"
