"""Monte Carlo equity: how often does this hand win against random opponent hands?"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from holdem.core.cards import FULL_DECK, Card
from holdem.core.evaluator import HandEvaluator


@dataclass(frozen=True, slots=True)
class EquityResult:
    win: float  # fraction of samples won outright
    tie: float  # fraction of samples tied for best
    equity: float  # win + share of ties; this is the number decisions use
    samples: int


Combo = tuple[Card, Card]


def estimate_equity(
    hole: Sequence[Card],
    board: Sequence[Card],
    n_opponents: int,
    rng: random.Random,
    evaluator: HandEvaluator,
    iterations: int = 300,
    opp_ranges: Sequence[Sequence[Combo] | None] | None = None,
) -> EquityResult:
    """Estimate equity versus ``n_opponents``.

    By default opponents hold uniformly random hands. ``opp_ranges`` can give,
    per opponent, the list of combos they might hold (see ``ai.ranges``);
    ``None`` for an opponent means "any two cards".
    """
    if n_opponents < 1:
        raise ValueError("need at least one opponent")
    if opp_ranges is not None:
        if len(opp_ranges) != n_opponents:
            raise ValueError("need one range (or None) per opponent")
        if any(r for r in opp_ranges):
            return _ranged_equity(hole, board, rng, evaluator, iterations, opp_ranges)
    if len(hole) != 2 or len(board) > 5:
        raise ValueError("need 2 hole cards and at most 5 board cards")
    known = set(hole) | set(board)
    if len(known) != len(hole) + len(board):
        raise ValueError("duplicate cards")

    remaining = [c for c in FULL_DECK if c not in known]
    board = list(board)
    need_board = 5 - len(board)
    draw = need_board + 2 * n_opponents
    score = evaluator.score

    wins = ties = 0
    share = 0.0
    for _ in range(iterations):
        sample = rng.sample(remaining, draw)
        full_board = board + sample[:need_board]
        mine = score(hole, full_board)
        best_opp = None
        n_best = 0
        for i in range(need_board, draw, 2):
            s = score(sample[i : i + 2], full_board)
            if best_opp is None or s < best_opp:
                best_opp, n_best = s, 1
            elif s == best_opp:
                n_best += 1
        assert best_opp is not None
        if mine < best_opp:
            wins += 1
            share += 1.0
        elif mine == best_opp:
            ties += 1
            share += 1.0 / (n_best + 1)

    return EquityResult(wins / iterations, ties / iterations, share / iterations, iterations)


def _ranged_equity(
    hole: Sequence[Card],
    board: Sequence[Card],
    rng: random.Random,
    evaluator: HandEvaluator,
    iterations: int,
    opp_ranges: Sequence[Sequence[Combo] | None],
) -> EquityResult:
    """Like estimate_equity, but opponents' hands are drawn from their ranges."""
    if len(hole) != 2 or len(board) > 5:
        raise ValueError("need 2 hole cards and at most 5 board cards")
    known = set(hole) | set(board)
    if len(known) != len(hole) + len(board):
        raise ValueError("duplicate cards")
    remaining = [c for c in FULL_DECK if c not in known]
    # Pre-filter each range to combos that don't clash with our visible cards.
    ranges = [
        [h for h in r if h[0] not in known and h[1] not in known] if r else None
        for r in opp_ranges
    ]
    board = list(board)
    need_board = 5 - len(board)
    score = evaluator.score

    wins = ties = 0
    share = 0.0
    for _ in range(iterations):
        used: set[Card] = set()
        hands: list[Sequence[Card] | None] = []
        for r in ranges:
            pick = None
            if r:
                for _try in range(30):  # reject combos clashing with other opponents
                    h = r[rng.randrange(len(r))]
                    if h[0] not in used and h[1] not in used:
                        pick = h
                        break
            if pick is not None:
                used.update(pick)
            hands.append(pick)
        pool = [c for c in remaining if c not in used] if used else remaining
        n_random = sum(h is None for h in hands)
        sample = rng.sample(pool, need_board + 2 * n_random)
        full_board = board + sample[:need_board]
        k = need_board
        for i, h in enumerate(hands):
            if h is None:
                hands[i] = sample[k : k + 2]
                k += 2

        mine = score(hole, full_board)
        opp_scores = [score(h, full_board) for h in hands]  # type: ignore[arg-type]
        best = min(opp_scores)
        if mine < best:
            wins += 1
            share += 1.0
        elif mine == best:
            ties += 1
            share += 1.0 / (opp_scores.count(best) + 1)

    return EquityResult(wins / iterations, ties / iterations, share / iterations, iterations)
