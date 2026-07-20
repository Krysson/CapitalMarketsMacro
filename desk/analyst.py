"""Desk Analyst — Claude wired to the live desk. ASK <GO>.

The analyst sees exactly what the trainee sees: a snapshot of every
computed reading on the desk, injected fresh into each exchange. Its
recommendation grammar is positioning language (long/short asset
classes, duration, vol, gamma, sector tilts) — never single names —
and every view must carry dashboard-tied reasoning plus falsification
conditions, in the book's voice.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

from desk import data, events, signals


def _try(fn, default=""):
    try:
        return fn()
    except Exception:
        return default


def desk_snapshot() -> str:
    """Every computed reading on the desk, as compact text. Each line is
    independently guarded — a dead feed drops its line, never the chat."""
    lines = [f"DESK SNAPSHOT — {dt.datetime.now(ZoneInfo('America/New_York')):%a %d %b %Y %H:%M} ET",
             "(free delayed data: FRED Tier 1, Yahoo Tier 2)"]

    def dials():
        bundle = data.macro_bundle()
        sigs = signals.compute_signals(bundle)
        out = ["MACRO DIALS: " + " | ".join(
            f"{s.category} {s.label} {s.score}/4" for s in sigs)]
        fails = [f"{s.category}: {c.label}" for s in sigs
                 for c in s.checks if c.passed is False]
        if fails:
            out.append("FAILING CHECKS: " + "; ".join(fails[:6]))
        p = data.print_lines(data.latest_prints(bundle))
        out.append(f"LATEST PRINTS: CPI {p['CPI']} | NFP {p['NFP']} | "
                   f"FOMC {p['FOMC']}")
        nl = data.net_liquidity(bundle)
        if not nl.empty:
            prior = nl.asof(nl.index[-1] - pd.DateOffset(weeks=13))
            if pd.notna(prior):
                out.append(f"NET LIQUIDITY: {float(nl.iloc[-1])/1e6:.2f}tn, "
                           f"{(float(nl.iloc[-1])-float(prior))/1e3:+,.0f}bn "
                           f"over 13w")
        return "\n".join(out)
    lines.append(_try(dials))

    def cal():
        return (f"CALENDAR: CPI {events.next_cpi().when} | "
                f"NFP {events.next_nfp().when} | "
                f"FOMC {events.next_fomc().when}")
    lines.append(_try(cal))

    def market():
        hist = data.market_history(period="6mo")
        out = []
        spx = hist["^GSPC"].dropna()
        ma200full = data.px_history("^GSPC").rolling(200).mean()
        if not spx.empty and not ma200full.empty:
            d = (spx.iloc[-1] / float(ma200full.iloc[-1]) - 1) * 100
            out.append(f"SPX {spx.iloc[-1]:,.0f} ({d:+.1f}% vs 200d)")
        for num, den, name in (("RSP", "SPY", "RSP/SPY breadth"),
                               ("HYG", "LQD", "HYG/LQD credit")):
            if num in hist and den in hist:
                r = (hist[num] / hist[den]).dropna()
                if len(r) > 21:
                    out.append(f"{name} {(r.iloc[-1]/r.iloc[-22]-1)*100:+.2f}%/1m")
        if "^VIX" in hist and "^VIX3M" in hist:
            r = (hist["^VIX"] / hist["^VIX3M"]).dropna()
            v = hist["^VIX"].dropna()
            if not r.empty:
                out.append(f"VIX {float(v.iloc[-1]):.1f}, VIX/VIX3M "
                           f"{float(r.iloc[-1]):.3f} "
                           f"({'INVERTED' if r.iloc[-1] >= 1 else 'contango'})")
        if "DX-Y.NYB" in hist:
            s = hist["DX-Y.NYB"].dropna()
            if len(s) > 21:
                out.append(f"DXY {float(s.iloc[-1]):,.1f} "
                           f"({(s.iloc[-1]/s.iloc[-22]-1)*100:+.1f}%/1m)")
        return "MARKET: " + " | ".join(out)
    lines.append(_try(market))

    def rates():
        curve = data.treasury_curve()
        out = []
        if not curve.empty:
            if "10Y" in curve and "2Y" in curve:
                s = (curve["10Y"] - curve["2Y"]).dropna()
                out.append(f"2s10s {float(s.iloc[-1]):+.2f}pp")
            if "10Y" in curve and "3M" in curve:
                s = (curve["10Y"] - curve["3M"]).dropna()
                out.append(f"3m10y {float(s.iloc[-1]):+.2f}pp")
            if "10Y" in curve:
                out.append(f"10Y {float(curve['10Y'].dropna().iloc[-1]):.2f}%")
        hy = data.fred_series("BAMLH0A0HYM2", start="2024-01-01")
        ig = data.fred_series("BAMLC0A0CM", start="2024-01-01")
        if not hy.empty:
            out.append(f"HY OAS {float(hy.iloc[-1]):.2f}%")
        if not ig.empty:
            out.append(f"IG OAS {float(ig.iloc[-1]):.2f}%")
        return "RATES/CREDIT: " + " | ".join(out)
    lines.append(_try(rates))

    def wires():
        items, _ = __import__("desk.wire", fromlist=["wire"]).fetch_tape(
            __import__("desk.wire", fromlist=["wire"]).PRIMARY_FEEDS)
        heads = [i["title"] for i in items[:3]]
        return "PRIMARY WIRE: " + " // ".join(heads) if heads else ""
    lines.append(_try(wires))

    return "\n".join(l for l in lines if l)


SYSTEM_PROMPT = """You are the Desk Analyst on the Capital Markets Desk — \
the free, terminal-styled training desk that accompanies a capital-markets \
book series. Your audience is trainee analysts learning how a real desk \
reasons in real time. You have the live desk snapshot below; treat its \
readings as [F] facts (delayed free data) and everything you infer from \
them as [I].

VOICE AND DISCIPLINE (the book's conventions — never break these):
- Terminal-concise. Short paragraphs. No filler, no hedging boilerplate.
- Evidence tags where useful: [F] fact, [E] estimate, [I] inference. Data \
reliability tiers: FRED = Tier 1, market prices = Tier 2, estimates = \
Tier 3, narrative/media = Tier 5. Never present Tier 5 as evidence.
- Colors/direction language describes direction, not good vs bad.
- Every analytical claim should be falsifiable — say what would prove it \
wrong and how fast you'd know.

POSITIONING RECOMMENDATIONS — the format when asked for a view (or when \
a "morning read" is requested):
1. POSITIONING: stated in desk grammar ONLY — e.g. "LONG EQUITIES / \
SHORT DURATION", "LONG VOL", "SHORT GAMMA", "LONG CREDIT (HY over IG)", \
"FLAT / HOLD", "LONG ENERGY vs SHORT TECH (sector tilt)". Conviction: \
low / moderate / high. Sectors and factors are allowed; INDIVIDUAL \
COMPANY NAMES ARE BANNED — if asked "should I buy [stock]", redirect to \
the sector/factor/asset-class expression of the same idea and say why \
the desk works that way.
2. REASONING: tied to SPECIFIC snapshot readings by name and number. If \
the snapshot doesn't support a view, say so — "the desk doesn't show me \
enough to lean" is a respectable answer.
3. WHAT KILLS IT: explicit falsification conditions using the desk's own \
tripwires (VIX/VIX3M 1.0, HYG/LQD rollover, breadth, 2s10s, OAS, net \
liquidity direction).
4. RISKS: what the free desk cannot see (positioning detail, intraday \
flow, unscheduled events).
5. One closing line, always: "Training desk — direction, not advice."

NOTEBOOK ENTRIES: when asked to draft one, use the exact template — \
Evidence (tagged) / Interpretation / Risks / Falsification / Decision / \
Directional call (Risk-on, Risk-off, or No call) / Instrument — ready to \
paste into the NOTE page.

TEACHING: when explaining a chart or concept (vol surface, term \
structure, OAS, breadth, the curve, options greeks, fixed income \
mechanics), teach it the book's way: mechanism first, then how to read \
it on THIS desk, then the classic mistake trainees make with it.

You may discuss general finance, fixed income, and options theory \
freely. You are not anyone's fiduciary; sizing and personal suitability \
are out of scope by design."""


def build_messages(history: list[dict], snapshot: str) -> tuple[str, list]:
    """(system_prompt_with_snapshot, trimmed_history)."""
    system = SYSTEM_PROMPT + "\n\n" + snapshot
    return system, history[-12:]
