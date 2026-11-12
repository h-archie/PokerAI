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
) -> MatchResult:
    """Play ``hands`` hands. The button moves every hand, so with a hand count
    that is a multiple of the number of players every agent sits in every
    position equally often."""
    for agent in agents:
        agent.reset()
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
