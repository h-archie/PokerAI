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


def estimate_equity(
    hole: Sequence[Card],
    board: Sequence[Card],
    n_opponents: int,
    rng: random.Random,
    evaluator: HandEvaluator,
    iterations: int = 300,
) -> EquityResult:
    """Estimate equity versus ``n_opponents`` holding uniformly random hands.

    Each sample deals the opponents two cards each and completes the board
    from the cards that are not visible to us.
    """
    if n_opponents < 1:
        raise ValueError("need at least one opponent")
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
