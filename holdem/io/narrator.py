"""Turn the public event stream into readable text.

Used by demo.py, the interactive game and hand-history replays. Because it
only sees public events, it never reveals hole cards before a showdown.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable

from holdem.core.cards import Card
from holdem.core.evaluator import HandEvaluator, TreysEvaluator
from holdem.engine.actions import ActionType
from holdem.engine.state import Street
from holdem.io import events as ev

SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


def fmt_card(card: Card, pretty: bool = False) -> str:
    text = str(card)
    if pretty:
        return text[0].replace("T", "10") + SUIT_SYMBOLS[text[1]]
    return text


def fmt_cards(cards: Iterable[Card], pretty: bool = False) -> str:
    return " ".join(fmt_card(c, pretty) for c in cards)


def describe_action(e: ev.ActionTaken) -> str:
    a = e.action
    return {
        ActionType.FOLD: "folds",
        ActionType.CHECK: "checks",
        ActionType.CALL: f"calls (to {a.amount})",
        ActionType.BET: f"bets {a.amount}",
        ActionType.RAISE: f"raises to {a.amount}",
        ActionType.ALL_IN: f"goes ALL-IN ({a.amount})",
    }[a.type]


class Narrator:
    def __init__(
        self,
        bus: ev.EventBus | None = None,
        out: Callable[[str], None] = print,
        pretty: bool = False,
        you: int | None = None,
        delay: float = 0.0,
        evaluator: HandEvaluator | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """``you``: seat of a human player, highlighted and never delayed.
        ``delay``: pause (seconds) after each bot action so a human can follow."""
        self.out = out
        self.pretty = pretty
        self.you = you
        self.delay = delay
        self.sleep = sleep
        self.evaluator = evaluator or TreysEvaluator()
        self.names: dict[int, str] = {}
        self.width = 6
        self.board: tuple[Card, ...] = ()
        if bus is not None:
            bus.subscribe(self.on_event)

    def n(self, seat: int) -> str:
        return self.names.get(seat, f"Seat {seat}")

    def cards(self, cs: Iterable[Card]) -> str:
        return fmt_cards(cs, self.pretty)

    def on_event(self, e: ev.Event) -> None:
        out, w = self.out, self.width
        if isinstance(e, ev.HandStarted):
            self.names = {seat: name for seat, name, _ in e.seats}
            self.width = w = max(len(n) for n in self.names.values())
            self.board = ()
            out(f"\n=== Hand #{e.hand_id}  |  blinds {e.small_blind}/{e.big_blind} ===")
            for seat, name, stack in e.seats:
                tag = "  (dealer button)" if seat == e.button else ""
                out(f"  {name:<{w}} {stack:>6} chips{tag}")
            out("")
        elif isinstance(e, ev.BlindPosted):
            out(f"  {self.n(e.seat):<{w}} posts blind {e.amount}")
        elif isinstance(e, ev.StreetAdvanced):
            self.board = e.board
            out(f"\n--- {Street(e.street).name}: [ {self.cards(e.board)} ] ---")
        elif isinstance(e, ev.ActionTaken):
            out(f"  {self.n(e.seat):<{w}} {describe_action(e):<22} pot: {e.pot}")
            if self.delay and e.seat != self.you:
                self.sleep(self.delay)
        elif isinstance(e, ev.ShowdownEvent):
            out("\n--- SHOWDOWN ---")
            for seat, hole in e.hands:
                label = ""
                if len(self.board) == 5:
                    score = self.evaluator.score(hole, self.board)
                    label = f"  ->  {self.evaluator.category(score).label}"
                out(f"  {self.n(seat):<{w}} shows [ {self.cards(hole)} ]{label}")
        elif isinstance(e, ev.PotAwarded):
            who = " & ".join(self.n(s) for s in sorted(e.winners))
            kind = "Main pot" if e.pot_index == 0 else f"Side pot {e.pot_index}"
            out(f"\n  {kind} of {e.amount} -> {who}")
        elif isinstance(e, ev.HandEnded):
            parts = [f"{self.n(s)} {d:+d}" for s, d in e.net if d]
            out("  Result: " + (", ".join(parts) if parts else "no change"))
