"""Shared test utilities: stacked hands and a random-action driver."""

from __future__ import annotations

import random
from typing import Sequence

from holdem.core.cards import Deck, parse_cards
from holdem.core.evaluator import TreysEvaluator
from holdem.engine.actions import Action
from holdem.engine.engine import HandEngine
from holdem.engine.rules import LegalActions
from holdem.io.events import EventBus

EVALUATOR = TreysEvaluator()


def stacked_engine(
    stacks: Sequence[int],
    holes: Sequence[str],
    board: str,
    button: int = 0,
    sb: int = 50,
    bb: int = 100,
    bus: EventBus | None = None,
) -> HandEngine:
    """Engine with a fixed deck. ``holes`` are per seat, e.g. ["AhAs", "KdKc"]."""
    top = [c for h in holes for c in parse_cards(h)] + list(parse_cards(board))
    players = [(f"P{i}", s) for i, s in enumerate(stacks)]
    eng = HandEngine(
        players, button, sb, bb, random.Random(0), EVALUATOR, bus=bus, deck=Deck.stacked(top)
    )
    eng.start()
    return eng


def play_script(eng: HandEngine, script: Sequence[tuple[int, Action]]) -> None:
    """Apply (expected_seat, action) pairs, asserting turn order."""
    for seat, action in script:
        assert eng.state.to_act == seat, f"expected seat {seat}, got {eng.state.to_act}"
        eng.apply(action)


def random_action(legal: LegalActions, rng: random.Random) -> Action:
    roll = rng.random()
    if legal.can_raise and roll < 0.25:
        assert legal.min_raise_to is not None and legal.max_raise_to is not None
        if rng.random() < 0.2:
            return Action.all_in()
        return Action.raise_to(rng.randint(legal.min_raise_to, legal.max_raise_to))
    if roll < 0.40 and not legal.can_check:
        return Action.fold()
    return Action.check() if legal.can_check else Action.call()
