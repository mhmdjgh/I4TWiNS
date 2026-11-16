from __future__ import annotations

import re

from skill_agent.context.tokens import estimate_tokens

_PARAGRAPHS = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?؟…])\s+|(?<=\n)")
_INSTRUCTION_END = re.compile(r"[:：\n]")


def split_instruction(prompt: str, max_instruction_chars: int = 300) -> tuple[str, str]:
    """Split "summarize this: <long text>" into ("summarize this", "<long text>").

    Heuristic: the instruction ends at the first colon or line break within the first few hundred
    characters. Without one, the whole prompt is treated as the text.
    """
    match = _INSTRUCTION_END.search(prompt[:max_instruction_chars])
    if not match:
        return "", prompt
    instruction, text = prompt[: match.start()].strip(), prompt[match.end() :].strip()
    return (instruction, text) if text else ("", prompt)


def _split_long(piece: str, max_tokens: int) -> list[str]:
    sentences = [s for s in _SENTENCE_END.split(piece) if s.strip()]
    if len(sentences) > 1:
        return sentences
    words, parts, current = piece.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and estimate_tokens(candidate) > max_tokens:
            parts.append(current)
            current = word
        else:
            current = candidate
    return [*parts, current] if current else parts


def chunk_text(text: str, max_tokens: int) -> list[str]:
    """Pack paragraphs (then sentences, then words) into chunks of at most `max_tokens`.

    Boundaries respect Persian punctuation (؟) so a chunk never ends mid-sentence unless a single
    sentence is longer than the budget.
    """
    # (separator to put before the piece, piece)
    pieces: list[tuple[str, str]] = []
    for paragraph in _PARAGRAPHS.split(text.strip()):
        units = [paragraph]
        if estimate_tokens(paragraph) > max_tokens:
            units = []
            for sentence in _split_long(paragraph, max_tokens):
                too_long = estimate_tokens(sentence) > max_tokens
                units.extend(_split_long(sentence, max_tokens) if too_long else [sentence])
        units = [u.strip() for u in units if u.strip()]
        pieces.extend(("\n\n" if i == 0 else " ", unit) for i, unit in enumerate(units))

    chunks: list[str] = []
    current = ""
    for separator, piece in pieces:
        candidate = f"{current}{separator}{piece}" if current else piece
        if current and estimate_tokens(candidate) > max_tokens:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
