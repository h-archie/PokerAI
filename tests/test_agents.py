"""Every agent must produce legal actions in every situation."""

import random

import pytest

from holdem.agents.base import Agent
from holdem.agents.registry import AGENTS, make_agents
from holdem.agents.smart import SmartAgent
from holdem.engine.actions import Action
from holdem.sim.table import Table

from tests.helpers import EVALUATOR


@pytest.mark.parametrize("kind", list(AGENTS))
def test_agent_never_makes_illegal_actions(kind):
    rng = random.Random(5)
    # The agent under test plays against a mix, at random table sizes.
    for n in (2, 3, 6):
        kinds = [kind] + [rng.choice(["random", "calling", "raise"]) for _ in range(n - 1)]
        agents = make_agents(kinds, seed=n, evaluator=EVALUATOR)
        table = Table(agents, rng=random.Random(n), evaluator=EVALUATOR, stack_mode="carry")
        for _ in range(60 if kind == "smart" else 150):
            table.play_hand()
        assert not table.warnings, table.warnings


def test_make_agents_unique_names_and_unknown_kind():
    agents = make_agents(["smart", "smart", "random"], seed=1, evaluator=EVALUATOR)
    assert [a.name for a in agents] == ["smart", "smart2", "random"]
    with pytest.raises(ValueError):
        make_agents(["nope"], seed=1, evaluator=EVALUATOR)


def test_smart_agent_explains_its_decisions():
    agents = make_agents(["smart", "calling"], seed=2, evaluator=EVALUATOR)
    Table(agents, rng=random.Random(2), evaluator=EVALUATOR).play_hand()
    smart = agents[0]
    assert isinstance(smart, SmartAgent)
    assert smart.last_decision is not None and smart.last_decision.reason
    assert 0.0 <= smart.last_equity <= 1.0


def test_smart_agent_folds_trash_to_a_raise_preflop():
    from tests.helpers import stacked_engine

    eng = stacked_engine([10_000] * 3, ["AhAs", "7c2d", "8h3s"], "KdQd4c5h6h", button=0)
    eng.apply(Action.raise_to(1000))  # seat 0 (UTG) raises big
    smart = SmartAgent(rng=random.Random(0), evaluator=EVALUATOR)
    assert smart.act(eng.view_for(1)) == Action.fold()  # 72o in the small blind
