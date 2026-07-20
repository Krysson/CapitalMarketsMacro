"""Macro Dashboard — Book III, Ch. 4: Growth / Inflation / Policy / Liquidity."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Macro — Desk", page_icon="📊", layout="wide")
theme.header("BOOK III · CH. 4", "Macro Dashboard",
             "All Tier 1, primary-source data via FRED. Read top to bottom: "
             "Growth → Inflation → Policy → Liquidity. Gray bands = NBER "
             "recessions (USREC).")

bundle = data.macro_bundle()
rec = data.usrec()
years = st.slider("Lookback (years)", 1, 20, 5)

NOTES = {
    "PAYEMS": "Above 0 = the economy is adding jobs vs a year ago. A rollover "
              "toward 0 has preceded every modern recession — slope matters "
              "more than level.",
    "INDPRO": "Factory output. Below 0 = industrial recession; goods lead "
              "services into and out of downturns.",
    "RSAFS": "The consumer's pulse — but nominal. Compare against CPI YoY: "
             "spending growth below inflation = real spending is shrinking.",
    "ICSA": "The fastest recession canary on the desk (weekly). Rising claims "
            "= labor market cracking; sustained moves matter, single prints "
            "don't.",
    "CPIAUCSL": "Headline inflation — energy and food swing it. The Fed's "
                "2% target is on PCE, not this, but markets react to this "
                "first.",
    "PCEPILFE": "The Fed's preferred gauge. This series, not CPI, is what "
                "actually moves policy. Sticky above 2% = no easy cuts.",
    "T5YIE": "The market's own 5-year inflation forecast. Rising = the bond "
             "market doubts inflation is beaten; it repriced before CPI did "
             "in 2021.",
    "T10YIE": "Long-run expectations. Anchored near 2–2.5% = Fed credibility "
              "intact; a break above 3% would be a regime event.",
    "DFEDTARU": "The price of money. Direction and pace matter more than "
                "level — markets trade the path, not the number.",
    "SOFR": "Where overnight money actually clears against Treasury "
            "collateral. Spikes above the target range = funding stress "
            "(the Sept 2019 repo episode). Quarter-end blips = plumbing "
            "noise.",
    "T10Y2Y": "Below 0 = inverted curve, the classic recession warning. The "
              "rapid re-steepening after inversion is historically the more "
              "dangerous phase, not the inversion itself.",
    "WALCL": "QE / QT in one line. Above 0 = the Fed's balance sheet is "
             "expanding — an asset-price tailwind; below 0 = drain.",
    "RRPONTSYD": "Cash parked overnight at the Fed. Falling = money leaving "
                 "the parking lot into markets (adds liquidity). Near zero = "
                 "that buffer is spent — future drains hit reserves directly.",
    "WTREGEN": "The Treasury's checking account. When TGA rises (tax days, "
               "debt-ceiling rebuilds) it pulls cash from markets; falling "
               "TGA adds it back.",
    "NFCI": "Chicago Fed composite of 105 indicators. Below 0 = conditions "
            "looser than average; a fast rise through 0 = a tightening "
            "squeeze underway.",
}


def line(sid, series, title, yoy=False, color=theme.BLUE):
    s = series.dropna() if series is not None else pd.Series(dtype=float)
    if s.empty:
        st.warning(f"{title}: no data")
        return
    if yoy:
        s = data.yoy_pct(s)
        title += " (YoY %)"
    s = data.tail_years(s, years)
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                               line=dict(width=1.8, color=color)))
    theme.recession_bands(fig, rec, start=s.index.min(), end=s.index.max())
    theme.plot(theme.style_fig(fig, title, height=260),
                    use_container_width=True)
    if sid in NOTES:
        theme.note(NOTES[sid])


nl = data.net_liquidity(bundle)
if not nl.empty:
    s = data.tail_years(nl, years) / 1_000_000
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                               line=dict(width=2.2, color=theme.AMBER)))
    theme.recession_bands(fig, rec, start=s.index.min(), end=s.index.max())
    theme.plot(
        theme.style_fig(fig, "Net Liquidity = Fed Balance Sheet − TGA − "
                             "ON RRP  ($tn)", height=320),
        use_container_width=True)
    theme.note("The book's rule of thumb for cash actually available to "
               "markets. Rising = tailwind for risk assets · Falling = "
               "drain. Direction over weeks matters; daily wiggles are "
               "plumbing.")

yoy_ids = {"PAYEMS", "INDPRO", "RSAFS", "CPIAUCSL", "PCEPILFE", "WALCL"}
for panel, series_list in data.MACRO_SERIES.items():
    st.subheader(panel.title())
    cols = st.columns(2)
    for i, (sid, name, units) in enumerate(series_list):
        with cols[i % 2]:
            line(sid, bundle.get(sid), f"{name} ({units})",
                 yoy=sid in yoy_ids)
