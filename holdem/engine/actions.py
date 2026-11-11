"""The action vocabulary.

Amount convention: ``amount`` is always the player's **total chips committed
on the current street** after the action ("raise *to* X", not "raise *by* X").
For FOLD and CHECK it is 0. Agents may leave it as 0 for CALL and ALL_IN; the
engine fills in the real value when it records the action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass(frozen=True, slots=True)
class Action:
    type: ActionType
    amount: int = 0

    @classmethod
    def fold(cls) -> "Action":
        return cls(ActionType.FOLD)

    @classmethod
    def check(cls) -> "Action":
        return cls(ActionType.CHECK)

    @classmethod
    def call(cls) -> "Action":
        return cls(ActionType.CALL)

    @classmethod
    def bet(cls, to: int) -> "Action":
        return cls(ActionType.BET, to)

    @classmethod
    def raise_to(cls, to: int) -> "Action":
        return cls(ActionType.RAISE, to)

    @classmethod
    def all_in(cls) -> "Action":
        return cls(ActionType.ALL_IN)

    def __str__(self) -> str:
        if self.type in (ActionType.FOLD, ActionType.CHECK):
            return self.type.value
        return f"{self.type.value} {self.amount}"
