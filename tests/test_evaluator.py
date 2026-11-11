import random
from itertools import combinations

import pytest

from holdem.core.cards import FULL_DECK, parse_cards
from holdem.core.evaluator import HandCategory, NaiveEvaluator, TreysEvaluator

EVALUATORS = [TreysEvaluator(), NaiveEvaluator()]

CATEGORY_CASES = [
    ("AhKh", "QhJhTh2c3d", HandCategory.STRAIGHT_FLUSH),
    ("5s4s", "3s2sAs9d9c", HandCategory.STRAIGHT_FLUSH),  # steel wheel
    ("9h9d", "9s9c2h3d4c", HandCategory.FOUR_OF_A_KIND),
    ("KhKd", "Ks2c2d7h8s", HandCategory.FULL_HOUSE),
    ("Ah2h", "9h7h4hKsQd", HandCategory.FLUSH),
    ("Ac2d", "3h4s5c9dKh", HandCategory.STRAIGHT),  # wheel
    ("7c7d", "7h2s4cJdKh", HandCategory.THREE_OF_A_KIND),
    ("AcAd", "KhKs4c8d2h", HandCategory.TWO_PAIR),
    ("AcAd", "Kh7s4c8d2h", HandCategory.PAIR),
    ("Ac9d", "Kh7s4c8d2h", HandCategory.HIGH_CARD),
]


@pytest.mark.parametrize("ev", EVALUATORS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("hole,board,expected", CATEGORY_CASES)
def test_categories(ev, hole, board, expected):
    assert ev.category(ev.score(parse_cards(hole), parse_cards(board))) is expected


@pytest.mark.parametrize("ev", EVALUATORS, ids=lambda e: type(e).__name__)
def test_known_orderings(ev):
    board = parse_cards("Kc8d2h5s9c")

    def s(h):
        return ev.score(parse_cards(h), board)

    assert s("KdKh") < s("AcAd")  # set beats overpair
    assert s("AcAd") < s("AhKd")  # overpair beats top pair
    assert s("AhKd") < s("QhKd")  # kicker
    assert s("AhKd") == s("AsKh")  # split


@pytest.mark.parametrize("ev", EVALUATORS, ids=lambda e: type(e).__name__)
def test_rejects_wrong_card_counts(ev):
    with pytest.raises(ValueError):
        ev.score(parse_cards("AhKh"), parse_cards("2c3d"))


def test_treys_matches_naive_oracle_on_random_hands():
    """Cross-check: both evaluators must order random 7-card hand pairs identically."""
    rng = random.Random(1234)
    treys, naive = TreysEvaluator(), NaiveEvaluator()
    for _ in range(1500):
        cards = rng.sample(FULL_DECK, 9)
        board, h1, h2 = cards[:5], cards[5:7], cards[7:9]
        t1, t2 = treys.score(h1, board), treys.score(h2, board)
        n1, n2 = naive.score(h1, board), naive.score(h2, board)
        assert (t1 > t2) - (t1 < t2) == (n1 > n2) - (n1 < n2), (h1, h2, board)
        assert treys.category(t1) is naive.category(n1)


def test_treys_category_counts_over_all_five_card_hands_sample():
    # Spot check: 5-card evaluation agrees with the oracle on a fixed sample.
    treys, naive = TreysEvaluator(), NaiveEvaluator()
    for i, combo in enumerate(combinations(FULL_DECK[:20], 5)):
        if i > 2000:
            break
        hole, board = combo[:2], combo[2:]
        assert treys.category(treys.score(hole, board)) is naive.category(naive.score(hole, board))
