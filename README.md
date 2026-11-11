# PokerAI

A simulated No-Limit Texas Hold'em engine and poker bots, in Python 3.11+.

## Status

- **Day 1 (done):** cards, hand evaluation, rules engine, side pots, the
  imperfect-information `PlayerView`, and public events, with tests.
- Day 2: agents, Monte Carlo equity, decision policy, match runner, CLI.
- Day 3: opponent modelling, hand-history logging, tuning.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Watch a hand

```bash
python demo.py                      # 3 players, seed 7
python demo.py --seed 11 --players 5
```

Prints every blind, action, street and the showdown. The bots in the demo are
placeholders (mostly check/call, sometimes bet); real bots come on Day 2.

## Layout

```
holdem/
  core/cards.py        Card, Rank, Suit, Deck (seeded RNG, stacked decks for tests)
  core/evaluator.py    HandEvaluator protocol: TreysEvaluator (fast) + NaiveEvaluator (test oracle)
  engine/actions.py    Action / ActionType ("amount" = total committed this street)
  engine/state.py      GameState, PlayerState, Street
  engine/rules.py      legal_actions(), min-raise and re-open rules
  engine/pot.py        Side pots and payouts (odd chips left of the button)
  engine/engine.py     HandEngine: the state machine for one hand
  engine/view.py       PlayerView: what one seat is allowed to see
  io/events.py         Public events + synchronous EventBus
tests/                 Unit, scripted-hand and 10k-hand invariant tests
```

## Driving a hand

The engine never calls agents; a driver loop does:

```python
import random
from holdem.core.evaluator import TreysEvaluator
from holdem.engine.actions import Action
from holdem.engine.engine import HandEngine

eng = HandEngine([("Alice", 1000), ("Bob", 1000)], button=0,
                 small_blind=50, big_blind=100,
                 rng=random.Random(42), evaluator=TreysEvaluator())
eng.start()
while not eng.is_over:
    view = eng.view_for(eng.state.to_act)
    eng.apply(Action.check() if view.legal.can_check else Action.call())
print(eng.result().net)
```
