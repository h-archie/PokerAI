import random

import pytest

from holdem.agents.baseline import AlwaysRaise, CallingStation, TightPassive
from holdem.agents.registry import make_agents
from holdem.agents.smart import SmartAgent
from holdem.ai.opponent_model import PRIORS, OpponentModel
from holdem.ai.ranges import TOTAL_COMBOS, ranked_classes, top_range
from holdem.engine.actions import Action
from holdem.io.events import EventBus
from holdem.sim.table import Table

from tests.helpers import EVALUATOR, play_script, stacked_engine


def test_top_range_sizes_and_order():
    assert len(top_range(1.0)) == TOTAL_COMBOS
    assert len(top_range(0.10)) == pytest.approx(0.10 * TOTAL_COMBOS, abs=12)
    assert set(top_range(0.05)) <= set(top_range(0.20))
    assert ranked_classes()[0] == "AA"
    assert ranked_classes()[-1] in {"32o", "72o", "42o", "62o", "52o", "82o"}


def test_unknown_player_gets_priors():
    s = OpponentModel().stats("nobody")
    assert (s.vpip, s.pfr, s.aggression, s.fold_to_bet) == pytest.approx(
        (PRIORS["vpip"], PRIORS["pfr"], PRIORS["aggression"], PRIORS["fold_to_bet"])
    )


def test_counts_from_a_scripted_hand():
    bus = EventBus()
    model = OpponentModel(prior_weight=0)  # no smoothing: raw frequencies
    bus.subscribe(model.on_event)
    # Seat 0 (button/UTG) raises, seat 1 (SB) folds, seat 2 (BB) calls.
    eng = stacked_engine([1000] * 3, ["AhAs", "7c2d", "KhKs"], "2c7d9c3d8s", button=0, bus=bus)
    play_script(eng, [(0, Action.raise_to(300)), (1, Action.fold()), (2, Action.call())])
    play_script(eng, [(2, Action.bet(200)), (0, Action.fold())])
    p0, p1, p2 = (model.stats(f"P{i}") for i in range(3))
    assert (p0.vpip, p0.pfr) == (1.0, 1.0)
    assert p0.fold_to_bet == 1.0  # faced one bet (flop), folded
    assert (p1.vpip, p1.fold_to_bet) == (0.0, 1.0)  # faced the raise, folded
    assert (p2.vpip, p2.pfr) == (1.0, 0.0)
    assert p2.aggression == 0.5  # one call, one bet


@pytest.mark.parametrize(
    "agent,check",
    [
        (CallingStation("x"), lambda s: s.fold_to_bet < 0.15 and s.aggression < 0.15 and s.vpip > 0.45),
        (AlwaysRaise("x"), lambda s: s.aggression > 0.8 and s.pfr > 0.8),
        (TightPassive("x"), lambda s: s.vpip < 0.2 and s.aggression < 0.25 and s.fold_to_bet > 0.6),
    ],
    ids=["station", "maniac", "rock"],
)
def test_model_learns_baseline_styles(agent, check):
    observer = SmartAgent("obs", rng=random.Random(0), evaluator=EVALUATOR, use_model=True)
    table = Table([observer, agent], rng=random.Random(1), evaluator=EVALUATOR)
    for _ in range(150):
        table.play_hand()
    stats = observer.model.stats("x")
    assert stats.hands == 150
    assert check(stats), stats


def test_hard_bot_narrows_a_tight_raisers_range():
    hard = SmartAgent("hard", rng=random.Random(0), evaluator=EVALUATOR, use_model=True)
    # Teach it that P0 almost never raises (tight).
    bus = EventBus()
    bus.subscribe(hard.on_event)
    for _ in range(40):
        eng = stacked_engine([1000, 1000], ["2c3d", "4h5s"], "9c9d9h2s3s", button=0, bus=bus)
        eng.apply(Action.fold())
    eng = stacked_engine([1000, 1000], ["AhAs", "JhJs"], "2c7d9c3d8s", button=0, bus=bus)
    eng.apply(Action.raise_to(300))  # the tight player suddenly raises
    view = eng.view_for(1)
    (frac,) = hard.range_fractions(view)
    assert frac < 0.12
    medium = SmartAgent("m", rng=random.Random(0), evaluator=EVALUATOR)
    # Medium thinks JJ is a monster; hard knows it is up against a tight range.
    assert hard.equity(view, 1) < medium.equity(view, 1) - 0.1


def test_reset_forgets_opponents():
    agents = make_agents(["hard", "calling"], seed=0, evaluator=EVALUATOR)
    table = Table(agents, rng=random.Random(0), evaluator=EVALUATOR)
    for _ in range(10):
        table.play_hand()
    assert agents[0].model.stats("calling").hands == 10
    agents[0].reset()
    assert agents[0].model.stats("calling").hands == 0
