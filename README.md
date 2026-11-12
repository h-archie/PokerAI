# PokerAI

No-Limit Texas Hold'em in Python 3.11+: a full rules engine, poker bots with
four difficulty levels, and a game you can play against them in the terminal.

## Quick start

```bash
pip install -e ".[dev]"
python play.py
```

## Play against the bots

```bash
python play.py                                  # you vs 2 medium bots
python play.py --difficulty hard --opponents 4  # 4 hard bots
python play.py --bots beginner,easy,hard        # mix difficulty levels
python play.py --help                           # all options
```

On your turn you'll see your cards, the board and your options:

```
  >>> YOUR TURN
      Your cards: [ 8♠ J♠ ]    Board: [ 5♣ A♠ 4♣ ]
      Pot: 120    To call: 0    Your chips: 940
      [c]heck   [r]aise <amount> (bet 20-940)   [a]ll-in   [?] help   [q]uit
  >
```

| Type | To |
|---|---|
| `c` | call, or check if there's nothing to call |
| `f` | fold |
| `r 300` | raise (or bet) **to** 300 in total this round |
| `r min` / `r half` / `r pot` | raise the minimum, half the pot, or the pot |
| `a` | go all-in |
| `?` | help |
| `q` | quit |

Stacks carry over between hands. Bots rebuy when they go broke; you're
offered a rebuy. At the end you get a summary, including what the hard bots
worked out about your playing style. Every game is saved to `history/`:

```bash
python -m holdem.cli replay history/game-20261112-153000.jsonl            # list hands
python -m holdem.cli replay history/game-20261112-153000.jsonl --hand 3   # replay one
```

### Difficulty levels

All four are the same bot with different skill settings:

| Level | Misreads its hand | Random mistakes | Calls too much | Learns your habits |
|---|---|---|---|---|
| `beginner` | a lot | 25% of decisions | a lot | no |
| `easy` | some | 10% | a bit | no |
| `medium` | no | no | no | no |
| `hard` | no | no | no | **yes** |

The `hard` bot tracks how often each opponent plays a hand, raises, bets and
folds to bets. It uses that to guess the range of hands they hold, bluffs more
against players who fold a lot, and never bluffs players who always call.

Each level beats the one below (2000-hand duplicate matches, bb/100 = big
blinds won per 100 hands, with 95% confidence intervals):

| Match | Winner's bb/100 | 95% CI |
|---|---|---|
| easy vs beginner | +262 | [+175, +349] |
| medium vs easy | +256 | [+188, +324] |
| hard vs medium | +114 | [+48, +180] |

## Watch bots play

```bash
python demo.py --seed 15                                # one hand, with each bot's reasoning
python -m holdem.cli match --agents hard,medium --hands 2000 --duplicate
python -m holdem.cli match --agents hard,calling,raise,tight --hands 1200
python -m holdem.cli agents                             # list all bots
```

`--duplicate` replays every deal with the seats rotated so each bot gets the
same cards, which removes most of the luck from a comparison.

Other bots to test against: `random`, `calling` (always calls), `raise`
(always raises), `tight` (only plays strong hands).

## How the bot thinks

1. **How strong is my hand?** Before the flop it looks up a precomputed
   equity table (169 starting hands x 1-5 opponents). After the flop it
   simulates a few hundred random run-outs (Monte Carlo). The hard bot
   simulates against the hands each opponent is *likely* to hold, not random ones.
2. **Compare with a fair share.** With 3 players, 33% equity is break-even.
   A big edge over that means it bets or raises for value.
3. **Facing a bet, check the price.** It calls only if its equity beats the
   pot odds (the share of the final pot it must put in).
4. **Size the bet** as a fraction of the pot, and occasionally bluff.

The demo prints this reasoning, e.g. `thinks: value hand (equity 58% vs fair 33%): bet`.

## Project layout

```
play.py                  Launcher: python play.py
demo.py                  Watch one hand between bots
holdem/
  core/                  Cards, deck, hand evaluator (treys + a test oracle)
  engine/                Rules: betting, side pots, showdown; PlayerView hides other players' cards
  ai/
    preflop.py           Preflop equity table lookup
    equity.py            Monte Carlo equity, optionally against hand ranges
    ranges.py            "Top X% of hands" as concrete card combos
    opponent_model.py    Learns VPIP, PFR, aggression, fold-to-bet from public events
    policy.py            Decision rules
    sizing.py            Turns decisions into legal bet sizes
  agents/
    smart.py             The bot (all difficulty levels)
    human.py             You, at the keyboard
    baseline.py          Simple test opponents
    registry.py          Difficulty presets and bot names
  sim/                   Table, matches (incl. duplicate), bb/100 metrics
  io/                    Events, narrator (text output), hand-history files
  play.py                The interactive game loop
  cli.py                 python -m holdem.cli play | match | replay | agents
scripts/build_preflop_table.py   Rebuilds holdem/ai/data/preflop_equity.json
tests/                   140 tests: rules, side pots, equity, bots, game, history
```

## Running the tests

```bash
pytest
```

The tests include a check that chips are never created or lost over 10,000
random hands, and that each bot always makes legal moves.

## Simplifications

- Hole cards are dealt two at a time in seat order, with no burn cards.
  This makes no difference on a shuffled deck.
- If the big blind is short-stacked, the amount to call preflop is the
  largest blind actually posted.
- Bots don't read the board texture: the hard bot narrows ranges from
  preflop actions and how aggressive a player is, not from which cards came.
