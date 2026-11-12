"""Opponent model: learns each player's tendencies from public events only.

Tracked per player name (names stay fixed while seats/buttons move):

- VPIP: how often they voluntarily put chips in preflop (loose vs tight)
- PFR: how often they raise preflop
- aggression: share of their bets/raises among bets, raises and calls
- fold_to_bet: how often they fold when facing a bet or raise (blinds don't count)

Every stat is smoothed toward a population prior, so a handful of hands
cannot swing it wildly: stat = (observed + prior * weight) / (opportunities + weight).
"""

from __future__ import annotations

from dataclasses import dataclass

from holdem.engine.actions import ActionType
from holdem.io import events as ev

PRIORS = {"vpip": 0.30, "pfr": 0.15, "aggression": 0.40, "fold_to_bet": 0.45}


@dataclass
class _Counts:
    hands: int = 0
    vpip: int = 0
    pfr: int = 0
    aggressive: int = 0
    calls: int = 0
    faced_bet: int = 0
    folded_to_bet: int = 0


@dataclass(frozen=True, slots=True)
class OpponentStats:
    name: str
    hands: int
    vpip: float
    pfr: float
    aggression: float
    fold_to_bet: float

    @property
    def style(self) -> str:
        """Human-readable label, e.g. "loose-passive" (a calling station)."""
        loose = "loose" if self.vpip > 0.35 else "tight"
        aggressive = "aggressive" if self.aggression > 0.45 else "passive"
        return f"{loose}-{aggressive}"


class OpponentModel:
    def __init__(self, prior_weight: float = 20.0) -> None:
        self.prior_weight = prior_weight
        self._counts: dict[str, _Counts] = {}
        self._seat_names: dict[int, str] = {}
        # Per-hand bookkeeping, reset on HandStarted.
        self._street = 0
        self._committed: dict[int, int] = {}
        self._current_bet = 0
        self._voluntary_bet = False  # has anyone bet/raised (not just blinds) this street?
        self._vpip_seats: set[int] = set()
        self._pfr_seats: set[int] = set()

    # ------------------------------------------------------------ queries

    def name_of(self, seat: int) -> str | None:
        return self._seat_names.get(seat)

    def stats(self, name: str) -> OpponentStats:
        c = self._counts.get(name, _Counts())
        w = self.prior_weight

        def smooth(hits: int, chances: int, key: str) -> float:
            if chances + w == 0:
                return PRIORS[key]
            return (hits + PRIORS[key] * w) / (chances + w)

        return OpponentStats(
            name=name,
            hands=c.hands,
            vpip=smooth(c.vpip, c.hands, "vpip"),
            pfr=smooth(c.pfr, c.hands, "pfr"),
            aggression=smooth(c.aggressive, c.aggressive + c.calls, "aggression"),
            fold_to_bet=smooth(c.folded_to_bet, c.faced_bet, "fold_to_bet"),
        )

    def stats_for_seat(self, seat: int) -> OpponentStats | None:
        name = self.name_of(seat)
        return self.stats(name) if name is not None else None

    # ------------------------------------------------------------- events

    def on_event(self, e: ev.Event) -> None:
        if isinstance(e, ev.HandStarted):
            self._seat_names = {seat: name for seat, name, _ in e.seats}
            for name in self._seat_names.values():
                self._counts.setdefault(name, _Counts())
            self._street = 0
            self._committed = {seat: 0 for seat in self._seat_names}
            self._current_bet = 0
            self._voluntary_bet = False
            self._vpip_seats = set()
            self._pfr_seats = set()
        elif isinstance(e, ev.BlindPosted):
            self._committed[e.seat] = self._committed.get(e.seat, 0) + e.amount
            self._current_bet = max(self._current_bet, self._committed[e.seat])
        elif isinstance(e, ev.StreetAdvanced):
            self._street = e.street
            self._committed = {seat: 0 for seat in self._committed}
            self._current_bet = 0
            self._voluntary_bet = False
        elif isinstance(e, ev.ActionTaken):
            self._on_action(e)
        elif isinstance(e, ev.HandEnded):
            for seat, name in self._seat_names.items():
                c = self._counts[name]
                c.hands += 1
                c.vpip += seat in self._vpip_seats
                c.pfr += seat in self._pfr_seats

    def _on_action(self, e: ev.ActionTaken) -> None:
        name = self._seat_names.get(e.seat)
        if name is None:
            return
        c = self._counts[name]
        a = e.action
        # Only real bets/raises count, not the blinds: otherwise every weak
        # preflop fold would look like "folding to aggression".
        facing = self._voluntary_bet and self._current_bet > self._committed.get(e.seat, 0)
        if facing:
            c.faced_bet += 1
            if a.type is ActionType.FOLD:
                c.folded_to_bet += 1

        if a.type in (ActionType.FOLD, ActionType.CHECK):
            return
        is_raise = a.amount > self._current_bet
        if is_raise:
            c.aggressive += 1
            self._voluntary_bet = True
        else:
            c.calls += 1
        if self._street == 0:
            self._vpip_seats.add(e.seat)
            if is_raise:
                self._pfr_seats.add(e.seat)
        self._committed[e.seat] = a.amount
        self._current_bet = max(self._current_bet, a.amount)
