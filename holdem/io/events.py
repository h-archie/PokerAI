"""Typed public events and a tiny synchronous event bus.

Only *public* information is published. Private hole cards reach a player
solely through their PlayerView; they appear here only at showdown.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from holdem.core.cards import Card
from holdem.engine.actions import Action


@dataclass(frozen=True, slots=True)
class Event:
    hand_id: int


@dataclass(frozen=True, slots=True)
class HandStarted(Event):
    button: int
    seats: tuple[tuple[int, str, int], ...]  # (seat, name, starting stack)
    small_blind: int
    big_blind: int


@dataclass(frozen=True, slots=True)
class BlindPosted(Event):
    seat: int
    amount: int


@dataclass(frozen=True, slots=True)
class ActionTaken(Event):
    street: int
    seat: int
    action: Action
    pot: int  # pot after the action


@dataclass(frozen=True, slots=True)
class StreetAdvanced(Event):
    street: int
    board: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class ShowdownEvent(Event):
    hands: tuple[tuple[int, tuple[Card, ...]], ...]  # (seat, hole cards)


@dataclass(frozen=True, slots=True)
class PotAwarded(Event):
    pot_index: int
    amount: int
    winners: frozenset[int]


@dataclass(frozen=True, slots=True)
class HandEnded(Event):
    net: tuple[tuple[int, int], ...]  # (seat, chip delta)


Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event] | None, list[Handler]] = defaultdict(list)

    def subscribe(self, handler: Handler, event_type: type[Event] | None = None) -> None:
        """Subscribe to one event type, or to all events if ``event_type`` is None."""
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for h in self._handlers.get(type(event), ()):
            h(event)
        for h in self._handlers.get(None, ()):
            h(event)


class EventRecorder:
    """Convenience subscriber that stores every event (handy in tests)."""

    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.subscribe(self.events.append)

    def of_type(self, event_type: type[Event]) -> list[Event]:
        return [e for e in self.events if isinstance(e, event_type)]
