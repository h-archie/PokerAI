import random

import pytest

from holdem.ai.equity import estimate_equity
from holdem.ai.preflop import all_hand_classes, hand_class, preflop_equity, representative
from holdem.core.cards import parse_cards

from tests.helpers import EVALUATOR


def eq(hole, board="", n=1, iters=3000, seed=0):
    return estimate_equity(
        parse_cards(hole), parse_cards(board), n, random.Random(seed), EVALUATOR, iters
    )


def test_aces_vs_one_random_hand_is_about_85_percent():
    assert eq("AhAs").equity == pytest.approx(0.85, abs=0.03)


def test_seven_deuce_vs_one_random_hand_is_about_35_percent():
    assert eq("7h2c").equity == pytest.approx(0.35, abs=0.03)


def test_more_opponents_means_less_equity():
    assert eq("AhAs", n=1).equity > eq("AhAs", n=3).equity > eq("AhAs", n=5).equity


def test_nuts_on_river_is_100_percent():
    r = eq("AhKh", board="QhJhTh2c3d", iters=200)
    assert r.equity == 1.0 and r.win == 1.0


def test_board_plays_for_everyone_is_a_tie():
    # Royal flush on board: every hand splits.
    r = eq("2c3d", board="AsKsQsJsTs", iters=200)
    assert r.tie == 1.0 and r.equity == pytest.approx(0.5)


def test_same_seed_same_result():
    assert eq("KdQd", "2c7h9s", iters=500, seed=3) == eq("KdQd", "2c7h9s", iters=500, seed=3)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        eq("AhAh")
    with pytest.raises(ValueError):
        eq("AhKh", n=0)


def test_hand_class_names():
    assert hand_class(parse_cards("AhKh")) == "AKs"
    assert hand_class(parse_cards("KhAd")) == "AKo"
    assert hand_class(parse_cards("7c7d")) == "77"
    classes = all_hand_classes()
    assert len(classes) == 169 == len(set(classes))
    for c in classes:
        assert hand_class(representative(c)) == c


def test_preflop_table_matches_known_values():
    assert preflop_equity(parse_cards("AhAs"), 1) == pytest.approx(0.852, abs=0.015)
    assert preflop_equity(parse_cards("KhKs"), 1) == pytest.approx(0.824, abs=0.015)
    assert preflop_equity(parse_cards("AhKh"), 1) == pytest.approx(0.670, abs=0.015)
    assert preflop_equity(parse_cards("7h2c"), 1) == pytest.approx(0.346, abs=0.015)
    # Clamped to 1..5 opponents.
    assert preflop_equity(parse_cards("AhAs"), 9) == preflop_equity(parse_cards("AhAs"), 5)


def test_preflop_ordering():
    def e(h):
        return preflop_equity(parse_cards(h), 1)

    assert e("AhAs") > e("KhKs") > e("AhKh") > e("AhKd") > e("7h2c")
    assert e("AhKh") > e("AhKd")  # suited beats offsuit
