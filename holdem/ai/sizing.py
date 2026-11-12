"""Convert a policy Intent into a concrete, always-legal Action."""

from __future__ import annotations

from holdem.ai.policy import Intent
from holdem.engine.actions import Action
from holdem.engine.view import PlayerView

POT_FRACTION = {
    Intent.BET_SMALL: 0.33,
    Intent.BET_MEDIUM: 0.66,
    Intent.BET_LARGE: 1.0,
}

# If a bet would commit at least this share of our stack, just go all-in.
SHOVE_THRESHOLD = 0.8


def passive(view: PlayerView) -> Action:
    """Check if free, otherwise call."""
    assert view.legal is not None
    return Action.check() if view.legal.can_check else Action.call()


def raise_to_fraction(view: PlayerView, fraction: float, shove_threshold: float | None = None) -> int:
    """Street total for a raise of ``fraction`` x the pot (after calling),
    clamped to the legal range."""
    legal = view.legal
    assert legal is not None and legal.min_raise_to is not None and legal.max_raise_to is not None
    current_bet = view.committed_street[view.seat] + legal.call_amount
    pot_after_call = view.pot + legal.call_amount
    target = current_bet + round(fraction * pot_after_call)
    target = max(legal.min_raise_to, min(target, legal.max_raise_to))
    if shove_threshold is not None and target >= shove_threshold * legal.max_raise_to:
        target = legal.max_raise_to
    return target


def bet_amount(intent: Intent, view: PlayerView) -> int:
    """Street total to raise to: current bet + fraction of the pot after calling."""
    return raise_to_fraction(view, POT_FRACTION[intent], SHOVE_THRESHOLD)


def to_action(intent: Intent, view: PlayerView) -> Action:
    legal = view.legal
    if legal is None:
        raise ValueError("to_action() called when it is not this player's turn")

    if intent is Intent.FOLD:
        return Action.check() if legal.can_check else Action.fold()  # never fold for free
    if intent is Intent.CHECK:
        return Action.check() if legal.can_check else Action.fold()
    if intent is Intent.CALL:
        return passive(view)
    if not legal.can_raise:
        return passive(view)  # wanted to bet/raise but the rules don't allow it
    if intent is Intent.ALL_IN:
        return Action.all_in()
    return Action.raise_to(bet_amount(intent, view))
