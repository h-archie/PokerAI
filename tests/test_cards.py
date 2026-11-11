import random

import pytest

from holdem.core.cards import FULL_DECK, Card, Deck, Rank, Suit, parse_cards


def test_parse_and_str_roundtrip():
    for c in FULL_DECK:
        assert Card.parse(str(c)) == c
    assert Card.parse("Ah") == Card(Rank.ACE, Suit.HEARTS)
    assert str(Card(Rank.TEN, Suit.DIAMONDS)) == "Td"


@pytest.mark.parametrize("bad", ["", "A", "1h", "Ax", "Ahh"])
def test_parse_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        Card.parse(bad)


def test_parse_cards_formats():
    assert parse_cards("Ah Kd") == parse_cards("AhKd") == (Card.parse("Ah"), Card.parse("Kd"))


def test_full_deck_is_52_unique():
    assert len(FULL_DECK) == 52 == len(set(FULL_DECK))


def test_deck_is_deterministic_for_a_seed():
    d1, d2 = Deck(random.Random(7)), Deck(random.Random(7))
    assert d1.deal(52) == d2.deal(52)
    assert Deck(random.Random(7)).deal(5) != Deck(random.Random(8)).deal(5)


def test_deck_exclude_and_deal():
    excluded = parse_cards("AhAs")
    d = Deck(random.Random(1), exclude=excluded)
    assert len(d) == 50
    dealt = d.deal(50)
    assert not set(excluded) & set(dealt)
    with pytest.raises(ValueError):
        d.deal(1)


def test_stacked_deck_order():
    top = parse_cards("2c3d4h")
    d = Deck.stacked(top)
    assert d.deal(3) == top
    assert len(d) == 49
    with pytest.raises(ValueError):
        Deck.stacked(parse_cards("2c2c"))
