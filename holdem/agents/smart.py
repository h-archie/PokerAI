"""SmartAgent: the real bot. Orchestration only; all logic lives in holdem.ai."""

from __future__ import annotations

import random

from holdem.agents.base import Agent
from holdem.ai import policy, sizing
from holdem.ai.equity import estimate_equity
from holdem.ai.policy import Decision, PolicyParams
from holdem.ai.preflop import preflop_equity
from holdem.core.evaluator import HandEvaluator, TreysEvaluator
from holdem.engine.actions import Action
from holdem.engine.state import Street
from holdem.engine.view import PlayerView
from holdem.io.events import Event, HandStarted


class SmartAgent(Agent):
    def __init__(
        self,
        name: str | None = None,
        params: PolicyParams | None = None,
        evaluator: HandEvaluator | None = None,
        rng: random.Random | None = None,
        iterations: int = 300,
    ) -> None:
        super().__init__(name)
        self.params = params or PolicyParams()
        self.evaluator = evaluator or TreysEvaluator()
        self.rng = rng or random.Random()
        self.iterations = iterations
        self._cache: dict[tuple, float] = {}
        # Exposed for logging / the demo: why the last action was chosen.
        self.last_equity: float | None = None
        self.last_decision: Decision | None = None

    def equity(self, view: PlayerView, n_opponents: int) -> float:
        assert view.hole is not None
        if view.street is Street.PREFLOP:
            return preflop_equity(view.hole, n_opponents)
        key = (view.hole, view.board, n_opponents)
        if key not in self._cache:
            self._cache[key] = estimate_equity(
                view.hole, view.board, n_opponents, self.rng, self.evaluator, self.iterations
            ).equity
        return self._cache[key]

    def act(self, view: PlayerView) -> Action:
        n_opponents = len(view.active_seats) - 1
        eq = self.equity(view, n_opponents)
        decision = policy.decide(view, eq, n_opponents, self.params, self.rng)
        self.last_equity, self.last_decision = eq, decision
        return sizing.to_action(decision.intent, view)

    def on_event(self, event: Event) -> None:
        if isinstance(event, HandStarted):
            self._cache.clear()
