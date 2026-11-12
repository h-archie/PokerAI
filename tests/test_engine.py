import pytest

from holdem.core.cards import parse_cards
from holdem.engine.actions import Action, ActionType
from holdem.engine.rules import IllegalAction
from holdem.engine.state import Street
from holdem.io.events import (
    ActionTaken,
    BlindPosted,
    EventBus,
    EventRecorder,
    HandEnded,
    ShowdownEvent,
    StreetAdvanced,
)

from tests.helpers import play_script, stacked_engine

LOW_BOARD = "2c7d9c3d8s"  # no straights/flushes for the pocket pairs used below


# ---------------------------------------------------------------- blinds & order


def test_heads_up_button_posts_sb_and_acts_first_preflop_last_postflop():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    s = eng.state
    assert s.players[0].committed_street == 50 and s.players[1].committed_street == 100
    assert s.to_act == 0  # button/SB first preflop
    play_script(eng, [(0, Action.call()), (1, Action.check())])
    assert s.street is Street.FLOP and len(s.board) == 3
    assert s.to_act == 1  # non-button first postflop


def test_three_handed_order():
    eng = stacked_engine([1000] * 3, ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    s = eng.state
    assert s.players[1].committed_street == 50  # SB
    assert s.players[2].committed_street == 100  # BB
    assert s.to_act == 0  # UTG = button when 3-handed
    play_script(eng, [(0, Action.call()), (1, Action.call()), (2, Action.check())])
    assert s.street is Street.FLOP and s.to_act == 1  # first left of button


def test_fold_to_big_blind():
    eng = stacked_engine([1000] * 3, ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.fold()), (1, Action.fold())])
    assert eng.is_over
    r = eng.result()
    assert r.net == {0: 0, 1: -50, 2: 50}
    assert not r.went_to_showdown and r.shown == {}


def test_big_blind_gets_option_after_limps():
    eng = stacked_engine([1000] * 3, ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.call())])
    assert eng.state.to_act == 2 and eng.state.street is Street.PREFLOP
    legal = eng.legal_actions()
    assert legal.can_check and legal.can_raise and legal.min_raise_to == 200
    eng.apply(Action.raise_to(400))
    assert eng.state.to_act == 0  # action reopened


# ------------------------------------------------------------------- raises


def test_min_raise_tracks_last_full_raise():
    eng = stacked_engine([5000] * 3, ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    assert eng.legal_actions().min_raise_to == 200
    eng.apply(Action.raise_to(300))  # raise by 200
    assert eng.legal_actions().min_raise_to == 500
    with pytest.raises(IllegalAction):
        eng.apply(Action.raise_to(450))
    eng.apply(Action.raise_to(1000))  # raise by 700
    assert eng.legal_actions().min_raise_to == 1700


def test_postflop_minimum_bet_is_big_blind():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.check())])
    legal = eng.legal_actions()
    assert legal.can_check and legal.min_raise_to == 100 and legal.max_raise_to == 900
    eng.apply(Action.bet(100))
    assert eng.state.history[-1].action == Action(ActionType.BET, 100)


def test_incomplete_all_in_raise_does_not_reopen_betting():
    # Seat 0 (button/UTG) 1000, seat 1 (SB) 1000, seat 2 (BB) 250.
    eng = stacked_engine([1000, 1000, 250], ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.raise_to(200)), (1, Action.call())])
    eng.apply(Action.all_in())  # BB to 250: only +50, less than a full raise of 100
    s = eng.state
    assert s.history[-1].action == Action(ActionType.ALL_IN, 250)
    assert s.to_act == 0
    legal = eng.legal_actions()
    assert not legal.can_raise and legal.call_amount == 50
    with pytest.raises(IllegalAction):
        eng.apply(Action.raise_to(600))
    eng.apply(Action.call())
    assert not eng.legal_actions().can_raise  # seat 1 also closed
    eng.apply(Action.call())
    assert s.street is Street.FLOP


def test_full_all_in_raise_reopens_betting():
    eng = stacked_engine([1000, 1000, 400], ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.raise_to(200)), (1, Action.call())])
    eng.apply(Action.all_in())  # to 400: +200 >= 100, full raise
    assert eng.state.to_act == 0
    assert eng.legal_actions().can_raise


# --------------------------------------------------------------- illegal input


def test_illegal_actions_are_rejected_and_state_unchanged():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    with pytest.raises(IllegalAction):
        eng.apply(Action.check())  # facing the big blind
    with pytest.raises(IllegalAction):
        eng.apply(Action.raise_to(150))  # below min raise
    with pytest.raises(IllegalAction):
        eng.apply(Action.raise_to(5000))  # above stack
    assert eng.state.history == [] and eng.state.to_act == 0
    assert eng.state.players[0].stack == 950


def test_call_when_check_is_possible_is_recorded_as_check():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.call())])
    assert eng.state.history[-1].action == Action.check()


# ------------------------------------------------------------------ showdown


def test_all_in_preflop_runs_out_and_best_hand_wins():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.all_in()), (1, Action.call())])
    assert eng.is_over
    r = eng.result()
    assert r.board == parse_cards(LOW_BOARD)
    assert r.final_stacks == {0: 2000, 1: 0}
    assert r.net == {0: 1000, 1: -1000}
    assert set(r.shown) == {0, 1}


def test_split_pot():
    # Board makes a broadway straight for both players.
    eng = stacked_engine([1000, 1000], ["2h3d", "2s3c"], "AcKdQhJsTc", button=0)
    play_script(eng, [(0, Action.all_in()), (1, Action.call())])
    assert eng.result().net == {0: 0, 1: 0}


def test_three_way_all_in_side_pots_through_engine():
    # Seat 0 short with best hand, seat 1 mid with 2nd best, seat 2 covers everyone.
    eng = stacked_engine([300, 600, 1000], ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.all_in()), (1, Action.all_in()), (2, Action.call())])
    r = eng.result()
    assert r.final_stacks == {0: 900, 1: 600, 2: 400}
    assert sum(r.net.values()) == 0


def test_short_small_blind_all_in_runs_out_immediately():
    eng = stacked_engine([30, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    assert eng.is_over  # SB is all-in posting 30; BB has nothing to decide
    r = eng.result()
    assert r.final_stacks == {0: 60, 1: 970}  # BB's uncalled 70 is returned


def test_uncalled_bet_is_returned():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.raise_to(600)), (1, Action.fold())])
    assert eng.result().final_stacks == {0: 1100, 1: 900}


# ------------------------------------------------------- information hiding


def test_view_contains_no_opponent_hole_cards():
    eng = stacked_engine([1000] * 3, ["AhAs", "KhKs", "QhQs"], LOW_BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.call()), (2, Action.check())])
    view = eng.view_for(1)
    text = repr(view)
    assert view.hole == parse_cards("KhKs")
    for hidden in ("Card('Ah')", "Card('As')", "Card('Qh')", "Card('Qs')", "Card('3d')"):
        assert hidden not in text  # opponents' cards and undealt turn card
    assert view.legal is not None  # seat 1 is first to act on the flop
    assert eng.view_for(0).legal is None
    with pytest.raises(Exception):
        view.pot = 0  # frozen


def test_events_are_public_and_consistent():
    bus = EventBus()
    rec = EventRecorder(bus)
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], LOW_BOARD, button=0, bus=bus)
    play_script(eng, [(0, Action.call()), (1, Action.check())])
    for _ in range(3):  # check down flop, turn, river
        play_script(eng, [(1, Action.check()), (0, Action.check())])
    assert eng.is_over
    assert len(rec.of_type(BlindPosted)) == 2
    assert [e.street for e in rec.of_type(StreetAdvanced)] == [1, 2, 3]
    assert len(rec.of_type(ActionTaken)) == 8
    (showdown,) = rec.of_type(ShowdownEvent)
    # Hole cards only appear in the showdown event.
    for e in rec.events:
        if not isinstance(e, ShowdownEvent):
            assert "Card('Ah')" not in repr(e) and "Card('Kh')" not in repr(e)
    (ended,) = rec.of_type(HandEnded)
    assert sum(delta for _, delta in ended.net) == 0
    assert dict(ended.net) == {0: 100, 1: -100}
