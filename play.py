"""Play Texas Hold'em against bots:  python play.py --difficulty hard

Same options as `python -m holdem.cli play` (see --help).
"""

import sys

from holdem.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["play", *sys.argv[1:]]))
