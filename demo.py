"""Watch one hand of Hold'em play out, step by step.

    python demo.py                                  # smart vs random vs calling
    python demo.py --seed 11 --agents smart,smart,tight,raise

Agents: smart, random, calling, raise, tight (see `python -m holdem.cli agents`).
For the smart bot, the demo also prints *why* it chose each action.

The narrator shows everyone's hole cards up front (like a TV broadcast); the
bots themselves only ever see their own cards via PlayerView.
"""

from __future__ import annotations

import argparse
import random

from holdem.agents.registry import make_agents
from holdem.agents.smart import SmartAgent
from holdem.core.evaluator import TreysEvaluator
from holdem.engine.actions import ActionType
from holdem.engine.engine import HandEngine
from holdem.engine.state import Street
from holdem.io import events as ev

NAMES = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank"]


def cards(cs) -> str:
    return " ".join(str(c) for c in cs)


class Narrator:
    """Subscribes to the event bus and prints what happens."""

    def __init__(self, bus: ev.EventBus, names: list[str], width: int = 6) -> None:
        self.names = names
        self.w = width
        self.evaluator = TreysEvaluator()
        self.board: tuple = ()
        bus.subscribe(self.on_event)

    def n(self, seat: int) -> str:
        return self.names[seat]

    def on_event(self, e: ev.Event) -> None:
        if isinstance(e, ev.HandStarted):
            print(f"=== Hand #{e.hand_id}  |  blinds {e.small_blind}/{e.big_blind} ===")
            for seat, name, stack in e.seats:
                tag = "  (button)" if seat == e.button else ""
                print(f"  Seat {seat}: {name:<{self.w}} {stack:>5} chips{tag}")
            print()
        elif isinstance(e, ev.BlindPosted):
            print(f"  {self.n(e.seat)} posts blind {e.amount}")
        elif isinstance(e, ev.StreetAdvanced):
            self.board = e.board
            print(f"\n--- {Street(e.street).name}: [{cards(e.board)}] ---")
        elif isinstance(e, ev.ActionTaken):
            a = e.action
            verb = {
                ActionType.FOLD: "folds",
                ActionType.CHECK: "checks",
                ActionType.CALL: f"calls (to {a.amount})",
                ActionType.BET: f"bets {a.amount}",
                ActionType.RAISE: f"raises to {a.amount}",
                ActionType.ALL_IN: f"goes ALL-IN ({a.amount})",
            }[a.type]
            print(f"  {self.n(e.seat):<{self.w}} {verb:<22} pot: {e.pot}")
        elif isinstance(e, ev.ShowdownEvent):
            print("\n--- SHOWDOWN ---")
            for seat, hole in e.hands:
                score = self.evaluator.score(hole, self.board)
                label = self.evaluator.category(score).label
                print(f"  {self.n(seat):<{self.w}} shows [{cards(hole)}]  ->  {label}")
        elif isinstance(e, ev.PotAwarded):
            who = " & ".join(self.n(s) for s in sorted(e.winners))
            kind = "Main pot" if e.pot_index == 0 else f"Side pot {e.pot_index}"
            print(f"\n  {kind} of {e.amount} -> {who}")
        elif isinstance(e, ev.HandEnded):
            print("\n=== Result ===")
            for seat, delta in e.net:
                print(f"  {self.n(seat):<{self.w}} {delta:+d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=7, help="random seed (same seed = same hand)")
    ap.add_argument("--agents", default="smart,random,calling", help="2-6 comma-separated agents")
    ap.add_argument("--stack", type=int, default=1000)
    args = ap.parse_args()

    kinds = [k.strip() for k in args.agents.split(",") if k.strip()]
    if not 2 <= len(kinds) <= 6:
        ap.error("need between 2 and 6 agents")
    evaluator = TreysEvaluator()
    agents = make_agents(kinds, args.seed, evaluator)
    names = [f"{NAMES[i]} ({a.name})" for i, a in enumerate(agents)]
    width = max(len(n) for n in names)

    bus = ev.EventBus()
    Narrator(bus, names, width)
    for agent in agents:
        bus.subscribe(agent.on_event)

    engine = HandEngine(
        [(n, args.stack) for n in names],
        button=0,
        small_blind=10,
        big_blind=20,
        rng=random.Random(args.seed),
        evaluator=evaluator,
        bus=bus,
        hand_id=args.seed,
    )
    engine.start()

    print("\n  Hole cards (narrator only - each bot sees just its own):")
    for p in engine.state.players:
        print(f"    {p.name:<{width}} [{cards(p.hole)}]")
    print("\n--- PREFLOP ---")

    while not engine.is_over:
        seat = engine.state.to_act
        agent = agents[seat]
        view = engine.view_for(seat)  # the ONLY thing a bot is given
        action = agent.act(view)
        if isinstance(agent, SmartAgent) and agent.last_decision:
            print(f"  {names[seat]:<{width}} thinks: {agent.last_decision.reason}")
        engine.apply(action)  # the narrator prints the action itself

    r = engine.result()
    print("\n  Final stacks:", ", ".join(f"{names[s]} {v}" for s, v in r.final_stacks.items()))


if __name__ == "__main__":
    main()
