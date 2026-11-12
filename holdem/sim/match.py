"""Run a match of N hands and collect per-hand results for every agent."""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Sequence

from holdem.agents.base import Agent
from holdem.core.evaluator import HandEvaluator
from holdem.sim.table import StackMode, Table


@dataclass
class MatchResult:
    names: list[str]
    big_blind: int
    # deltas[i][h] = chips agent i won (+) or lost (-) on hand h
    deltas: list[list[int]] = field(default_factory=list)
    warnings: Counter[str] = field(default_factory=Counter)
    # Consecutive hands that belong together (duplicate rotations of one deal).
    # Metrics compute confidence intervals over these blocks.
    block: int = 1

    @property
    def hands(self) -> int:
        return len(self.deltas[0]) if self.deltas else 0


def run_match(
    agents: Sequence[Agent],
    hands: int,
    seed: int = 0,
    small_blind: int = 50,
    big_blind: int = 100,
    starting_stack: int = 10_000,
    stack_mode: StackMode = "reset",
    evaluator: HandEvaluator | None = None,
    progress: Callable[[int, int], None] | None = None,
    duplicate: bool = False,
) -> MatchResult:
    """Play ``hands`` hands. The button moves every hand, so with a hand count
    that is a multiple of the number of players every agent sits in every
    position equally often.

    ``duplicate=True`` removes most card luck: every deal is replayed once per
    seat rotation, so each agent plays every set of hole cards. ``hands`` is
    the total number of hands played (rounded down to a multiple of the
    number of agents). Requires stack_mode="reset".
    """
    for agent in agents:
        agent.reset()
    if duplicate:
        if stack_mode != "reset":
            raise ValueError("duplicate matches need stack_mode='reset'")
        return _run_duplicate(
            agents, hands, seed, small_blind, big_blind, starting_stack, evaluator, progress
        )
    table = Table(
        agents,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_stack=starting_stack,
        rng=random.Random(f"{seed}-deck"),
        evaluator=evaluator,
        stack_mode=stack_mode,
    )
    result = MatchResult([a.name for a in agents], big_blind, [[] for _ in agents])
    for h in range(hands):
        hand = table.play_hand()
        for i in range(len(agents)):
            result.deltas[i].append(hand.net[i])
        if progress and (h + 1) % 100 == 0:
            progress(h + 1, hands)
    result.warnings = table.warnings
    return result


def _run_duplicate(
    agents: Sequence[Agent],
    hands: int,
    seed: int,
    small_blind: int,
    big_blind: int,
    starting_stack: int,
    evaluator: HandEvaluator | None,
    progress: Callable[[int, int], None] | None,
) -> MatchResult:
    n = len(agents)
    # Table r seats the agents rotated by r: seat i holds agent (i + r) % n.
    tables = [
        Table(
            [agents[(i + r) % n] for i in range(n)],
            small_blind=small_blind,
            big_blind=big_blind,
            starting_stack=starting_stack,
            evaluator=evaluator,
        )
        for r in range(n)
    ]
    result = MatchResult([a.name for a in agents], big_blind, [[] for _ in agents], block=n)
    played = 0
    for deal in range(hands // n):
        deck_seed = f"{seed}-dup-{deal}"
        for r, table in enumerate(tables):
            hand = table.play_hand(deck_seed=deck_seed)
            for seat in range(n):
                result.deltas[(seat + r) % n].append(hand.net[seat])
            played += 1
            if progress and played % 100 == 0:
                progress(played, hands)
    for table in tables:
        result.warnings.update(table.warnings)
    return result
