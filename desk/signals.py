"""Signal engine — direct port of the Google Sheet Summary tab.

Each category runs four boolean checks against FRED data.
Score 3–4 → green, 2 → yellow, 0–1 → red. Colors indicate DIRECTION
(up / loose), not good vs. bad. These are quick-glance heuristics,
not the book's methodology and not trading signals.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Check:
    label: str
    passed: bool | None  # None = data unavailable


@dataclass
class Signal:
    category: str
    checks: list[Check]
    hi: str   # label when score >= 3
    lo: str   # label when score <= 1
    mid: str  # label when score == 2

    @property
    def score(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def loading(self) -> bool:
        return any(c.passed is None for c in self.checks)

    @property
    def label(self) -> str:
        if self.loading:
            return "Loading…"
        if self.score >= 3:
            return self.hi
        if self.score <= 1:
            return self.lo
        return self.mid

    @property
    def color(self) -> str:
        if self.loading:
            return "#8a8a8a"
        if self.score >= 3:
            return "#1e9e4a"
        if self.score <= 1:
            return "#d64545"
        return "#e0a83c"


def _last(s: pd.Series) -> float | None:
    s = s.dropna()
    return None if s.empty else float(s.iloc[-1])


def _ago(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    return None if len(s) <= n else float(s.iloc[-1 - n])


def _cmp(a: float | None, b: float | None, op: str) -> bool | None:
    if a is None or b is None:
        return None
    return a > b if op == ">" else a < b


def compute_signals(f: dict[str, pd.Series]) -> list[Signal]:
    g = lambda k: f.get(k, pd.Series(dtype=float))

    growth = Signal("Growth", [
        Check("Payrolls above year-ago level",
              _cmp(_last(g("PAYEMS")), _ago(g("PAYEMS"), 12), ">")),
        Check("Industrial production above year-ago",
              _cmp(_last(g("INDPRO")), _ago(g("INDPRO"), 12), ">")),
        Check("Retail sales above year-ago",
              _cmp(_last(g("RSAFS")), _ago(g("RSAFS"), 12), ">")),
        Check("Jobless claims below year-ago",
              _cmp(_last(g("ICSA")), _ago(g("ICSA"), 52), "<")),
    ], "Rising", "Slowing", "Mixed")

    def six_m_vs_yoy(s: pd.Series) -> bool | None:
        latest, m6, m12 = _last(s), _ago(s, 6), _ago(s, 12)
        if None in (latest, m6, m12):
            return None
        return (latest / m6) ** 2 - 1 > latest / m12 - 1

    inflation = Signal("Inflation", [
        Check("CPI 6m-annualized above its YoY pace", six_m_vs_yoy(g("CPIAUCSL"))),
        Check("Core PCE 6m-annualized above its YoY pace", six_m_vs_yoy(g("PCEPILFE"))),
        Check("5Y breakeven above 3 months ago",
              _cmp(_last(g("T5YIE")), _ago(g("T5YIE"), 63), ">")),
        Check("10Y breakeven above 3 months ago",
              _cmp(_last(g("T10YIE")), _ago(g("T10YIE"), 63), ">")),
    ], "Heating Up", "Cooling", "Mixed")

    ff_now, ff_3m, ff_1y = (_last(g("DFEDTARU")), _ago(g("DFEDTARU"), 63),
                            _ago(g("DFEDTARU"), 260))
    be10 = _last(g("T10YIE"))
    real_ok = None if None in (ff_now, be10) else (ff_now - be10) < 1

    policy = Signal("Policy", [
        Check("Fed funds below year-ago (easing cycle)", _cmp(ff_now, ff_1y, "<")),
        Check("No hikes over past 3 months",
              None if None in (ff_now, ff_3m) else ff_now <= ff_3m),
        Check("Yield curve positive (10Y − 2Y > 0)",
              _cmp(_last(g("T10Y2Y")), 0.0, ">")),
        Check("Policy rate < 1pt above 10Y breakeven", real_ok),
    ], "Loose / Easing", "Tight", "Neutral")

    liquidity = Signal("Liquidity", [
        Check("Fed balance sheet growing (vs 3 months ago)",
              _cmp(_last(g("WALCL")), _ago(g("WALCL"), 13), ">")),
        Check("TGA falling — adds liquidity (vs 3 months ago)",
              _cmp(_last(g("WTREGEN")), _ago(g("WTREGEN"), 13), "<")),
        Check("ON RRP falling — adds liquidity (vs 3 months ago)",
              _cmp(_last(g("RRPONTSYD")), _ago(g("RRPONTSYD"), 63), "<")),
        Check("NFCI below 0 (conditions looser than average)",
              _cmp(_last(g("NFCI")), 0.0, "<")),
    ], "Ample / Loosening", "Tight / Draining", "Neutral")

    return [growth, inflation, policy, liquidity]
