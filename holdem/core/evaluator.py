"""Hand evaluation behind a small adapter interface.

Convention: ``score`` returns an int where **lower is stronger**. Scores are
only comparable between hands scored by the same evaluator.
"""

from __future__ import annotations

from collections import Counter
from enum import IntEnum
from itertools import combinations
from typing import Protocol, Sequence

from treys import Card as TreysCard
from treys import Evaluator as _TreysEvaluator

from holdem.core.cards import Card


class HandCategory(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


class HandEvaluator(Protocol):
    def score(self, hole: Sequence[Card], board: Sequence[Card]) -> int: ...

    def category(self, score: int) -> HandCategory: ...


def _check_size(hole: Sequence[Card], board: Sequence[Card]) -> None:
    n = len(hole) + len(board)
    if not 5 <= n <= 7:
        raise ValueError(f"need 5-7 cards to evaluate, got {n}")


class TreysEvaluator:
    """Fast lookup-table evaluator (default)."""

    # Upper score bound (inclusive) for each category, from treys' LookupTable.
    _THRESHOLDS: tuple[tuple[int, HandCategory], ...] = (
        (10, HandCategory.STRAIGHT_FLUSH),
        (166, HandCategory.FOUR_OF_A_KIND),
        (322, HandCategory.FULL_HOUSE),
        (1599, HandCategory.FLUSH),
        (1609, HandCategory.STRAIGHT),
        (2467, HandCategory.THREE_OF_A_KIND),
        (3325, HandCategory.TWO_PAIR),
        (6185, HandCategory.PAIR),
        (7462, HandCategory.HIGH_CARD),
    )

    def __init__(self) -> None:
        self._ev = _TreysEvaluator()
        self._cache: dict[Card, int] = {}

    def _to_treys(self, cards: Sequence[Card]) -> list[int]:
        out = []
        for c in cards:
            v = self._cache.get(c)
            if v is None:
                v = self._cache[c] = TreysCard.new(str(c))
            out.append(v)
        return out

    def score(self, hole: Sequence[Card], board: Sequence[Card]) -> int:
        _check_size(hole, board)
        return self._ev.evaluate(self._to_treys(hole), self._to_treys(board))

    def category(self, score: int) -> HandCategory:
        for bound, cat in self._THRESHOLDS:
            if score <= bound:
                return cat
        raise ValueError(f"score out of range: {score}")


class NaiveEvaluator:
    """Slow, obviously-correct pure-Python evaluator. Used as a test oracle."""

    _BASE = 15  # ranks are 2..14
    _MAX = _BASE**6

    @staticmethod
    def _five_key(cards: Sequence[Card]) -> tuple[int, ...]:
        ranks = sorted((c.rank for c in cards), reverse=True)
        counts = Counter(ranks)
        # Ranks ordered by (count, rank) descending, e.g. full house -> [trips, pair].
        grouped = sorted(counts, key=lambda r: (counts[r], r), reverse=True)
        shape = sorted(counts.values(), reverse=True)
        flush = len({c.suit for c in cards}) == 1
        uniq = sorted(set(ranks), reverse=True)
        straight_high = 0
        if len(uniq) == 5:
            if uniq[0] - uniq[4] == 4:
                straight_high = uniq[0]
            elif uniq == [14, 5, 4, 3, 2]:  # wheel
                straight_high = 5

        if straight_high and flush:
            return (HandCategory.STRAIGHT_FLUSH, straight_high)
        if shape == [4, 1]:
            return (HandCategory.FOUR_OF_A_KIND, *grouped)
        if shape == [3, 2]:
            return (HandCategory.FULL_HOUSE, *grouped)
        if flush:
            return (HandCategory.FLUSH, *ranks)
        if straight_high:
            return (HandCategory.STRAIGHT, straight_high)
        if shape == [3, 1, 1]:
            return (HandCategory.THREE_OF_A_KIND, *grouped)
        if shape == [2, 2, 1]:
            return (HandCategory.TWO_PAIR, *grouped)
        if shape == [2, 1, 1, 1]:
            return (HandCategory.PAIR, *grouped)
        return (HandCategory.HIGH_CARD, *ranks)

    def score(self, hole: Sequence[Card], board: Sequence[Card]) -> int:
        _check_size(hole, board)
        best = max(self._five_key(combo) for combo in combinations([*hole, *board], 5))
        encoded = 0
        for part in (*best, *([0] * (6 - len(best)))):
            encoded = encoded * self._BASE + int(part)
        return self._MAX - encoded  # invert so lower is stronger

    def category(self, score: int) -> HandCategory:
        return HandCategory((self._MAX - score) // self._BASE**5)
