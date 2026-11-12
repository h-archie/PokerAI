"""Ground-truth state of a single hand. Only the engine mutates it."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from holdem.core.cards import Card, Deck
from holdem.engine.actions import Action


class Street(IntEnum):
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4


@dataclass
class PlayerState:
    seat: int
    name: str
    stack: int
    hole: tuple[Card, Card] | None = None
    committed_street: int = 0
    committed_total: int = 0
    folded: bool = False
    all_in: bool = False

    @property
    def in_hand(self) -> bool:
        return not self.folded

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    street: Street
    seat: int
    action: Action


@dataclass
class GameState:
    hand_id: int
    button: int
    small_blind: int
    big_blind: int
    players: list[PlayerState]
    deck: Deck
    street: Street = Street.PREFLOP
    board: list[Card] = field(default_factory=list)
    to_act: int | None = None
    current_bet: int = 0
    # Size of the last *full* bet or raise this street; the next raise must be
    # at least this much larger than current_bet.
    min_raise: int = 0
    history: list[HistoryEntry] = field(default_factory=list)
    # Seats that have acted voluntarily this street.
    acted: set[int] = field(default_factory=set)
    # Seats that have acted since the last full raise. They may call or fold
    # but not re-raise (handles incomplete all-in raises).
    raise_closed: set[int] = field(default_factory=set)

    @property
    def pot(self) -> int:
        return sum(p.committed_total for p in self.players)

    @property
    def num_seats(self) -> int:
        return len(self.players)

    def live_players(self) -> list[PlayerState]:
        return [p for p in self.players if p.in_hand]
