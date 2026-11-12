"""Watch one hand of Hold'em between bots, step by step.

    python demo.py                                    # hard vs medium vs calling
    python demo.py --seed 11 --agents beginner,easy,medium,hard

Agents: see `python -m holdem.cli agents`. For the smart bots (beginner to
hard) the demo also prints *why* they chose each action.

The narrator shows everyone's hole cards up front, like a TV broadcast; the
bots themselves only ever see their own cards (via PlayerView).
"""

from __future__ import annotations

import argparse
import random

from holdem.agents.registry import make_agents
from holdem.agents.smart import SmartAgent
from holdem.core.evaluator import TreysEvaluator
from holdem.engine.engine import HandEngine
from holdem.io import events as ev
from holdem.io.narrator import Narrator, fmt_cards

NAMES = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=15, help="random seed (same seed = same hand)")
    ap.add_argument("--agents", default="hard,medium,calling", help="2-6 comma-separated agents")
    ap.add_argument("--stack", type=int, default=1000)
    ap.add_argument("--ascii", action="store_true", help="plain card text instead of suit symbols")
    args = ap.parse_args()

    kinds = [k.strip() for k in args.agents.split(",") if k.strip()]
    if not 2 <= len(kinds) <= 6:
        ap.error("need between 2 and 6 agents")
    evaluator = TreysEvaluator()
    agents = make_agents(kinds, args.seed, evaluator)
    names = [f"{NAMES[i]} ({a.name})" for i, a in enumerate(agents)]
    width = max(len(n) for n in names)
    pretty = not args.ascii

    bus = ev.EventBus()
    Narrator(bus, pretty=pretty, evaluator=evaluator)
    for agent in agents:
        bus.subscribe(agent.on_event)

    engine = HandEngine(
        [(n, args.stack) for n in names],
        button=0,
        small_blind=10,
        big_blind=20,
        rng=random.Random(args.seed),
        evaluator=evaluator,
        bus=bus,
        hand_id=args.seed,
    )
    engine.start()

    print("\n  Hole cards (narrator only - each bot sees just its own):")
    for p in engine.state.players:
        print(f"    {p.name:<{width}} [ {fmt_cards(p.hole, pretty)} ]")
    print("\n--- PREFLOP ---")

    while not engine.is_over:
        seat = engine.state.to_act
        agent = agents[seat]
        view = engine.view_for(seat)  # the ONLY thing a bot is given
        action = agent.act(view)
        if isinstance(agent, SmartAgent) and agent.last_decision:
            print(f"  {names[seat]:<{width}} thinks: {agent.last_decision.reason}")
        engine.apply(action)  # the narrator prints the action itself


if __name__ == "__main__":
    main()
