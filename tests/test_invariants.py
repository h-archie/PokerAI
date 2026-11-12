"""Property-style tests over thousands of random hands."""

import random

from holdem.engine.engine import HandEngine

from tests.helpers import EVALUATOR, random_action


def _play_random_hand(seed: int):
    rng = random.Random(seed)
    n = rng.randint(2, 6)
    stacks = [rng.choice([rng.randint(1, 300), rng.randint(300, 5000)]) for _ in range(n)]
    eng = HandEngine(
        [(f"P{i}", s) for i, s in enumerate(stacks)],
        button=rng.randrange(n),
        small_blind=50,
        big_blind=100,
        rng=rng,
        evaluator=EVALUATOR,
        hand_id=seed,
    )
    eng.start()
    steps = 0
    while not eng.is_over:
        seat = eng.state.to_act
        view = eng.view_for(seat)
        assert view.legal is not None
        eng.apply(random_action(view.legal, rng))
        steps += 1
        assert steps < 500, "hand did not terminate"
    return stacks, eng


def test_chip_conservation_over_10k_random_hands():
    showdowns = 0
    for seed in range(10_000):
        stacks, eng = _play_random_hand(seed)
        r = eng.result()
        assert sum(r.final_stacks.values()) == sum(stacks), seed
        assert all(v >= 0 for v in r.final_stacks.values()), seed
        assert sum(r.net.values()) == 0, seed
        assert sum(p.amount for p in r.pots) == sum(stacks) - sum(
            stacks[i] - eng.state.players[i].committed_total for i in range(len(stacks))
        )
        if r.went_to_showdown:
            assert len(r.board) == 5, seed
        showdowns += r.went_to_showdown
    assert showdowns > 1000  # sanity: the random driver reaches showdown often


def test_same_seed_replays_identically():
    _, a = _play_random_hand(42)
    _, b = _play_random_hand(42)
    assert a.state.history == b.state.history
    assert a.result() == b.result()
