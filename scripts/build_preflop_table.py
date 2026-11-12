"""Build holdem/ai/data/preflop_equity.json by Monte Carlo simulation.

    python scripts/build_preflop_table.py --iterations 3000

Takes about a minute on 4 cores. The result is deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from holdem.ai.equity import estimate_equity
from holdem.ai.preflop import MAX_OPPONENTS, all_hand_classes, representative
from holdem.core.evaluator import TreysEvaluator

OUT = Path(__file__).resolve().parent.parent / "holdem" / "ai" / "data" / "preflop_equity.json"


def _row(args: tuple[str, int, int]) -> tuple[str, list[float]]:
    cls, iterations, seed = args
    ev = TreysEvaluator()
    hole = representative(cls)
    row = []
    for n in range(1, MAX_OPPONENTS + 1):
        rng = random.Random(f"{seed}-{cls}-{n}")
        row.append(round(estimate_equity(hole, [], n, rng, ev, iterations).equity, 4))
    return cls, row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    jobs = [(c, args.iterations, args.seed) for c in all_hand_classes()]
    with ProcessPoolExecutor() as pool:
        table = dict(pool.map(_row, jobs))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "Equity vs 1..5 random opponents, by starting-hand class",
        "iterations": args.iterations,
        "seed": args.seed,
        "equity": table,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(table)} hand classes to {OUT}")


if __name__ == "__main__":
    main()
