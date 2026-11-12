"""Play Texas Hold'em against bots in the terminal.

    python play.py                                   # you vs 2 medium bots
    python play.py --difficulty hard --opponents 4
    python play.py --bots beginner,easy,hard         # mix difficulty levels

Stacks carry over between hands. A bot that goes broke rebuys automatically;
if you go broke you are offered a rebuy. Type q at any prompt to stop.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from holdem.agents.human import HumanAgent
from holdem.agents.registry import DIFFICULTY, make_agent
from holdem.agents.base import Agent, StopGame
from holdem.agents.smart import SmartAgent
from holdem.core.evaluator import TreysEvaluator
from holdem.io.events import EventBus
from holdem.io.hand_history import HandHistoryWriter
from holdem.io.narrator import Narrator
from holdem.sim.table import Table

BOT_NAMES = ["Bob", "Carol", "Dave", "Erin", "Frank"]


@dataclass
class SessionResult:
    hands_played: int
    buy_ins: int
    final_stack: int
    starting_stack: int
    history_path: Path | None

    @property
    def net(self) -> int:
        return self.final_stack - self.buy_ins * self.starting_stack


def default_history_path() -> Path:
    return Path("history") / f"game-{datetime.now():%Y%m%d-%H%M%S}.jsonl"


def play_session(
    bots: list[str],
    stack: int = 1000,
    small_blind: int = 10,
    big_blind: int = 20,
    seed: int | None = None,
    input_fn: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
    delay: float = 0.6,
    pretty: bool = True,
    history_path: Path | None = None,
    max_hands: int | None = None,
) -> SessionResult:
    if not 1 <= len(bots) <= 5:
        raise ValueError("choose between 1 and 5 bots")
    for level in bots:
        if level not in DIFFICULTY:
            raise ValueError(f"unknown difficulty {level!r}; choose from {', '.join(DIFFICULTY)}")

    seed = seed if seed is not None else random.randrange(10**9)
    evaluator = TreysEvaluator()
    human = HumanAgent("You", input_fn=input_fn, out=out, pretty=pretty)
    agents: list[Agent] = [human]
    for i, level in enumerate(bots):
        name = f"{BOT_NAMES[i]} [{level}]"
        agents.append(make_agent(level, name, random.Random(f"{seed}-bot-{i}"), evaluator))

    bus = EventBus()
    Narrator(bus, out=out, pretty=pretty, you=0, delay=delay, evaluator=evaluator)
    writer = HandHistoryWriter(bus, history_path) if history_path else None
    table = Table(
        agents,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_stack=stack,
        rng=random.Random(f"{seed}-deck"),
        evaluator=evaluator,
        bus=bus,
        stack_mode="carry",
    )

    out(f"\nWelcome to the table! Blinds {small_blind}/{big_blind}, everyone starts with {stack}.")
    out("Opponents: " + ", ".join(a.name for a in agents[1:]))
    out("Type ? on your turn for help, q to quit.")

    hands = 0
    buy_ins = 1
    try:
        while max_hands is None or hands < max_hands:
            if table.stacks[0] < big_blind:
                answer = input_fn(f"\nYou're out of chips! Rebuy for {stack}? (y/n) > ").strip().lower()
                if not answer.startswith("y"):
                    break
                buy_ins += 1
            for i, s in enumerate(table.stacks[1:], start=1):
                if s < big_blind:
                    out(f"\n  {agents[i].name} is broke and rebuys for {stack}.")
            table.play_hand()
            hands += 1
            answer = input_fn("\n[Enter] next hand, [q] quit > ").strip().lower()
            if answer.startswith("q"):
                break
    except (StopGame, KeyboardInterrupt):
        out("\n(Leaving the table...)")

    result = SessionResult(hands, buy_ins, table.stacks[0], stack, history_path if writer else None)
    _print_summary(result, agents, out)
    return result


def _print_summary(result: SessionResult, agents: list[Agent], out: Callable[[str], None]) -> None:
    out("\n=== Session over ===")
    out(f"  Hands played: {result.hands_played}")
    out(f"  Buy-ins:      {result.buy_ins} x {result.starting_stack}")
    out(f"  Final chips:  {result.final_stack}")
    out(f"  Net result:   {result.net:+d}")
    # A "hard" bot keeps notes on you; show what it learned.
    for agent in agents:
        if isinstance(agent, SmartAgent) and agent.model is not None and result.hands_played:
            s = agent.model.stats("You")
            out(f"\n  What {agent.name} learned about you over {s.hands} hands:")
            out(f"    plays {s.vpip:.0%} of hands, raises preflop {s.pfr:.0%}, "
                f"aggression {s.aggression:.0%}, folds to bets {s.fold_to_bet:.0%}")
            out(f"    -> it thinks you are {s.style}")
            break
    if result.history_path:
        out(f"\n  Hand history saved to {result.history_path}")
        out(f"  Replay a hand with: python -m holdem.cli replay {result.history_path} --hand 1")
