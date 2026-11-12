"""Main/side pot construction and payout. Pure arithmetic, no game state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Pot:
    amount: int
    eligible: frozenset[int]


def build_pots(contributions: Mapping[int, int], folded: set[int] | frozenset[int]) -> list[Pot]:
    """Split total contributions into a main pot and side pots.

    Folded players' chips go into the pots but they are not eligible to win.
    An uncalled excess forms a final pot whose only eligible seat is the
    player who put it in, so it is returned to them.
    """
    live = {s for s, c in contributions.items() if s not in folded and c > 0}
    if not live:
        raise ValueError("at least one live contributor is required")

    pots: list[Pot] = []
    prev = 0
    for level in sorted({contributions[s] for s in live}):
        amount = sum(min(c, level) - min(c, prev) for c in contributions.values())
        eligible = frozenset(s for s in live if contributions[s] >= level)
        if pots and pots[-1].eligible == eligible:
            pots[-1] = Pot(pots[-1].amount + amount, eligible)
        elif amount:
            pots.append(Pot(amount, eligible))
        prev = level

    # Folded chips above the highest live level (rare): add to the last pot.
    leftover = sum(contributions.values()) - sum(p.amount for p in pots)
    if leftover:
        pots[-1] = Pot(pots[-1].amount + leftover, pots[-1].eligible)
    return pots


def award_pots(
    pots: list[Pot],
    scores: Mapping[int, int],
    button: int,
    num_seats: int,
) -> tuple[dict[int, int], list[tuple[int, frozenset[int]]]]:
    """Distribute pots. ``scores``: lower is stronger.

    Returns (winnings by seat, list of (amount, winners) per pot). Odd chips
    go one at a time to winners starting left of the button.
    """
    winnings: dict[int, int] = {}
    awards: list[tuple[int, frozenset[int]]] = []

    def order(seat: int) -> int:
        return (seat - button - 1) % num_seats

    for pot in pots:
        if len(pot.eligible) == 1:
            winners = sorted(pot.eligible)
        else:
            best = min(scores[s] for s in pot.eligible)
            winners = sorted((s for s in pot.eligible if scores[s] == best), key=order)
        share, odd = divmod(pot.amount, len(winners))
        for i, s in enumerate(winners):
            winnings[s] = winnings.get(s, 0) + share + (1 if i < odd else 0)
        awards.append((pot.amount, frozenset(winners)))
    return winnings, awards
