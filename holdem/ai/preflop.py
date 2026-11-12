"""Preflop strength from a precomputed equity table (no simulation at runtime).

The table holds the equity of each of the 169 distinct starting hands against
1-5 random opponents. Rebuild it with ``python scripts/build_preflop_table.py``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Sequence

from holdem.core.cards import Card, Rank, Suit

MAX_OPPONENTS = 5


def hand_class(hole: Sequence[Card]) -> str:
    """Canonical name: "AA", "AKs" (suited) or "AKo" (offsuit), high card first."""
    a, b = sorted(hole, key=lambda c: c.rank, reverse=True)
    if a.rank == b.rank:
        return a.rank.symbol * 2
    return f"{a.rank.symbol}{b.rank.symbol}{'s' if a.suit == b.suit else 'o'}"


def all_hand_classes() -> list[str]:
    ranks = sorted(Rank, reverse=True)
    out = []
    for i, hi in enumerate(ranks):
        for lo in ranks[i:]:
            if hi == lo:
                out.append(hi.symbol * 2)
            else:
                out += [f"{hi.symbol}{lo.symbol}s", f"{hi.symbol}{lo.symbol}o"]
    return out


def representative(cls: str) -> tuple[Card, Card]:
    """Concrete hole cards for a hand class (used to build the table)."""
    hi, lo = Rank.from_symbol(cls[0]), Rank.from_symbol(cls[1])
    second_suit = Suit.SPADES if cls.endswith("s") else Suit.HEARTS
    return Card(hi, Suit.SPADES), Card(lo, second_suit)


@lru_cache(maxsize=1)
def _table() -> dict[str, list[float]]:
    text = resources.files("holdem.ai").joinpath("data/preflop_equity.json").read_text()
    return json.loads(text)["equity"]


def preflop_equity(hole: Sequence[Card], n_opponents: int) -> float:
    """Equity of ``hole`` against ``n_opponents`` random hands (clamped to 1-5)."""
    n = min(max(n_opponents, 1), MAX_OPPONENTS)
    return _table()[hand_class(hole)][n - 1]
