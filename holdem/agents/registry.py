"""Build agents by short name, e.g. for the CLI: "hard", "random", "calling".

Difficulty levels are all the same SmartAgent with different skill settings:

| level    | misreads hands | mistakes | calls too much | learns opponents |
|----------|----------------|----------|----------------|------------------|
| beginner | a lot (±20%)   | 25%      | a lot          | no               |
| easy     | some (±10%)    | 10%      | a bit          | no               |
| medium   | no             | no       | no             | no               |
| hard     | no             | no       | no             | yes              |
"""

from __future__ import annotations

import random
from typing import Any, Callable

from holdem.agents.base import Agent
from holdem.agents.baseline import AlwaysRaise, CallingStation, RandomAgent, TightPassive
from holdem.agents.smart import SmartAgent
from holdem.ai.policy import PolicyParams
from holdem.core.evaluator import HandEvaluator

Factory = Callable[[str, random.Random, HandEvaluator], Agent]

DIFFICULTY: dict[str, dict[str, Any]] = {
    "beginner": dict(
        params=PolicyParams(call_margin=-0.15, bluff_freq=0.02, value_edge=0.22, strong_edge=0.38),
        equity_noise=0.20,
        mistake_rate=0.25,
        iterations=100,
    ),
    "easy": dict(
        params=PolicyParams(call_margin=-0.06, bluff_freq=0.05),
        equity_noise=0.10,
        mistake_rate=0.10,
        iterations=150,
    ),
    "medium": dict(),
    "hard": dict(use_model=True),
}
DIFFICULTY_ORDER = list(DIFFICULTY)


def _smart(level: str) -> Factory:
    return lambda n, r, e: SmartAgent(n, rng=r, evaluator=e, **DIFFICULTY[level])


AGENTS: dict[str, tuple[Factory, str]] = {
    "beginner": (_smart("beginner"), "difficulty 1: misreads hands, calls far too much"),
    "easy": (_smart("easy"), "difficulty 2: some misreads and mistakes"),
    "medium": (_smart("medium"), "difficulty 3: solid equity + pot-odds play"),
    "hard": (_smart("hard"), "difficulty 4: medium + learns and exploits opponents"),
    "smart": (_smart("medium"), "alias for medium"),
    "random": (lambda n, r, e: RandomAgent(n, rng=r), "random fold/call/raise"),
    "calling": (lambda n, r, e: CallingStation(n), "always checks or calls"),
    "raise": (lambda n, r, e: AlwaysRaise(n), "min-raises whenever it can"),
    "tight": (lambda n, r, e: TightPassive(n), "plays only strong hands, never raises"),
}


def make_agent(kind: str, name: str, rng: random.Random, evaluator: HandEvaluator) -> Agent:
    if kind not in AGENTS:
        raise ValueError(f"unknown agent {kind!r}; choose from {', '.join(AGENTS)}")
    factory, _ = AGENTS[kind]
    return factory(name, rng, evaluator)


def make_agents(kinds: list[str], seed: int, evaluator: HandEvaluator) -> list[Agent]:
    """Create agents with unique names ("smart", "smart2", ...) and seeded RNGs."""
    agents: list[Agent] = []
    counts: dict[str, int] = {}
    for i, kind in enumerate(kinds):
        counts[kind] = counts.get(kind, 0) + 1
        name = kind if counts[kind] == 1 else f"{kind}{counts[kind]}"
        agents.append(make_agent(kind, name, random.Random(f"{seed}-agent-{i}"), evaluator))
    return agents
