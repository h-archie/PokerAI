"""Legal-action computation. Pure functions over GameState."""

from __future__ import annotations

from dataclasses import dataclass

from holdem.engine.state import GameState


class IllegalAction(ValueError):
    """Raised when an agent submits an action the rules do not allow."""


@dataclass(frozen=True, slots=True)
class LegalActions:
    can_check: bool
    # Chips the player must add to call (capped at their stack). 0 if they can check.
    call_amount: int
    # Bounds for BET/RAISE, as street totals ("raise to"). None if raising is not allowed.
    min_raise_to: int | None
    max_raise_to: int | None

    @property
    def can_raise(self) -> bool:
        return self.min_raise_to is not None


def legal_actions(state: GameState, seat: int) -> LegalActions:
    p = state.players[seat]
    if not p.can_act:
        raise IllegalAction(f"seat {seat} cannot act")

    to_call = max(0, state.current_bet - p.committed_street)
    call_amount = min(to_call, p.stack)
    max_to = p.committed_street + p.stack

    # Raising needs chips beyond a call, and the action must be open to this
    # player (i.e. they have not acted since the last full raise), and there
    # must be at least one other player who could still respond.
    others_can_act = any(o.can_act for o in state.players if o.seat != seat)
    can_raise = (
        max_to > state.current_bet
        and seat not in state.raise_closed
        and others_can_act
    )
    if can_raise:
        min_to = min(state.current_bet + state.min_raise, max_to)  # short all-in allowed
        return LegalActions(to_call == 0, call_amount, min_to, max_to)
    return LegalActions(to_call == 0, call_amount, None, None)
