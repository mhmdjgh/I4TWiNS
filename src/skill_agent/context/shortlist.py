from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from skill_agent.skills.base import SkillCard
from skill_agent.text.persian import normalize_text

_WORD = re.compile(r"\w+")


def _normalize(text: str) -> str:
    return normalize_text(text).lower()


def _words(text: str) -> set[str]:
    return set(_WORD.findall(_normalize(text)))


class Shortlister:
    """Pre-selects the skill cards worth showing to the router.

    With a handful of skills every card goes into the router prompt. Past `threshold` skills, the
    prompt would grow linearly with the catalogue, so a cheap lexical score (keyword phrases plus
    IDF-weighted word overlap, in both Persian and English, no LLM call) keeps only the `top_k`
    most relevant cards. The fallback skill is always kept so the router can still fall back.
    """

    def __init__(
        self, cards: Sequence[SkillCard], fallback: str, threshold: int, top_k: int
    ) -> None:
        self.cards = list(cards)
        self.fallback = fallback
        self.threshold = threshold
        self.top_k = top_k
        self._vocab = {card.name: self._card_words(card) for card in self.cards}
        document_freq = Counter(word for words in self._vocab.values() for word in words)
        n = len(self.cards)
        self._idf = {w: math.log((n + 1) / (df + 0.5)) for w, df in document_freq.items()}

    @staticmethod
    def _card_words(card: SkillCard) -> set[str]:
        text = " ".join([card.name.replace("_", " "), card.summary, *card.examples, *card.keywords])
        return _words(text)

    def score(self, card: SkillCard, query: str) -> float:
        normalized = _normalize(query)
        query_words = _words(query)
        phrase_hits = sum(1 for kw in card.keywords if _normalize(kw) in normalized)
        overlap = sum(self._idf.get(w, 0.0) for w in query_words & self._vocab[card.name])
        return 3.0 * phrase_hits + overlap

    def select(self, query: str) -> list[SkillCard]:
        if len(self.cards) <= self.threshold:
            return self.cards
        ranked = sorted(self.cards, key=lambda c: self.score(c, query), reverse=True)
        keep = {card.name for card in ranked[: self.top_k]} | {self.fallback}
        return [card for card in self.cards if card.name in keep]  # stable prompt order
