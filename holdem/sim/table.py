"""Table: seats agents, drives HandEngine hand after hand, rotates the button.

A buggy agent can never crash a long simulation: exceptions and illegal
actions are caught, counted in ``warnings``, and replaced with check/fold.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Literal, Sequence

from holdem.agents.base import Agent, StopGame
from holdem.core.evaluator import HandEvaluator, TreysEvaluator
from holdem.engine.actions import Action
from holdem.engine.engine import HandEngine, HandResult
from holdem.engine.rules import IllegalAction, LegalActions
from holdem.io.events import Event, EventBus

StackMode = Literal["reset", "carry"]


def safe_fallback(legal: LegalActions) -> Action:
    return Action.check() if legal.can_check else Action.fold()


class Table:
    def __init__(
        self,
        agents: Sequence[Agent],
        small_blind: int = 50,
        big_blind: int = 100,
        starting_stack: int = 10_000,
        rng: random.Random | None = None,
        evaluator: HandEvaluator | None = None,
        bus: EventBus | None = None,
        stack_mode: StackMode = "reset",
    ) -> None:
        """``stack_mode``: "reset" gives everyone ``starting_stack`` every hand
        (independent hands, lower variance). "carry" keeps stacks between hands
        and rebuys anyone who drops below one big blind."""
        if len(agents) < 2:
            raise ValueError("need at least 2 agents")
        if len({a.name for a in agents}) != len(agents):
            raise ValueError("agent names must be unique")
        self.agents = list(agents)
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.starting_stack = starting_stack
        self.rng = rng or random.Random()
        self.evaluator = evaluator or TreysEvaluator()
        self.bus = bus or EventBus()
        self.stack_mode = stack_mode
        self.stacks = [starting_stack] * len(agents)
        self.rebuys = [0] * len(agents)
        self.button = 0
        self.hand_id = 1
        self.warnings: Counter[str] = Counter()
        for agent in self.agents:
            self.bus.subscribe(self._safe_handler(agent))

    def _safe_handler(self, agent: Agent):
        def handler(event: Event) -> None:
            try:
                agent.on_event(event)
            except Exception as exc:  # noqa: BLE001 - isolate agent bugs
                self.warnings[f"{agent.name}: on_event {type(exc).__name__}"] += 1

        return handler

    def _ask(self, engine: HandEngine, seat: int) -> None:
        agent = self.agents[seat]
        view = engine.view_for(seat)
        assert view.legal is not None
        try:
            action = agent.act(view)
            engine.apply(action)
            return
        except StopGame:
            raise
        except IllegalAction:
            self.warnings[f"{agent.name}: illegal action"] += 1
        except Exception as exc:  # noqa: BLE001 - isolate agent bugs
            self.warnings[f"{agent.name}: act {type(exc).__name__}"] += 1
        engine.apply(safe_fallback(view.legal))

    def play_hand(self, deck_seed: int | str | None = None) -> HandResult:
        """Play one hand. ``deck_seed`` fixes the shuffle (used by duplicate
        matches to deal identical cards at several tables)."""
        if self.stack_mode == "reset":
            self.stacks = [self.starting_stack] * len(self.agents)
        else:
            for i, s in enumerate(self.stacks):
                if s < self.big_blind:
                    self.stacks[i] = self.starting_stack
                    self.rebuys[i] += 1

        engine = HandEngine(
            [(a.name, s) for a, s in zip(self.agents, self.stacks)],
            button=self.button,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            rng=self.rng if deck_seed is None else random.Random(deck_seed),
            evaluator=self.evaluator,
            bus=self.bus,
            hand_id=self.hand_id,
        )
        engine.start()
        while not engine.is_over:
            assert engine.state.to_act is not None
            self._ask(engine, engine.state.to_act)

        result = engine.result()
        self.stacks = [result.final_stacks[i] for i in range(len(self.agents))]
        self.button = (self.button + 1) % len(self.agents)
        self.hand_id += 1
        return result
