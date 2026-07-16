"""Macro Dashboard — Book III, Ch. 4: Growth / Inflation / Policy / Liquidity."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Macro — Desk", page_icon="📊", layout="wide")
theme.header("BOOK III · CH. 4", "Macro Dashboard",
             "All Tier 1, primary-source data via FRED. Read top to bottom: "
             "Growth → Inflation → Policy → Liquidity.")

bundle = data.macro_bundle()
years = st.slider("Lookback (years)", 1, 20, 5)


def tail_years(s: pd.Series, n: int) -> pd.Series:
    if s.empty:
        return s
    cutoff = s.index.max() - pd.Timedelta(days=int(n * 365.25))
    return s[s.index >= cutoff]


def line(series, title, yoy=False, color=theme.BLUE):
    s = series.dropna() if series is not None else pd.Series(dtype=float)
    if s.empty:
        st.warning(f"{title}: no data")
        return
    if yoy:
        m = s.resample("MS").last()
        s = ((m / m.shift(12) - 1) * 100).dropna()
        title += " (YoY %)"
    s = tail_years(s, years)
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                               line=dict(width=1.8, color=color)))
    st.plotly_chart(theme.style_fig(fig, title, height=260),
                    use_container_width=True)


nl = data.net_liquidity(bundle)
if not nl.empty:
    s = tail_years(nl, years) / 1_000_000
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                               line=dict(width=2.2, color=theme.AMBER)))
    st.plotly_chart(
        theme.style_fig(fig, "Net Liquidity = Fed Balance Sheet − TGA − "
                             "ON RRP  ($tn)", height=320),
        use_container_width=True)

yoy_ids = {"PAYEMS", "INDPRO", "RSAFS", "CPIAUCSL", "PCEPILFE", "WALCL"}
for panel, series_list in data.MACRO_SERIES.items():
    st.subheader(panel.title())
    cols = st.columns(2)
    for i, (sid, name, units) in enumerate(series_list):
        with cols[i % 2]:
            line(bundle.get(sid), f"{name} ({units})", yoy=sid in yoy_ids)
