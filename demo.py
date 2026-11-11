"""Watch one hand of Hold'em play out, step by step.

    python demo.py                 # 3 players, seed 7
    python demo.py --seed 11 --players 4

The players here are throwaway "random but sensible" bots so there is some
betting to watch. Real bots arrive on Day 2. The narrator shows everyone's
hole cards up front (like a TV broadcast); the bots themselves only ever see
their own cards via PlayerView.
"""

from __future__ import annotations

import argparse
import random

from holdem.core.evaluator import TreysEvaluator
from holdem.engine.actions import Action, ActionType
from holdem.engine.engine import HandEngine
from holdem.engine.rules import LegalActions
from holdem.engine.state import Street
from holdem.io import events as ev

NAMES = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank"]


def cards(cs) -> str:
    return " ".join(str(c) for c in cs)


def demo_bot(legal: LegalActions, pot: int, rng: random.Random) -> Action:
    """Mostly checks/calls, sometimes bets about half the pot, occasionally folds."""
    roll = rng.random()
    if legal.can_raise and roll < 0.25:
        assert legal.min_raise_to is not None and legal.max_raise_to is not None
        target = legal.min_raise_to + pot // 2
        return Action.raise_to(min(max(target, legal.min_raise_to), legal.max_raise_to))
    if not legal.can_check and roll > 0.80:
        return Action.fold()
    return Action.check() if legal.can_check else Action.call()


class Narrator:
    """Subscribes to the event bus and prints what happens."""

    def __init__(self, bus: ev.EventBus, names: list[str]) -> None:
        self.names = names
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
                print(f"  Seat {seat}: {name:<6} {stack:>5} chips{tag}")
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
            print(f"  {self.n(e.seat):<6} {verb:<22} pot: {e.pot}")
        elif isinstance(e, ev.ShowdownEvent):
            print("\n--- SHOWDOWN ---")
            for seat, hole in e.hands:
                score = self.evaluator.score(hole, self.board)
                label = self.evaluator.category(score).label
                print(f"  {self.n(seat):<6} shows [{cards(hole)}]  ->  {label}")
        elif isinstance(e, ev.PotAwarded):
            who = " & ".join(self.n(s) for s in sorted(e.winners))
            kind = "Main pot" if e.pot_index == 0 else f"Side pot {e.pot_index}"
            print(f"\n  {kind} of {e.amount} -> {who}")
        elif isinstance(e, ev.HandEnded):
            print("\n=== Result ===")
            for seat, delta in e.net:
                print(f"  {self.n(seat):<6} {delta:+d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=7, help="random seed (same seed = same hand)")
    ap.add_argument("--players", type=int, default=3, choices=range(2, 7))
    ap.add_argument("--stack", type=int, default=1000)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    names = NAMES[: args.players]
    bus = ev.EventBus()
    Narrator(bus, names)

    engine = HandEngine(
        [(n, args.stack) for n in names],
        button=0,
        small_blind=10,
        big_blind=20,
        rng=rng,
        evaluator=TreysEvaluator(),
        bus=bus,
        hand_id=args.seed,
    )
    engine.start()

    print("\n  Hole cards (narrator only - each bot sees just its own):")
    for p in engine.state.players:
        print(f"    {p.name:<6} [{cards(p.hole)}]")
    print("\n--- PREFLOP ---")

    while not engine.is_over:
        seat = engine.state.to_act
        view = engine.view_for(seat)  # the ONLY thing a bot is given
        engine.apply(demo_bot(view.legal, view.pot, rng))

    r = engine.result()
    print("\n  Final stacks:", ", ".join(f"{names[s]} {v}" for s, v in r.final_stacks.items()))


if __name__ == "__main__":
    main()
