import pytest

from holdem.agents.base import StopGame
from holdem.agents.human import HumanAgent, parse_command
from holdem.engine.actions import Action, ActionType

from tests.helpers import play_script, stacked_engine

BOARD = "2c7d9c3d8s"


def preflop_view():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], BOARD, button=0)  # seat 0 faces the BB
    return eng.view_for(0)


def flop_view():
    eng = stacked_engine([1000, 1000], ["AhAs", "KhKs"], BOARD, button=0)
    play_script(eng, [(0, Action.call()), (1, Action.check())])
    return eng.view_for(1)  # pot 40... (blinds 50/100 -> pot 200), nothing to call


@pytest.mark.parametrize(
    "text,expected",
    [
        ("c", Action.call()),
        ("call", Action.call()),
        ("f", Action.fold()),
        ("a", Action.all_in()),
        ("r", Action.raise_to(200)),
        ("r min", Action.raise_to(200)),
        ("r 450", Action.raise_to(450)),
        ("RAISE 450", Action.raise_to(450)),
        ("r max", Action.all_in()),
    ],
)
def test_parse_valid_commands_facing_a_bet(text, expected):
    assert parse_command(text, preflop_view()) == expected


def test_parse_check_and_free_fold_protection():
    view = flop_view()
    assert parse_command("c", view) == Action.check()
    assert parse_command("k", view) == Action.check()
    assert isinstance(parse_command("f", view), str)  # warned: checking is free
    assert parse_command("f!", view) == Action.fold()


def test_parse_pot_sized_bets():
    view = flop_view()  # pot 200
    assert parse_command("r pot", view) == Action.raise_to(200)
    assert parse_command("r half", view) == Action.raise_to(100)


@pytest.mark.parametrize("text", ["", "zzz", "r abc", "r 150", "r 99999"])
def test_parse_errors_are_messages(text):
    result = parse_command(text, preflop_view())
    assert isinstance(result, str) and result


def test_quit_raises_stop_game():
    with pytest.raises(StopGame):
        parse_command("q", preflop_view())


def test_human_agent_reprompts_until_valid():
    typed = iter(["nonsense", "r 10", "r 300"])
    shown: list[str] = []
    agent = HumanAgent(input_fn=lambda _: next(typed), out=shown.append)
    action = agent.act(preflop_view())
    assert action == Action.raise_to(300)
    assert "YOUR TURN" in shown[0]
    assert any("Unknown command" in s for s in shown)
    assert any("minimum raise" in s for s in shown)


def test_end_of_input_quits():
    def eof(_):
        raise EOFError

    with pytest.raises(StopGame):
        HumanAgent(input_fn=eof, out=lambda _: None).act(preflop_view())


def test_prompt_never_shows_opponent_cards():
    shown: list[str] = []
    HumanAgent(input_fn=lambda _: "c", out=shown.append, pretty=False).act(preflop_view())
    assert "Ah As" in shown[0] and "Kh" not in shown[0]
