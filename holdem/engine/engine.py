"""HandEngine: the finite-state machine for one hand of No-Limit Hold'em.

The engine never calls agents. An outside driver (``sim.table`` on Day 2, or a
test) reads ``state.to_act``, gets a view with ``view_for``, and calls
``apply``. This keeps the engine testable with scripted action lists.

Simplifications (documented on purpose):
- Hole cards are dealt two at a time in seat order 0..n-1, then flop, turn
  and river. There are no burn cards. This makes stacked-deck tests readable
  and has no effect on a randomly shuffled deck.
- If the big blind is short-stacked, the amount to call preflop is the
  largest blind actually posted.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from holdem.core.cards import Card, Deck
from holdem.core.evaluator import HandEvaluator
from holdem.engine.actions import Action, ActionType
from holdem.engine.pot import Pot, award_pots, build_pots
from holdem.engine.rules import IllegalAction, LegalActions, legal_actions
from holdem.engine.state import GameState, HistoryEntry, PlayerState, Street
from holdem.engine.view import PlayerView, make_view
from holdem.io import events as ev


@dataclass(frozen=True)
class HandResult:
    hand_id: int
    board: tuple[Card, ...]
    pots: tuple[Pot, ...]
    winnings: dict[int, int]  # gross chips won, by seat
    net: dict[int, int]  # winnings minus chips committed, by seat
    final_stacks: dict[int, int]
    shown: dict[int, tuple[Card, Card]]  # hole cards revealed at showdown
    went_to_showdown: bool


class HandEngine:
    def __init__(
        self,
        players: Sequence[tuple[str, int]],
        button: int,
        small_blind: int,
        big_blind: int,
        rng: random.Random,
        evaluator: HandEvaluator,
        bus: ev.EventBus | None = None,
        hand_id: int = 0,
        deck: Deck | None = None,
    ) -> None:
        if len(players) < 2:
            raise ValueError("need at least 2 players")
        if any(stack <= 0 for _, stack in players):
            raise ValueError("every seated player needs a positive stack")
        if not 0 <= button < len(players):
            raise ValueError("button out of range")
        if not 0 < small_blind <= big_blind:
            raise ValueError("need 0 < small_blind <= big_blind")

        self._evaluator = evaluator
        self._bus = bus or ev.EventBus()
        self._starting = {i: stack for i, (_, stack) in enumerate(players)}
        self._result: HandResult | None = None
        self.state = GameState(
            hand_id=hand_id,
            button=button,
            small_blind=small_blind,
            big_blind=big_blind,
            players=[PlayerState(i, name, stack) for i, (name, stack) in enumerate(players)],
            deck=deck if deck is not None else Deck(rng),
            min_raise=big_blind,
        )

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        s = self.state
        if s.history or s.to_act is not None or self._result is not None:
            raise RuntimeError("hand already started")
        self._emit(
            ev.HandStarted(
                s.hand_id,
                s.button,
                tuple((p.seat, p.name, p.stack) for p in s.players),
                s.small_blind,
                s.big_blind,
            )
        )
        sb_seat, bb_seat = self._blind_seats()
        self._post_blind(sb_seat, s.small_blind)
        self._post_blind(bb_seat, s.big_blind)
        s.current_bet = max(p.committed_street for p in s.players)

        for p in s.players:
            a, b = s.deck.deal(2)
            p.hole = (a, b)

        n = s.num_seats
        first = s.button if n == 2 else (bb_seat + 1) % n
        self._continue_from(first)

    @property
    def is_over(self) -> bool:
        return self._result is not None

    def legal_actions(self) -> LegalActions:
        if self.state.to_act is None:
            raise IllegalAction("no player to act")
        return legal_actions(self.state, self.state.to_act)

    def view_for(self, seat: int) -> PlayerView:
        return make_view(self.state, seat)

    def result(self) -> HandResult:
        if self._result is None:
            raise RuntimeError("hand is not over")
        return self._result

    def apply(self, action: Action) -> None:
        s = self.state
        if s.to_act is None:
            raise IllegalAction("no player to act")
        seat = s.to_act
        p = s.players[seat]
        legal = legal_actions(s, seat)
        t = action.type

        if t is ActionType.FOLD:
            p.folded = True
            recorded = Action.fold()
            s.raise_closed.add(seat)
        elif t is ActionType.CHECK or (t is ActionType.CALL and legal.can_check):
            if not legal.can_check:
                raise IllegalAction(f"seat {seat} cannot check facing {legal.call_amount}")
            recorded = Action.check()
            s.raise_closed.add(seat)
        elif t is ActionType.CALL:
            self._commit(p, legal.call_amount)
            recorded = Action(ActionType.CALL, p.committed_street)
            s.raise_closed.add(seat)
        elif t in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            all_in_to = p.committed_street + p.stack
            to = all_in_to if t is ActionType.ALL_IN else action.amount
            if t is ActionType.ALL_IN and to <= s.current_bet:
                # All-in for no more than a call: it's just a call.
                self._commit(p, p.stack)
                recorded = Action(ActionType.ALL_IN, p.committed_street)
                s.raise_closed.add(seat)
            else:
                recorded = self._raise(p, to, legal)
        else:  # pragma: no cover - exhaustive enum
            raise IllegalAction(f"unknown action {action!r}")

        s.acted.add(seat)
        s.history.append(HistoryEntry(s.street, seat, recorded))
        self._emit(ev.ActionTaken(s.hand_id, int(s.street), seat, recorded, s.pot))

        if len(s.live_players()) == 1:
            self._finish(showdown=False)
            return
        self._continue_from((seat + 1) % s.num_seats)

    # ------------------------------------------------------------ internals

    def _emit(self, event: ev.Event) -> None:
        self._bus.publish(event)

    def _blind_seats(self) -> tuple[int, int]:
        n, b = self.state.num_seats, self.state.button
        if n == 2:
            return b, (b + 1) % n  # heads-up: button posts the small blind
        return (b + 1) % n, (b + 2) % n

    def _post_blind(self, seat: int, amount: int) -> None:
        p = self.state.players[seat]
        posted = min(amount, p.stack)
        self._commit(p, posted)
        self._emit(ev.BlindPosted(self.state.hand_id, seat, posted))

    @staticmethod
    def _commit(p: PlayerState, chips: int) -> None:
        if chips < 0 or chips > p.stack:
            raise IllegalAction(f"seat {p.seat} cannot commit {chips} with stack {p.stack}")
        p.stack -= chips
        p.committed_street += chips
        p.committed_total += chips
        if p.stack == 0:
            p.all_in = True

    def _raise(self, p: PlayerState, to: int, legal: LegalActions) -> Action:
        s = self.state
        if not legal.can_raise:
            raise IllegalAction(f"seat {p.seat} may not bet or raise now")
        assert legal.min_raise_to is not None and legal.max_raise_to is not None
        if to > legal.max_raise_to:
            raise IllegalAction(f"raise to {to} exceeds max {legal.max_raise_to}")
        if to < legal.min_raise_to:
            raise IllegalAction(f"raise to {to} below min {legal.min_raise_to}")

        kind = ActionType.BET if s.current_bet == 0 else ActionType.RAISE
        increment = to - s.current_bet
        self._commit(p, to - p.committed_street)
        if increment >= s.min_raise:
            # Full raise: reopens the action for everyone else.
            s.min_raise = increment
            s.raise_closed = {p.seat}
        else:
            # Incomplete all-in raise: does not reopen for players who already acted.
            s.raise_closed.add(p.seat)
        s.current_bet = to
        return Action(ActionType.ALL_IN if p.all_in else kind, to)

    def _needs_to_act(self, p: PlayerState) -> bool:
        s = self.state
        return p.can_act and (p.seat not in s.acted or p.committed_street < s.current_bet)

    def _continue_from(self, start: int) -> None:
        """Find the next seat to act from ``start``; otherwise close the street."""
        s = self.state
        can_act = [p for p in s.players if p.can_act]
        lone_player_matched = len(can_act) <= 1 and all(
            p.committed_street >= s.current_bet for p in can_act
        )
        if not lone_player_matched:
            n = s.num_seats
            for i in range(n):
                p = s.players[(start + i) % n]
                if self._needs_to_act(p):
                    s.to_act = p.seat
                    return
        s.to_act = None
        self._end_street()

    def _end_street(self) -> None:
        s = self.state
        if s.street is Street.RIVER:
            self._finish(showdown=True)
            return
        if sum(p.can_act for p in s.players) < 2:
            # Nobody left to bet: run out the board.
            while s.street < Street.RIVER:
                self._deal_next_street()
            self._finish(showdown=True)
            return
        self._deal_next_street()
        self._continue_from((s.button + 1) % s.num_seats)

    def _deal_next_street(self) -> None:
        s = self.state
        s.street = Street(s.street + 1)
        s.board.extend(s.deck.deal(3 if s.street is Street.FLOP else 1))
        for p in s.players:
            p.committed_street = 0
        s.current_bet = 0
        s.min_raise = s.big_blind
        s.acted = set()
        s.raise_closed = set()
        self._emit(ev.StreetAdvanced(s.hand_id, int(s.street), tuple(s.board)))

    def _finish(self, showdown: bool) -> None:
        s = self.state
        s.to_act = None
        live = s.live_players()
        contributions = {p.seat: p.committed_total for p in s.players}
        folded = {p.seat for p in s.players if p.folded}
        pots = build_pots(contributions, folded)

        scores: dict[int, int] = {}
        shown: dict[int, tuple[Card, Card]] = {}
        if showdown and len(live) > 1:
            s.street = Street.SHOWDOWN
            for p in live:
                assert p.hole is not None
                scores[p.seat] = self._evaluator.score(p.hole, s.board)
                shown[p.seat] = p.hole
            self._emit(ev.ShowdownEvent(s.hand_id, tuple(shown.items())))

        winnings, awards = award_pots(pots, scores, s.button, s.num_seats)
        for i, (amount, winners) in enumerate(awards):
            self._emit(ev.PotAwarded(s.hand_id, i, amount, winners))
        for seat, chips in winnings.items():
            s.players[seat].stack += chips

        net = {p.seat: p.stack - self._starting[p.seat] for p in s.players}
        self._result = HandResult(
            hand_id=s.hand_id,
            board=tuple(s.board),
            pots=tuple(pots),
            winnings={p.seat: winnings.get(p.seat, 0) for p in s.players},
            net=net,
            final_stacks={p.seat: p.stack for p in s.players},
            shown=shown,
            went_to_showdown=bool(shown),
        )
        self._emit(ev.HandEnded(s.hand_id, tuple(net.items())))
