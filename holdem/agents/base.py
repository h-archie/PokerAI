"""The Agent interface every player implements."""

from __future__ import annotations

from holdem.engine.actions import Action
from holdem.engine.view import PlayerView
from holdem.io.events import Event


class StopGame(Exception):
    """Raised by an agent (e.g. a human typing "quit") to end the session.
    Unlike other agent errors, the table lets it propagate."""


class Agent:
    """Base class for players.

    Subclasses must implement ``act``. ``on_event`` receives every public
    event (useful for opponent modelling); ``reset`` is called between matches.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or type(self).__name__

    def act(self, view: PlayerView) -> Action:
        raise NotImplementedError

    def on_event(self, event: Event) -> None:
        pass

    def reset(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"
