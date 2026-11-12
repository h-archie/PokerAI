"""Build agents by short name, e.g. for the CLI: "smart", "random", "calling"."""

from __future__ import annotations

import random
from typing import Callable

from holdem.agents.base import Agent
from holdem.agents.baseline import AlwaysRaise, CallingStation, RandomAgent, TightPassive
from holdem.agents.smart import SmartAgent
from holdem.core.evaluator import HandEvaluator

Factory = Callable[[str, random.Random, HandEvaluator], Agent]

AGENTS: dict[str, tuple[Factory, str]] = {
    "smart": (lambda n, r, e: SmartAgent(n, rng=r, evaluator=e), "equity + pot odds bot"),
    "random": (lambda n, r, e: RandomAgent(n, rng=r), "random fold/call/raise"),
    "calling": (lambda n, r, e: CallingStation(n), "always checks or calls"),
    "raise": (lambda n, r, e: AlwaysRaise(n), "min-raises whenever it can"),
    "tight": (lambda n, r, e: TightPassive(n), "plays only strong hands, never raises"),
}


def make_agents(kinds: list[str], seed: int, evaluator: HandEvaluator) -> list[Agent]:
    """Create agents with unique names ("smart", "smart2", ...) and seeded RNGs."""
    agents: list[Agent] = []
    counts: dict[str, int] = {}
    for i, kind in enumerate(kinds):
        if kind not in AGENTS:
            raise ValueError(f"unknown agent {kind!r}; choose from {', '.join(AGENTS)}")
        counts[kind] = counts.get(kind, 0) + 1
        name = kind if counts[kind] == 1 else f"{kind}{counts[kind]}"
        factory, _ = AGENTS[kind]
        agents.append(factory(name, random.Random(f"{seed}-agent-{i}"), evaluator))
    return agents
