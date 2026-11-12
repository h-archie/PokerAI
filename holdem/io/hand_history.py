"""Hand histories: record every hand's public events as one JSON line.

Files are JSON Lines (one hand per line), so they can be appended to while a
game runs and read back hand by hand. Replaying a hand simply feeds the saved
events back through a Narrator.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Iterator

from holdem.core.cards import Card
from holdem.engine.actions import Action, ActionType
from holdem.io import events as ev

EVENT_TYPES: dict[str, type[ev.Event]] = {
    cls.__name__: cls
    for cls in (
        ev.HandStarted,
        ev.BlindPosted,
        ev.ActionTaken,
        ev.StreetAdvanced,
        ev.ShowdownEvent,
        ev.PotAwarded,
        ev.HandEnded,
    )
}


# --------------------------------------------------------------- encoding


def _encode(value: Any) -> Any:
    if isinstance(value, Card):
        return {"card": str(value)}
    if isinstance(value, Action):
        return {"action": value.type.value, "amount": value.amount}
    if isinstance(value, frozenset):
        return {"set": sorted(_encode(v) for v in value)}
    if isinstance(value, (tuple, list)):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if "card" in value:
            return Card.parse(value["card"])
        if "action" in value:
            return Action(ActionType(value["action"]), value["amount"])
        if "set" in value:
            return frozenset(_decode(v) for v in value["set"])
    if isinstance(value, list):
        return tuple(_decode(v) for v in value)
    return value


def encode_event(e: ev.Event) -> dict[str, Any]:
    fields = {f.name: _encode(getattr(e, f.name)) for f in dataclasses.fields(e)}
    return {"type": type(e).__name__, **fields}


def decode_event(data: dict[str, Any]) -> ev.Event:
    data = dict(data)
    cls = EVENT_TYPES[data.pop("type")]
    return cls(**{k: _decode(v) for k, v in data.items()})


# ---------------------------------------------------------------- writing


class HandHistoryWriter:
    """Subscribe to a bus; append one JSON line per finished hand."""

    def __init__(self, bus: ev.EventBus, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[ev.Event] = []
        self.hands_written = 0
        bus.subscribe(self.on_event)

    def on_event(self, e: ev.Event) -> None:
        if isinstance(e, ev.HandStarted):
            self._events = []
        self._events.append(e)
        if isinstance(e, ev.HandEnded):
            self._write()

    def _write(self) -> None:
        start = self._events[0]
        assert isinstance(start, ev.HandStarted)
        names = {seat: name for seat, name, _ in start.seats}
        end = self._events[-1]
        assert isinstance(end, ev.HandEnded)
        boards = [e.board for e in self._events if isinstance(e, ev.StreetAdvanced)]
        record = {
            "hand_id": start.hand_id,
            "players": [names[s] for s in sorted(names)],
            "board": " ".join(map(str, boards[-1])) if boards else "",
            "net": {names[seat]: delta for seat, delta in end.net},
            "events": [encode_event(e) for e in self._events],
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self.hands_written += 1


# ---------------------------------------------------------------- reading


def load_hands(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def hand_events(record: dict[str, Any]) -> list[ev.Event]:
    return [decode_event(e) for e in record["events"]]
