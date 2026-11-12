"""Decision logic: turn hand strength + pot odds into an intent.

The policy is a pure function. It knows nothing about chip amounts beyond what
it needs for pot odds; ``sizing`` converts its intent into a legal action.

Core idea:
- *Edge* = equity minus a fair share of the pot (1 / number of players in the
  hand). Big edge -> bet/raise for value. This scales thresholds for multiway
  pots automatically.
- Facing a bet, call only when equity beats the pot odds by a margin.
- Occasionally bluff when checked to, but only against one or two opponents.
- With an opponent read (``fold_to_bet``), bluff more against players who
  fold a lot, never bluff calling stations, and value-bet thinner against them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from holdem.engine.actions import ActionType
from holdem.engine.view import PlayerView


class Intent(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET_SMALL = "bet_small"  # ~1/3 pot
    BET_MEDIUM = "bet_medium"  # ~2/3 pot
    BET_LARGE = "bet_large"  # ~pot
    ALL_IN = "all_in"


@dataclass(frozen=True, slots=True)
class PolicyParams:
    value_edge: float = 0.15  # edge needed to bet/raise for value
    strong_edge: float = 0.30  # edge needed to bet big / re-raise
    shove_edge: float = 0.45  # edge needed to go all-in in a raising war
    call_margin: float = 0.03  # equity must beat pot odds by this much to call
    bluff_freq: float = 0.08  # chance of a small bluff when checked to
    max_raises: int = 3  # after this many raises on a street, stop re-raising
    thin_value: float = 0.07  # how much lower the value bar goes vs players who never fold


FOLD_TO_BET_BASELINE = 0.45  # typical fold-to-bet rate (the opponent model's prior)


@dataclass(frozen=True, slots=True)
class Decision:
    intent: Intent
    reason: str


def raises_this_street(view: PlayerView) -> int:
    aggressive = (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
    return sum(
        1 for h in view.history if h.street == view.street and h.action.type in aggressive
    )


def pot_odds(view: PlayerView) -> float:
    assert view.legal is not None
    to_call = view.legal.call_amount
    return to_call / (view.pot + to_call) if to_call else 0.0


def decide(
    view: PlayerView,
    equity: float,
    n_opponents: int,
    params: PolicyParams,
    rng: random.Random,
    fold_to_bet: float | None = None,
) -> Decision:
    """``fold_to_bet``: how often the opponents in this hand fold to a bet
    (from the opponent model), or None to play without a read."""
    legal = view.legal
    if legal is None:
        raise ValueError("decide() called when it is not this player's turn")

    bluff_freq, value_edge = params.bluff_freq, params.value_edge
    if fold_to_bet is not None:
        ratio = fold_to_bet / FOLD_TO_BET_BASELINE  # 1.0 = an average opponent
        bluff_freq *= min(max(ratio, 0.0), 2.5) ** 2  # stations ~0, folders up to ~6x
        value_edge -= params.thin_value * max(0.0, 1.0 - ratio)

    fair = 1.0 / (n_opponents + 1)
    edge = equity - fair
    odds = pot_odds(view)
    raises = raises_this_street(view)
    facing_bet = not legal.can_check
    can_raise = legal.can_raise
    tag = f"equity {equity:.0%} vs fair {fair:.0%}"

    # 1. Very strong: build the pot.
    if edge >= params.strong_edge and can_raise:
        if raises < params.max_raises:
            return Decision(Intent.BET_LARGE, f"strong hand ({tag}): bet big")
        if edge >= params.shove_edge:
            return Decision(Intent.ALL_IN, f"monster in a raising war ({tag}): all-in")
        return Decision(Intent.CALL, f"strong but raising capped ({tag}): call")

    # 2. Good: bet when checked to, raise a single bet, otherwise just call.
    if edge >= value_edge:
        if not facing_bet and can_raise:
            return Decision(Intent.BET_MEDIUM, f"value hand ({tag}): bet")
        if facing_bet and raises <= 1 and can_raise:
            return Decision(Intent.BET_MEDIUM, f"value hand facing one bet ({tag}): raise")
        if facing_bet:
            return Decision(Intent.CALL, f"value hand ({tag}): call")
        return Decision(Intent.CHECK, f"value hand but cannot bet ({tag}): check")

    # 3. Facing a bet with a marginal/weak hand: pot odds decide.
    if facing_bet:
        if equity >= odds + params.call_margin:
            return Decision(Intent.CALL, f"{tag}, pot odds {odds:.0%}: call")
        return Decision(Intent.FOLD, f"{tag}, pot odds {odds:.0%}: fold")

    # 4. Checked to with a weak hand: sometimes bluff small, otherwise check.
    if can_raise and n_opponents <= 2 and rng.random() < bluff_freq:
        return Decision(Intent.BET_SMALL, f"weak hand ({tag}): bluff")
    return Decision(Intent.CHECK, f"weak hand ({tag}): check")
