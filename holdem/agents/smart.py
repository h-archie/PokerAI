"""SmartAgent: the real bot. Orchestration only; all logic lives in holdem.ai.

Knobs used by the difficulty levels:
- ``equity_noise``: random error added to its hand-strength estimate (misreads)
- ``mistake_rate``: chance of just checking/calling instead of its real choice
- ``use_model``: learn opponents' habits and play against their likely hands
"""

from __future__ import annotations

import random

from holdem.agents.base import Agent
from holdem.ai import policy, sizing
from holdem.ai.equity import estimate_equity
from holdem.ai.opponent_model import OpponentModel
from holdem.ai.policy import Decision, Intent, PolicyParams
from holdem.ai.preflop import preflop_equity
from holdem.ai.ranges import top_range
from holdem.core.evaluator import HandEvaluator, TreysEvaluator
from holdem.engine.actions import Action, ActionType
from holdem.engine.state import Street
from holdem.engine.view import PlayerView
from holdem.io.events import Event, HandStarted

AGGRESSIVE = (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)


class SmartAgent(Agent):
    def __init__(
        self,
        name: str | None = None,
        params: PolicyParams | None = None,
        evaluator: HandEvaluator | None = None,
        rng: random.Random | None = None,
        iterations: int = 300,
        equity_noise: float = 0.0,
        mistake_rate: float = 0.0,
        use_model: bool = False,
    ) -> None:
        super().__init__(name)
        self.params = params or PolicyParams()
        self.evaluator = evaluator or TreysEvaluator()
        self.rng = rng or random.Random()
        self.iterations = iterations
        self.equity_noise = equity_noise
        self.mistake_rate = mistake_rate
        self.model = OpponentModel() if use_model else None
        self._cache: dict[tuple, float] = {}
        # Exposed for logging / the demo: why the last action was chosen.
        self.last_equity: float | None = None
        self.last_decision: Decision | None = None

    # ------------------------------------------------------- hand reading

    def range_fractions(self, view: PlayerView) -> list[float]:
        """For each opponent still in the hand: the share of starting hands
        they are likely to hold, given their habits and actions this hand."""
        assert self.model is not None
        out = []
        for seat in sorted(view.active_seats - {view.seat}):
            stats = self.model.stats_for_seat(seat)
            if stats is None:
                out.append(1.0)
                continue
            pre = [h.action.type for h in view.history if h.street is Street.PREFLOP and h.seat == seat]
            raises = sum(t in AGGRESSIVE for t in pre)
            if raises:
                frac = stats.pfr * 0.5 ** (raises - 1)  # each re-raise halves the range
            elif ActionType.CALL in pre:
                frac = stats.vpip
            else:
                frac = 1.0  # e.g. a big blind who checked: could be anything
            if view.street is not Street.PREFLOP and any(
                h.street == view.street and h.seat == seat and h.action.type in AGGRESSIVE
                for h in view.history
            ):
                # Betting now: strong more often, unless they bet everything.
                frac *= 0.4 + 0.6 * stats.aggression
            out.append(min(1.0, max(0.02, frac)))
        return out

    def equity(self, view: PlayerView, n_opponents: int) -> float:
        assert view.hole is not None
        fractions = self.range_fractions(view) if self.model else []
        narrowed = any(f < 0.99 for f in fractions)
        if view.street is Street.PREFLOP and not narrowed:
            return preflop_equity(view.hole, n_opponents)
        key = (view.hole, view.board, n_opponents, tuple(round(f, 2) for f in fractions))
        if key not in self._cache:
            ranges = [top_range(f) if f < 0.99 else None for f in fractions] if narrowed else None
            self._cache[key] = estimate_equity(
                view.hole,
                view.board,
                n_opponents,
                self.rng,
                self.evaluator,
                self.iterations,
                opp_ranges=ranges,
            ).equity
        return self._cache[key]

    def fold_to_bet_read(self, view: PlayerView) -> float | None:
        if self.model is None:
            return None
        stats = [self.model.stats_for_seat(s) for s in view.active_seats - {view.seat}]
        known = [s.fold_to_bet for s in stats if s is not None]
        return sum(known) / len(known) if known else None

    # ---------------------------------------------------------- interface

    def act(self, view: PlayerView) -> Action:
        assert view.legal is not None
        n_opponents = len(view.active_seats) - 1
        eq = self.equity(view, n_opponents)
        if self.equity_noise:
            eq = min(1.0, max(0.0, eq + self.rng.gauss(0.0, self.equity_noise)))
        decision = policy.decide(
            view, eq, n_opponents, self.params, self.rng, fold_to_bet=self.fold_to_bet_read(view)
        )
        if self.mistake_rate and self.rng.random() < self.mistake_rate:
            passive = Intent.CHECK if view.legal.can_check else Intent.CALL
            decision = Decision(passive, f"mistake! (meant to: {decision.reason})")
        self.last_equity, self.last_decision = eq, decision
        return sizing.to_action(decision.intent, view)

    def on_event(self, event: Event) -> None:
        if isinstance(event, HandStarted):
            self._cache.clear()
        if self.model is not None:
            self.model.on_event(event)

    def reset(self) -> None:
        if self.model is not None:
            self.model = OpponentModel(self.model.prior_weight)
