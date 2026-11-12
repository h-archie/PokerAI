import random

from holdem.ai.policy import Intent, PolicyParams, decide
from holdem.ai.sizing import bet_amount, to_action
from holdem.engine.actions import Action, ActionType

from tests.helpers import play_script, stacked_engine

RNG = random.Random(0)
NO_BLUFF = PolicyParams(bluff_freq=0.0)
LOW_BOARD = "2c7d9c3d8s"


def heads_up_flop_view(facing_bet: int | None = None):
    """Heads-up, flop dealt, pot 200. Seat 1 acts first; optionally seat 1 bets
    and we look at seat 0's view."""
    eng = stacked_engine([10_000, 10_000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.check())])
    if facing_bet is None:
        return eng.view_for(1)
    eng.apply(Action.bet(facing_bet))
    return eng.view_for(0)


def test_strong_hand_bets_big():
    d = decide(heads_up_flop_view(), equity=0.90, n_opponents=1, params=NO_BLUFF, rng=RNG)
    assert d.intent is Intent.BET_LARGE


def test_value_hand_bets_medium_when_checked_to():
    d = decide(heads_up_flop_view(), equity=0.70, n_opponents=1, params=NO_BLUFF, rng=RNG)
    assert d.intent is Intent.BET_MEDIUM


def test_weak_hand_checks_without_bluffing():
    d = decide(heads_up_flop_view(), equity=0.30, n_opponents=1, params=NO_BLUFF, rng=RNG)
    assert d.intent is Intent.CHECK


def test_always_bluff_when_bluff_freq_is_one():
    d = decide(heads_up_flop_view(), 0.30, 1, PolicyParams(bluff_freq=1.0), RNG)
    assert d.intent is Intent.BET_SMALL and "bluff" in d.reason


def test_folds_weak_hand_to_big_bet():
    view = heads_up_flop_view(facing_bet=1000)  # pot odds 1000/2200 = 45%
    d = decide(view, equity=0.30, n_opponents=1, params=NO_BLUFF, rng=RNG)
    assert d.intent is Intent.FOLD


def test_calls_with_good_pot_odds():
    view = heads_up_flop_view(facing_bet=100)  # pot odds 100/400 = 25%
    d = decide(view, equity=0.40, n_opponents=1, params=NO_BLUFF, rng=RNG)
    assert d.intent is Intent.CALL


def test_value_threshold_scales_with_number_of_opponents():
    view = heads_up_flop_view()
    # 50% equity is no edge heads-up, but a big edge 4-way (fair share 25%).
    assert decide(view, 0.50, 1, NO_BLUFF, RNG).intent is Intent.CHECK
    assert decide(view, 0.50, 3, NO_BLUFF, RNG).intent is not Intent.CHECK


def test_sizing_fractions_of_pot():
    view = heads_up_flop_view()  # pot 200, nothing to call
    assert bet_amount(Intent.BET_SMALL, view) == 100  # 0.33*200=66 -> min bet 100
    assert bet_amount(Intent.BET_MEDIUM, view) == 132
    assert bet_amount(Intent.BET_LARGE, view) == 200


def test_sizing_raise_includes_call():
    view = heads_up_flop_view(facing_bet=100)  # pot 300, 100 to call
    # to = current bet 100 + pot after call 400 * 1.0
    assert bet_amount(Intent.BET_LARGE, view) == 500


def test_sizing_shoves_when_bet_would_commit_most_of_stack():
    eng = stacked_engine([600, 600], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.raise_to(200)), (1, Action.call())])
    view = eng.view_for(1)  # pot 400, stacks 400 behind; pot bet = 400 = all-in
    assert bet_amount(Intent.BET_LARGE, view) == view.legal.max_raise_to


def test_to_action_never_folds_for_free_and_falls_back_when_cannot_raise():
    view = heads_up_flop_view()
    assert to_action(Intent.FOLD, view) == Action.check()
    # Short-stack all-in that cannot be re-raised: aggression becomes a call.
    eng = stacked_engine([10_000, 300], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    eng.apply(Action.raise_to(500))
    v = eng.view_for(1)
    assert not v.legal.can_raise
    assert to_action(Intent.BET_LARGE, v).type is ActionType.CALL
