"""Summarise a match: big blinds won per 100 hands, with a 95% confidence interval.

bb/100 is the standard poker win-rate unit. The confidence interval tells you
whether a result is real or just luck: if the whole interval is above zero,
the agent is winning with ~95% confidence.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from holdem.sim.match import MatchResult


@dataclass(frozen=True, slots=True)
class AgentReport:
    name: str
    hands: int
    net_chips: int
    bb_per_100: float
    ci95: float  # half-width of the 95% confidence interval on bb/100
    hands_won: float  # fraction of hands with a positive result

    @property
    def low(self) -> float:
        return self.bb_per_100 - self.ci95

    @property
    def high(self) -> float:
        return self.bb_per_100 + self.ci95

    @property
    def verdict(self) -> str:
        if self.low > 0:
            return "winning"
        if self.high < 0:
            return "losing"
        return "unclear"


def summarize(result: MatchResult) -> list[AgentReport]:
    reports = []
    bb = result.big_blind
    for name, deltas in zip(result.names, result.deltas):
        n = len(deltas)
        in_bb = [d / bb for d in deltas]
        mean = statistics.fmean(in_bb) if n else 0.0
        sd = statistics.stdev(in_bb) if n > 1 else 0.0
        reports.append(
            AgentReport(
                name=name,
                hands=n,
                net_chips=sum(deltas),
                bb_per_100=mean * 100,
                ci95=1.96 * sd / math.sqrt(n) * 100 if n > 1 else math.inf,
                hands_won=sum(d > 0 for d in deltas) / n if n else 0.0,
            )
        )
    return sorted(reports, key=lambda r: r.bb_per_100, reverse=True)


def format_report(reports: list[AgentReport]) -> str:
    header = f"{'agent':<10} {'hands':>7} {'net chips':>11} {'bb/100':>9} {'95% CI':>19} {'won':>6}  verdict"
    lines = [header, "-" * len(header)]
    for r in reports:
        ci = f"[{r.low:+.1f}, {r.high:+.1f}]"
        lines.append(
            f"{r.name:<10} {r.hands:>7} {r.net_chips:>+11} {r.bb_per_100:>+9.1f} {ci:>19} "
            f"{r.hands_won:>6.0%}  {r.verdict}"
        )
    return "\n".join(lines)
