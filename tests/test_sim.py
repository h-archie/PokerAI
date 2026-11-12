import random

import pytest

from holdem.agents.base import Agent
from holdem.agents.baseline import CallingStation, RandomAgent
from holdem.agents.registry import make_agents
from holdem.engine.actions import Action
from holdem.sim.match import MatchResult, run_match
from holdem.sim.metrics import format_report, summarize
from holdem.sim.table import Table

from tests.helpers import EVALUATOR


class Crasher(Agent):
    def act(self, view):
        raise RuntimeError("boom")

    def on_event(self, event):
        raise KeyError("also boom")


class Cheater(Agent):
    def act(self, view):
        return Action.raise_to(10**9)


def test_table_rotates_button():
    agents = [RandomAgent(f"r{i}", rng=random.Random(i)) for i in range(4)]
    table = Table(agents, rng=random.Random(0), evaluator=EVALUATOR)
    buttons = []
    for _ in range(8):
        buttons.append(table.button)
        table.play_hand()
    assert buttons == [0, 1, 2, 3, 0, 1, 2, 3]


def test_carry_mode_conserves_chips_plus_rebuys():
    agents = [RandomAgent(f"r{i}", rng=random.Random(i)) for i in range(3)]
    table = Table(agents, rng=random.Random(1), evaluator=EVALUATOR, stack_mode="carry")
    expected_total = sum(table.stacks)
    for _ in range(300):
        # Rebuys happen at the start of play_hand: top up stacks below 1 BB.
        expected_total += sum(
            table.starting_stack - s for s in table.stacks if s < table.big_blind
        )
        table.play_hand()
        assert sum(table.stacks) == expected_total
    assert sum(table.rebuys) > 0  # the random agents do bust


def test_buggy_agents_cannot_crash_the_table():
    agents = [Crasher("crash"), Cheater("cheat"), CallingStation("calling")]
    table = Table(agents, rng=random.Random(0), evaluator=EVALUATOR)
    for _ in range(30):
        table.play_hand()
    assert table.warnings["crash: act RuntimeError"] > 0
    assert table.warnings["cheat: illegal action"] > 0
    assert table.warnings["crash: on_event KeyError"] > 0


def test_table_rejects_duplicate_names():
    with pytest.raises(ValueError):
        Table([CallingStation("x"), CallingStation("x")])


def test_match_is_zero_sum_and_deterministic():
    def go():
        agents = make_agents(["random", "calling", "raise"], seed=4, evaluator=EVALUATOR)
        return run_match(agents, 150, seed=4, evaluator=EVALUATOR)

    a, b = go(), go()
    assert a.deltas == b.deltas
    assert a.hands == 150
    for h in range(a.hands):
        assert sum(d[h] for d in a.deltas) == 0


def test_metrics_bb_per_100_and_confidence_interval():
    result = MatchResult(["a", "b"], big_blind=100, deltas=[[100, -100] * 50, [-100, 100] * 50])
    ra = {r.name: r for r in summarize(result)}["a"]
    assert ra.bb_per_100 == pytest.approx(0.0)
    assert ra.ci95 == pytest.approx(1.96 * 1.00503781 / 10 * 100, rel=1e-4)
    assert ra.verdict == "unclear"

    winning = MatchResult(["w", "l"], 100, [[50] * 99 + [150], [-50] * 99 + [-150]])
    reports = summarize(winning)
    assert reports[0].name == "w" and reports[0].bb_per_100 == pytest.approx(51.0)
    assert reports[0].verdict == "winning" and reports[1].verdict == "losing"
    assert "bb/100" in format_report(reports)


@pytest.mark.parametrize("opponent", ["random", "calling"])
def test_smart_beats_baseline_heads_up(opponent):
    """Day 2 exit criterion, as a seeded regression test."""
    agents = make_agents(["smart", opponent], seed=11, evaluator=EVALUATOR)
    report = {r.name: r for r in summarize(run_match(agents, 400, seed=11, evaluator=EVALUATOR))}
    assert report["smart"].low > 0, report["smart"]
