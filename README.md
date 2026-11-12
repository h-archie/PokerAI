# PokerAI

A simulated No-Limit Texas Hold'em engine and poker bots, in Python 3.11+.

## Status

- **Day 1 (done):** cards, hand evaluation, rules engine, side pots, the
  imperfect-information `PlayerView`, and public events, with tests.
- **Day 2 (done):** bots, Monte Carlo equity, preflop equity table, decision
  policy, bet sizing, table/match runner, bb/100 metrics, CLI.
- Day 3: opponent modelling, hand-history logging, tuning.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Watch a hand

```bash
python demo.py --seed 15                              # smart vs random vs calling
python demo.py --seed 4 --agents smart,smart,tight,raise
```

Prints every blind, action, street and the showdown, plus the smart bot's
reasoning ("thinks: ...") before each of its decisions.

## Run a match

```bash
python -m holdem.cli agents                                        # list bots
python -m holdem.cli match --agents smart,calling --hands 3000     # heads-up
python -m holdem.cli match --agents smart,random,calling,raise,tight,smart --hands 1200
```

Results are in **bb/100** (big blinds won per 100 hands) with a 95% confidence
interval. "winning" means the whole interval is above zero.

| Bots | Description |
|---|---|
| `smart` | Preflop equity table + Monte Carlo equity postflop, pot odds, value bets, occasional bluffs |
| `random` | Random fold / call / raise |
| `calling` | Always checks or calls |
| `raise` | Min-raises whenever it can |
| `tight` | Plays only strong starting hands, then calls down |

Day 2 results (3000 hands heads-up, seed 1):

| smart vs | bb/100 | 95% CI |
|---|---|---|
| random | +675 | [+579, +771] |
| calling | +423 | [+376, +470] |
| raise | +1986 | [+1809, +2163] |
| tight | +91 | [+71, +111] |
| smart (itself) | +6 | [-129, +141] (no edge, as expected) |

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
  ai/preflop.py        Preflop equity lookup (169 hand classes x 1-5 opponents)
  ai/equity.py         Monte Carlo equity vs random hands
  ai/policy.py         Decision logic: edge over fair share, pot odds, bluffs
  ai/sizing.py         Intent -> legal bet size (fractions of the pot)
  agents/              Agent base class, baseline bots, SmartAgent, registry
  sim/table.py         Runs hands, rotates the button, isolates buggy bots
  sim/match.py         N-hand matches
  sim/metrics.py       bb/100 and confidence intervals
  cli.py               `python -m holdem.cli ...`
scripts/build_preflop_table.py   Regenerates holdem/ai/data/preflop_equity.json
tests/                 Unit, scripted-hand, invariant and bot-strength tests
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
