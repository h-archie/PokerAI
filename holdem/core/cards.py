"""Card, Rank, Suit and Deck.

All randomness comes from an injected ``random.Random`` so every deal is
reproducible from a seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Iterable, Sequence

_RANK_CHARS = "23456789TJQKA"


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def symbol(self) -> str:
        return _RANK_CHARS[self - 2]

    @classmethod
    def from_symbol(cls, ch: str) -> "Rank":
        idx = _RANK_CHARS.find(ch.upper())
        if idx < 0:
            raise ValueError(f"invalid rank {ch!r}")
        return cls(idx + 2)


class Suit(Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    @classmethod
    def parse(cls, text: str) -> "Card":
        """Parse a two-character card such as ``"Ah"`` or ``"Td"``."""
        if len(text) != 2:
            raise ValueError(f"invalid card {text!r}")
        try:
            suit = Suit(text[1].lower())
        except ValueError:
            raise ValueError(f"invalid suit in {text!r}") from None
        return cls(Rank.from_symbol(text[0]), suit)

    def __str__(self) -> str:
        return f"{self.rank.symbol}{self.suit.value}"

    def __repr__(self) -> str:
        return f"Card({str(self)!r})"


def parse_cards(text: str) -> tuple[Card, ...]:
    """Parse ``"Ah Kd"`` or ``"AhKd"`` into a tuple of cards."""
    compact = text.replace(" ", "").replace(",", "")
    if len(compact) % 2:
        raise ValueError(f"invalid card list {text!r}")
    return tuple(Card.parse(compact[i : i + 2]) for i in range(0, len(compact), 2))


FULL_DECK: tuple[Card, ...] = tuple(Card(r, s) for s in Suit for r in Rank)


class Deck:
    """A shuffled deck. Cards are dealt from the top (index 0)."""

    def __init__(self, rng: random.Random, exclude: Iterable[Card] = ()) -> None:
        excluded = set(exclude)
        self._cards: list[Card] = [c for c in FULL_DECK if c not in excluded]
        rng.shuffle(self._cards)

    @classmethod
    def stacked(cls, top: Sequence[Card]) -> "Deck":
        """Deterministic deck for tests: ``top`` first, then the rest unshuffled."""
        if len(set(top)) != len(top):
            raise ValueError("duplicate cards in stacked deck")
        deck = cls.__new__(cls)
        chosen = set(top)
        deck._cards = list(top) + [c for c in FULL_DECK if c not in chosen]
        return deck

    def deal(self, n: int) -> tuple[Card, ...]:
        if n < 0 or n > len(self._cards):
            raise ValueError(f"cannot deal {n} cards from {len(self._cards)}")
        out = tuple(self._cards[:n])
        del self._cards[:n]
        return out

    def __len__(self) -> int:
        return len(self._cards)
