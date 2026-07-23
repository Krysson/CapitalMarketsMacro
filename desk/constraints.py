"""The Constraint Map — WHO is forced to do WHAT, at WHAT level?

Ch. 15's G4 made into furniture. The best trades come from someone
else's forced flow, and forced flow has addresses: mechanical
strategies with published rules, mandates with hard limits, calendars
with blackout windows. This module computes the trigger levels the
desk CAN compute from its own data, estimates the ones it can only
approximate (and says so), and leaves the rest to the reader — which
is the point: the panel is a worked example of the question, not the
answer key.

Every row: ACTOR · FORCED TO · AT WHAT LEVEL (live) · WHERE WE ARE.
Status: green = slack, yellow = inside 3% / conditions building,
red = binding now.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from desk import theme


def _row(actor: str, forced: str, level: str, now: str,
         status: str, basis: str) -> dict:
    return {"actor": actor, "forced": forced, "level": level,
            "now": now, "status": status, "basis": basis}


def build(hist: pd.DataFrame) -> list[dict]:
    """Compute the map from the desk's market history. Pure-ish
    (reads only the frame). Rows degrade to '—' on missing data."""
    rows = []
    G, Y, R = theme.GREEN, theme.YELLOW, theme.RED

    spx = hist.get("^GSPC", pd.Series(dtype=float)).dropna() \
        if not hist.empty else pd.Series(dtype=float)

    # --- trend followers: the 200-day and 50-day lines -------------
    if len(spx) >= 200:
        px = float(spx.iloc[-1])
        ma200 = float(spx.rolling(200).mean().iloc[-1])
        d200 = (px / ma200 - 1) * 100
        rows.append(_row(
            "Trend followers (CTAs, slow models)",
            "cut longs, then flip short, on a sustained break",
            f"SPX 200-day: {ma200:,.0f}",
            f"{px:,.0f} ({d200:+.1f}%)",
            G if d200 > 3 else (Y if d200 > 0 else R),
            "computed"))
        ma50 = float(spx.rolling(50).mean().iloc[-1])
        d50 = (px / ma50 - 1) * 100
        rows.append(_row(
            "Fast trend models",
            "de-risk on loss of momentum",
            f"SPX 50-day: {ma50:,.0f}",
            f"{px:,.0f} ({d50:+.1f}%)",
            G if d50 > 1.5 else (Y if d50 > 0 else R),
            "computed"))

    # --- vol-target funds ------------------------------------------
    vix = hist.get("^VIX", pd.Series(dtype=float)).dropna() \
        if not hist.empty else pd.Series(dtype=float)
    v3m = hist.get("^VIX3M", pd.Series(dtype=float)).dropna() \
        if not hist.empty else pd.Series(dtype=float)
    if not vix.empty:
        v = float(vix.iloc[-1])
        ratio = (float(vix.iloc[-1]) / float(v3m.iloc[-1])
                 if not v3m.empty else None)
        rtxt = f" · VIX/VIX3M {ratio:.2f} vs 1.00" if ratio else ""
        rows.append(_row(
            "Vol-target / vol-control funds",
            "mechanically sell equity as realized vol rises",
            "VIX sustained > ~20 (heuristic) · ratio > 1.00",
            f"VIX {v:.1f}{rtxt}",
            R if (v > 25 or (ratio and ratio > 1)) else
            (Y if v > 18 else G),
            "computed vs estimated threshold"))

    # --- risk parity: correlation flip in a drawdown ---------------
    tlt = hist.get("TLT", pd.Series(dtype=float)).dropna() \
        if not hist.empty else pd.Series(dtype=float)
    if len(spx) > 25 and len(tlt) > 25:
        r_s = spx.pct_change().tail(20)
        r_b = tlt.pct_change().reindex(r_s.index)
        corr = float(r_s.corr(r_b))
        spx_20d = float(spx.iloc[-1] / spx.iloc[-21] - 1) * 100
        binding = corr > 0.2 and spx_20d < 0
        rows.append(_row(
            "Risk parity / 60-40 rebalancers",
            "de-gross when stocks and bonds fall TOGETHER",
            "20d stock-bond corr > 0 during an equity drawdown",
            f"corr {corr:+.2f} · SPX 20d {spx_20d:+.1f}%",
            R if binding else (Y if corr > 0.2 else G),
            "computed"))

    # --- corporate buybacks: the blackout calendar -----------------
    today = dt.date.today()
    m, d = today.month, today.day
    qtr_end_month = m if m in (3, 6, 9, 12) else None
    in_blackout = ((m in (3, 6, 9, 12) and d >= 15)
                   or (m in (1, 4, 7, 10) and d <= 24))
    rows.append(_row(
        "Corporate buyback desks",
        "STOP purchasing (blackout) — the market's largest single "
        "bid steps away",
        "~2 weeks before quarter-end until earnings (est.)",
        "IN BLACKOUT (est.)" if in_blackout else "window OPEN (est.)",
        Y if in_blackout else G,
        "calendar estimate"))

    # --- dealers / gamma -------------------------------------------
    rows.append(_row(
        "Options dealers (gamma)",
        "sell weakness / buy strength when SHORT gamma — "
        "amplifying moves instead of damping them",
        "the OI shelves on your SPY chain (read the walls)",
        "manual — read the chain on the Vol page",
        Y,
        "manual (G4 rewards actual reading)"))
    return rows


def render(hist: pd.DataFrame, compact: bool = False) -> None:
    """The panel, either page."""
    theme.panel_bar("THE CONSTRAINT MAP",
                    "who is forced to do what, at what level?")
    rows = build(hist)
    if not rows:
        st.warning("Market data unavailable — the map needs history.")
        return
    for r in rows:
        st.markdown(
            f'<div style="display:flex;gap:14px;padding:7px 10px;'
            f'border-left:3px solid {r["status"]};'
            f'background:rgba(232,230,225,0.03);margin-bottom:4px;'
            f'font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:0.78rem;align-items:baseline">'
            f'<span style="color:{theme.AMBER};min-width:230px">'
            f'{r["actor"]}</span>'
            f'<span style="color:{theme.TEXT};flex:1">'
            f'forced to {r["forced"]}</span>'
            f'<span style="color:{theme.MUTED}">{r["level"]}</span>'
            f'<span style="color:{r["status"]}">{r["now"]}</span>'
            f'</div>', unsafe_allow_html=True)
    if not compact:
        theme.note(
            "Ch. 15, G4: the best flows to trade against are the ones "
            "somebody HAS to do. Computed rows use live desk data; "
            "'estimated' rows are honest heuristics (vol-target "
            "thresholds and blackout windows aren't published — "
            "they're inferred, and being roughly right about a real "
            "constraint beats being precise about an imagined one). "
            "The dealer row stays manual on purpose: G4 rewards "
            "actual reading, and the walls move daily. Red = binding "
            "now; yellow = inside the trigger zone; the trade isn't "
            "'red = sell' — it's knowing WHOSE selling arrives if "
            "that level breaks, and standing where you're paid to "
            "take the other side.")
