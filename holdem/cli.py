"""Command-line entry point.

    python -m holdem.cli agents
    python -m holdem.cli match --agents smart,random,calling --hands 3000 --seed 1
"""

from __future__ import annotations

import argparse
import sys
import time

from holdem.agents.registry import AGENTS, make_agents
from holdem.core.evaluator import TreysEvaluator
from holdem.sim.match import run_match
from holdem.sim.metrics import format_report, summarize


def cmd_agents(_: argparse.Namespace) -> int:
    for name, (_, description) in AGENTS.items():
        print(f"  {name:<8} {description}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    kinds = [k.strip() for k in args.agents.split(",") if k.strip()]
    if not 2 <= len(kinds) <= 6:
        print("need between 2 and 6 agents", file=sys.stderr)
        return 2
    evaluator = TreysEvaluator()
    try:
        agents = make_agents(kinds, args.seed, evaluator)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    def progress(done: int, total: int) -> None:
        print(f"\r  {done}/{total} hands", end="", file=sys.stderr, flush=True)

    print(f"Match: {', '.join(a.name for a in agents)} | {args.hands} hands | seed {args.seed}")
    start = time.perf_counter()
    result = run_match(
        agents,
        args.hands,
        seed=args.seed,
        small_blind=args.sb,
        big_blind=args.bb,
        starting_stack=args.stack,
        stack_mode=args.mode,
        evaluator=evaluator,
        progress=None if args.quiet else progress,
    )
    if not args.quiet:
        print("\r" + " " * 30 + "\r", end="", file=sys.stderr)
    elapsed = time.perf_counter() - start
    print(format_report(summarize(result)))
    print(f"\n{result.hands} hands in {elapsed:.1f}s ({result.hands / elapsed:.0f} hands/s)")
    if result.warnings:
        print("Warnings:")
        for msg, count in result.warnings.most_common():
            print(f"  {count:>5} x {msg}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="holdem", description="Texas Hold'em bot simulator")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("agents", help="list available agents").set_defaults(func=cmd_agents)

    m = sub.add_parser("match", help="play agents against each other")
    m.add_argument("--agents", default="smart,random,calling", help="comma-separated agent names")
    m.add_argument("--hands", type=int, default=3000)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--sb", type=int, default=50)
    m.add_argument("--bb", type=int, default=100)
    m.add_argument("--stack", type=int, default=10_000)
    m.add_argument("--mode", choices=["reset", "carry"], default="reset")
    m.add_argument("--quiet", action="store_true", help="no progress counter")
    m.set_defaults(func=cmd_match)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
