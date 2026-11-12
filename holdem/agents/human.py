"""HumanAgent: a person playing from the terminal.

Input and output functions are injectable so the agent can be tested with
scripted input.
"""

from __future__ import annotations

from typing import Callable

from holdem.agents.base import Agent, StopGame
from holdem.ai.sizing import raise_to_fraction
from holdem.engine.actions import Action
from holdem.engine.state import Street
from holdem.engine.view import PlayerView
from holdem.io.events import Event, HandStarted
from holdem.io.narrator import fmt_cards

HELP = """\
  Commands:
    c  or  call / check   call the bet, or check if there is nothing to call
    f  or  fold           give up this hand
    r 300                 raise (or bet) TO 300 in total this round
    r min / r half / r pot / r max
                          raise the minimum, half the pot, the pot, or everything
    a  or  all-in         bet all your chips
    q  or  quit           leave the table
    ?                     show this help"""


def parse_command(text: str, view: PlayerView) -> Action | str:
    """Turn typed text into an Action, or return an error message to show."""
    legal = view.legal
    assert legal is not None
    words = text.strip().lower().split()
    if not words:
        return "Type a command (? for help)."
    cmd, rest = words[0], words[1:]

    if cmd in ("q", "quit", "exit"):
        raise StopGame
    if cmd in ("?", "h", "help"):
        return HELP
    if cmd in ("c", "call", "k", "check", "x"):
        return Action.check() if legal.can_check else Action.call()
    if cmd in ("f", "fold"):
        if legal.can_check:
            return "Nothing to call - you can check for free with 'c'. (Type 'f!' to fold anyway.)"
        return Action.fold()
    if cmd == "f!":
        return Action.fold()
    if cmd in ("a", "all-in", "allin", "all", "shove"):
        return Action.all_in()
    if cmd in ("r", "raise", "b", "bet"):
        if not legal.can_raise:
            return "You can't raise right now - only call or fold."
        assert legal.min_raise_to is not None and legal.max_raise_to is not None
        arg = rest[0] if rest else "min"
        presets = {"min": None, "half": 0.5, "pot": 1.0, "max": None}
        if arg == "min":
            return Action.raise_to(legal.min_raise_to)
        if arg == "max":
            return Action.all_in()
        if arg in presets:
            return Action.raise_to(raise_to_fraction(view, presets[arg]))  # type: ignore[arg-type]
        try:
            to = int(arg)
        except ValueError:
            return f"'{arg}' isn't a number. Example: r {legal.min_raise_to}"
        if to < legal.min_raise_to:
            if to >= legal.max_raise_to:
                return Action.all_in()
            return f"The minimum raise is to {legal.min_raise_to}."
        if to > legal.max_raise_to:
            return f"You only have enough to raise to {legal.max_raise_to} ('a' for all-in)."
        return Action.raise_to(to)
    return f"Unknown command '{cmd}'. Type ? for help."


class HumanAgent(Agent):
    def __init__(
        self,
        name: str = "You",
        input_fn: Callable[[str], str] = input,
        out: Callable[[str], None] = print,
        pretty: bool = True,
    ) -> None:
        super().__init__(name)
        self.input_fn = input_fn
        self.out = out
        self.pretty = pretty
        self.names: dict[int, str] = {}

    def on_event(self, event: Event) -> None:
        if isinstance(event, HandStarted):
            self.names = {seat: name for seat, name, _ in event.seats}

    def prompt(self, view: PlayerView) -> str:
        legal = view.legal
        assert legal is not None and view.hole is not None
        board = fmt_cards(view.board, self.pretty) if view.board else "(none yet)"
        others = "  ".join(
            f"{self.names.get(s, s)}: {view.stacks[s]}" + ("" if s in view.active_seats else " (folded)")
            for s in sorted(view.stacks)
            if s != view.seat
        )
        options = ["[c]heck" if legal.can_check else f"[c]all {legal.call_amount}"]
        if not legal.can_check:
            options.append("[f]old")
        if legal.can_raise:
            verb = "bet" if legal.can_check and view.street is not Street.PREFLOP else "raise to"
            options.append(f"[r]aise <amount> ({verb} {legal.min_raise_to}-{legal.max_raise_to})")
            options.append("[a]ll-in")
        options += ["[?] help", "[q]uit"]
        return "\n".join(
            [
                "",
                "  >>> YOUR TURN",
                f"      Your cards: [ {fmt_cards(view.hole, self.pretty)} ]    Board: [ {board} ]",
                f"      Pot: {view.pot}    To call: {legal.call_amount}    Your chips: {view.stacks[view.seat]}",
                f"      Others: {others}",
                "      " + "   ".join(options),
            ]
        )

    def act(self, view: PlayerView) -> Action:
        self.out(self.prompt(view))
        while True:
            try:
                text = self.input_fn("  > ")
            except EOFError:
                raise StopGame from None
            result = parse_command(text, view)
            if isinstance(result, Action):
                return result
            self.out(result)
