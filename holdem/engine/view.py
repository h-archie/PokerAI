"""PlayerView: the imperfect-information boundary.

Agents only ever receive a PlayerView. It contains the viewer's own hole cards
and public information, never opponents' cards or the deck.
"""

from __future__ import annotations

from dataclasses import dataclass

from holdem.core.cards import Card
from holdem.engine.rules import LegalActions, legal_actions
from holdem.engine.state import GameState, HistoryEntry, Street


@dataclass(frozen=True)
class PlayerView:
    hand_id: int
    seat: int
    hole: tuple[Card, Card] | None
    board: tuple[Card, ...]
    street: Street
    pot: int
    to_call: int
    legal: LegalActions | None  # None when it is not this seat's turn
    stacks: dict[int, int]
    committed_street: dict[int, int]
    active_seats: frozenset[int]  # seats not folded
    button: int
    small_blind: int
    big_blind: int
    history: tuple[HistoryEntry, ...]


def make_view(state: GameState, seat: int) -> PlayerView:
    me = state.players[seat]
    legal = legal_actions(state, seat) if state.to_act == seat else None
    return PlayerView(
        hand_id=state.hand_id,
        seat=seat,
        hole=me.hole,
        board=tuple(state.board),
        street=state.street,
        pot=state.pot,
        to_call=max(0, min(state.current_bet - me.committed_street, me.stack)),
        legal=legal,
        stacks={p.seat: p.stack for p in state.players},
        committed_street={p.seat: p.committed_street for p in state.players},
        active_seats=frozenset(p.seat for p in state.players if p.in_hand),
        button=state.button,
        small_blind=state.small_blind,
        big_blind=state.big_blind,
        history=tuple(state.history),
    )
