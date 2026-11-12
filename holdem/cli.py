"""Command-line entry point.

    python -m holdem.cli play --difficulty medium --opponents 2
    python -m holdem.cli agents
    python -m holdem.cli match --agents hard,medium --hands 2000 --duplicate
    python -m holdem.cli replay history/game-....jsonl --hand 3
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from holdem.agents.registry import AGENTS, DIFFICULTY, make_agents
from holdem.core.evaluator import TreysEvaluator
from holdem.io.hand_history import hand_events, load_hands
from holdem.io.narrator import Narrator
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

    dup = " | duplicate" if args.duplicate else ""
    print(f"Match: {', '.join(a.name for a in agents)} | {args.hands} hands | seed {args.seed}{dup}")
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
        duplicate=args.duplicate,
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


def cmd_play(args: argparse.Namespace) -> int:
    from holdem.play import default_history_path, play_session

    if args.bots:
        bots = [b.strip() for b in args.bots.split(",") if b.strip()]
    else:
        bots = [args.difficulty] * args.opponents
    try:
        sb, bb = (int(x) for x in args.blinds.split("/"))
    except ValueError:
        print("--blinds must look like 10/20", file=sys.stderr)
        return 2
    try:
        play_session(
            bots,
            stack=args.stack,
            small_blind=sb,
            big_blind=bb,
            seed=args.seed,
            delay=args.delay,
            pretty=not args.ascii,
            history_path=None if args.no_history else default_history_path(),
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    hands = list(load_hands(args.file))
    if not hands:
        print("no hands in file", file=sys.stderr)
        return 1
    if args.hand is None:
        print(f"{len(hands)} hands in {args.file}:")
        for h in hands:
            net = ", ".join(f"{n} {d:+d}" for n, d in h["net"].items() if d)
            print(f"  #{h['hand_id']:<4} board [{h['board'] or '-'}]  {net}")
        print("\nShow one with --hand N")
        return 0
    match = [h for h in hands if h["hand_id"] == args.hand]
    if not match:
        print(f"hand {args.hand} not found", file=sys.stderr)
        return 1
    narrator = Narrator(pretty=not args.ascii)
    for event in hand_events(match[0]):
        narrator.on_event(event)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="holdem", description="Texas Hold'em bot simulator")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("play", help="play against bots yourself")
    p.add_argument("--difficulty", choices=list(DIFFICULTY), default="medium")
    p.add_argument("--opponents", type=int, default=2, choices=range(1, 6))
    p.add_argument("--bots", help="mix levels instead, e.g. beginner,easy,hard")
    p.add_argument("--stack", type=int, default=1000)
    p.add_argument("--blinds", default="10/20", help="small/big blind, e.g. 10/20")
    p.add_argument("--seed", type=int, help="same seed = same cards")
    p.add_argument("--delay", type=float, default=0.6, help="seconds to pause after each bot action")
    p.add_argument("--ascii", action="store_true", help="plain card text (Ah) instead of symbols (A♥)")
    p.add_argument("--no-history", action="store_true", help="don't save a hand history file")
    p.set_defaults(func=cmd_play)

    sub.add_parser("agents", help="list available agents").set_defaults(func=cmd_agents)

    r = sub.add_parser("replay", help="list or replay hands from a history file")
    r.add_argument("file", type=Path)
    r.add_argument("--hand", type=int, help="hand number to replay")
    r.add_argument("--ascii", action="store_true")
    r.set_defaults(func=cmd_replay)

    m = sub.add_parser("match", help="play agents against each other")
    m.add_argument("--agents", default="hard,medium,easy", help="comma-separated agent names")
    m.add_argument("--hands", type=int, default=3000)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--sb", type=int, default=50)
    m.add_argument("--bb", type=int, default=100)
    m.add_argument("--stack", type=int, default=10_000)
    m.add_argument("--mode", choices=["reset", "carry"], default="reset")
    m.add_argument("--duplicate", action="store_true", help="replay every deal with seats rotated (less luck)")
    m.add_argument("--quiet", action="store_true", help="no progress counter")
    m.set_defaults(func=cmd_match)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
