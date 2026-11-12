import random

from holdem.agents.registry import make_agents
from holdem.io.events import EventBus, EventRecorder
from holdem.io.hand_history import (
    HandHistoryWriter,
    decode_event,
    encode_event,
    hand_events,
    load_hands,
)
from holdem.io.narrator import Narrator
from holdem.play import play_session
from holdem.sim.table import Table

from tests.helpers import EVALUATOR


def test_events_roundtrip_through_json(tmp_path):
    bus = EventBus()
    rec = EventRecorder(bus)
    path = tmp_path / "h.jsonl"
    writer = HandHistoryWriter(bus, path)
    agents = make_agents(["random", "calling", "raise"], seed=1, evaluator=EVALUATOR)
    table = Table(agents, rng=random.Random(1), evaluator=EVALUATOR, bus=bus)
    for _ in range(25):
        table.play_hand()
    assert writer.hands_written == 25
    for e in rec.events:
        assert decode_event(encode_event(e)) == e
    hands = list(load_hands(path))
    assert [h["hand_id"] for h in hands] == list(range(1, 26))
    replayed = [e for h in hands for e in hand_events(h)]
    assert replayed == rec.events
    assert all(sum(h["net"].values()) == 0 for h in hands)


def test_narrator_replays_a_hand(tmp_path):
    lines: list[str] = []
    bus = EventBus()
    path = tmp_path / "h.jsonl"
    HandHistoryWriter(bus, path)
    agents = make_agents(["calling", "calling"], seed=2, evaluator=EVALUATOR)
    Table(agents, rng=random.Random(2), evaluator=EVALUATOR, bus=bus).play_hand()
    narrator = Narrator(out=lines.append)
    for e in hand_events(next(load_hands(path))):
        narrator.on_event(e)
    text = "\n".join(lines)
    assert "Hand #1" in text and "SHOWDOWN" in text and "Result:" in text


def scripted(answers):
    it = iter(answers)
    return lambda prompt: next(it, "q")


def test_play_session_quit_immediately():
    out: list[str] = []
    result = play_session(["easy"], seed=1, input_fn=scripted(["q"]), out=out.append, delay=0)
    assert result.hands_played == 0 and result.net == 0
    assert any("Session over" in line for line in out)


def test_play_session_calling_through_several_hands(tmp_path):
    out: list[str] = []
    path = tmp_path / "game.jsonl"
    # Always call/check, press Enter between hands, decline any rebuy.
    answers = ["c"] * 2000
    result = play_session(
        ["beginner", "hard"],
        seed=7,
        input_fn=lambda p: "n" if "Rebuy" in p else ("" if "next hand" in p else "c"),
        out=out.append,
        delay=0,
        history_path=path,
        max_hands=15,
    )
    assert 1 <= result.hands_played <= 15
    assert result.final_stack >= 0
    hands = list(load_hands(path))
    assert len(hands) == result.hands_played
    assert sum(h["net"]["You"] for h in hands) == result.net
    assert any("learned about you" in line for line in out)


def test_play_session_rejects_unknown_difficulty():
    import pytest

    with pytest.raises(ValueError):
        play_session(["impossible"], input_fn=scripted([]), out=lambda _: None)
