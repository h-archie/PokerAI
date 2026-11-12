"""Hand ranges: "the top X% of starting hands" as concrete two-card combos.

Hands are ranked by preflop equity against one random opponent, and the
percentage counts combos (a pair has 6, a suited hand 4, an offsuit hand 12),
so "top 10%" means roughly 133 of the 1326 possible starting hands.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations

from holdem.ai.preflop import _table, all_hand_classes, hand_class
from holdem.core.cards import FULL_DECK, Card

Combo = tuple[Card, Card]
TOTAL_COMBOS = 1326


@lru_cache(maxsize=1)
def _combos_by_class() -> dict[str, list[Combo]]:
    out: dict[str, list[Combo]] = {c: [] for c in all_hand_classes()}
    for a, b in combinations(FULL_DECK, 2):
        out[hand_class((a, b))].append((a, b))
    return out


@lru_cache(maxsize=1)
def ranked_classes() -> list[str]:
    """All 169 hand classes, strongest first."""
    table = _table()
    return sorted(all_hand_classes(), key=lambda c: table[c][0], reverse=True)


@lru_cache(maxsize=128)
def _top_range(percent: int) -> tuple[Combo, ...]:
    by_class = _combos_by_class()
    target = TOTAL_COMBOS * percent / 100
    out: list[Combo] = []
    for cls in ranked_classes():
        if len(out) >= target:
            break
        out.extend(by_class[cls])
    return tuple(out)


def top_range(fraction: float) -> tuple[Combo, ...]:
    """Combos in the strongest ``fraction`` (0-1) of starting hands.

    Rounded to whole percents so results can be cached. Always includes at
    least the top 1% (aces and kings).
    """
    percent = min(100, max(1, round(fraction * 100)))
    return _top_range(percent)
