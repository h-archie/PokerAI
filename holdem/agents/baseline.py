"""Simple benchmark opponents. Each is a few lines and easy to reason about."""

from __future__ import annotations

import random

from holdem.agents.base import Agent
from holdem.ai.preflop import preflop_equity
from holdem.ai.sizing import passive
from holdem.engine.actions import Action
from holdem.engine.state import Street
from holdem.engine.view import PlayerView


class RandomAgent(Agent):
    """Picks uniformly between fold / call / raise (never folds when it can check)."""

    def __init__(self, name: str | None = None, rng: random.Random | None = None) -> None:
        super().__init__(name)
        self.rng = rng or random.Random()

    def act(self, view: PlayerView) -> Action:
        legal = view.legal
        assert legal is not None
        options = ["passive", "raise"] if legal.can_check else ["fold", "passive", "raise"]
        if not legal.can_raise:
            options.remove("raise")
        choice = self.rng.choice(options)
        if choice == "fold":
            return Action.fold()
        if choice == "passive":
            return passive(view)
        assert legal.min_raise_to is not None and legal.max_raise_to is not None
        high = min(legal.max_raise_to, legal.min_raise_to + view.pot)
        return Action.raise_to(self.rng.randint(legal.min_raise_to, high))


class CallingStation(Agent):
    """Never folds, never raises: always checks or calls."""

    def act(self, view: PlayerView) -> Action:
        return passive(view)


class AlwaysRaise(Agent):
    """Maniac: min-raises whenever allowed, otherwise calls."""

    def act(self, view: PlayerView) -> Action:
        legal = view.legal
        assert legal is not None
        if legal.can_raise:
            assert legal.min_raise_to is not None
            return Action.raise_to(legal.min_raise_to)
        return passive(view)


class TightPassive(Agent):
    """Rock: plays only strong starting hands, then calls down. Never raises."""

    def __init__(self, name: str | None = None, min_edge: float = 0.10) -> None:
        super().__init__(name)
        self.min_edge = min_edge
        self._playing = False

    def act(self, view: PlayerView) -> Action:
        legal = view.legal
        assert legal is not None and view.hole is not None
        if view.street is Street.PREFLOP:
            n_opp = len(view.active_seats) - 1
            fair = 1.0 / (n_opp + 1)
            self._playing = preflop_equity(view.hole, n_opp) - fair >= self.min_edge
        if legal.can_check or self._playing:
            return passive(view)
        return Action.fold()
