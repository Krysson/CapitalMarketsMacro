"""Rates & Credit — the free window into fixed income. GC <GO>.

What's here is Tier 1: the full constant-maturity Treasury curve, the
classic recession spreads, the real/breakeven decomposition, and ICE
BofA option-adjusted credit spreads — all FRED. What's deliberately
absent: per-bond pricing, dealer runs, the tradeable universe. That's
the paid moat, and pretending otherwise would break the desk's rules.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Rates — Desk", page_icon="📉", layout="wide")
theme.header(
    "BOOK III · RATES & CREDIT",
    "Rates & Credit",
    "The curve, the spreads, and what credit is charging for risk — all "
    "Tier 1 via FRED. Per-bond pricing and dealer runs are paid data and "
    "deliberately absent; the tradeable free window is the ETF complex "
    "(SHY/IEF/TLT, HYG/LQD) on the Market page.")

curve = data.treasury_curve()
rec = data.usrec()
years = st.selectbox("History lookback (years)", [1, 2, 5, 10], index=2)

if curve.empty:
    st.error("FRED unavailable — try again shortly.")
    st.stop()

# ------------------------------------------------------- the curve ----
theme.panel_bar("US Treasury par yield curve",
                f"as of {curve.index[-1]:%d-%b-%Y}")
snaps = [("today", -1, theme.AMBER, 2.4),
         ("1 month ago", -22, theme.BLUE, 1.4),
         ("1 year ago", -252, theme.MUTED, 1.2)]
fig = go.Figure()
for label, pos, color, width in snaps:
    if len(curve) >= abs(pos):
        row = curve.iloc[pos].dropna()
        fig.add_scatter(x=list(row.index), y=row.values,
                        mode="lines+markers", name=label,
                        line=dict(width=width, color=color),
                        marker=dict(size=5))
theme.plot(theme.style_fig(fig, None, height=340),
                use_container_width=True)
theme.note("The price of money at every maturity, and how it moved. "
           "Shape is the message: upward-sloping = normal; humped or "
           "inverted = the market pricing cuts ahead; the whole curve "
           "shifting up = term premium or inflation fear, not just Fed "
           "policy. Watch the 1-month ghost — the curve's recent motion "
           "tells you what repriced.")

# ------------------------------------------------ recession spreads ----
def spread(a: str, b: str) -> pd.Series:
    if a in curve and b in curve:
        return (curve[a] - curve[b]).dropna()
    return pd.Series(dtype=float)

s_2s10s, s_3m10y, s_5s30s = (spread("10Y", "2Y"), spread("10Y", "3M"),
                             spread("30Y", "5Y"))
m1, m2, m3 = st.columns(3)
for col, name, s in ((m1, "2s10s", s_2s10s), (m2, "3m10y", s_3m10y),
                     (m3, "5s30s", s_5s30s)):
    if not s.empty:
        v = float(s.iloc[-1])
        col.metric(name, f"{v:+.2f}pp",
                   "inverted" if v < 0 else "positive",
                   delta_color="inverse" if v < 0 else "normal")

fig = go.Figure()
for name, s, color in (("2s10s", s_2s10s, theme.AMBER),
                       ("3m10y", s_3m10y, theme.BLUE)):
    tail = data.tail_years(s, years)
    if not tail.empty:
        fig.add_scatter(x=tail.index, y=tail.values, mode="lines",
                        name=name, line=dict(width=1.6, color=color))
fig.add_hline(y=0, line=dict(color=theme.RED, width=1, dash="dash"))
if not s_2s10s.empty:
    tail = data.tail_years(s_2s10s, years)
    theme.recession_bands(fig, rec, start=tail.index.min(),
                          end=tail.index.max())
theme.plot(theme.style_fig(fig, "CURVE SPREADS (pp)", height=300),
                use_container_width=True)
theme.note("The classic recession machinery. 3m10y is the academic "
           "favorite (the Fed's own recession-probability input); 2s10s "
           "is the market's shorthand. Inversion is the warning; the "
           "violent RE-steepening afterward — short rates collapsing as "
           "cuts get priced — is historically the dangerous phase.")

st.divider()

# ------------------------------------- nominal = real + breakeven ----
nom = curve.get("10Y", pd.Series(dtype=float))
real = data.fred_series("DFII10", start="2015-01-01")
be = data.fred_series("T10YIE", start="2015-01-01")
if not nom.empty and not real.empty:
    fig = go.Figure()
    for name, s, color in (("10Y nominal", nom, theme.TEXT),
                           ("10Y real (TIPS)", real, theme.BLUE),
                           ("10Y breakeven", be, theme.AMBER)):
        tail = data.tail_years(s.dropna(), years)
        fig.add_scatter(x=tail.index, y=tail.values, mode="lines",
                        name=name, line=dict(width=1.5, color=color))
    theme.plot(
        theme.style_fig(fig, "10Y DECOMPOSITION — NOMINAL = REAL + "
                             "BREAKEVEN (%)", height=300),
        use_container_width=True)
    theme.note("Which component is moving is the whole story. Yields up "
               "on RISING BREAKEVENS = inflation fear (bad for bonds AND "
               "stocks). Yields up on RISING REAL RATES = tightening "
               "financial conditions (the 2022 signature — gravity for "
               "every asset). Same nominal move, opposite regimes.")

st.divider()

# --------------------------------------------------------- credit ----
theme.panel_bar("Credit — ICE BofA option-adjusted spreads", "Tier 1")
hy = data.fred_series("BAMLH0A0HYM2", start="2010-01-01")
ig = data.fred_series("BAMLC0A0CM", start="2010-01-01")
if hy.empty and ig.empty:
    st.warning("Credit spread series unavailable — try again shortly.")
else:
    fig = go.Figure()
    for name, s, color in (("High Yield OAS", hy, theme.RED),
                           ("Investment Grade OAS", ig, theme.BLUE)):
        tail = data.tail_years(s.dropna(), years)
        if not tail.empty:
            fig.add_scatter(x=tail.index, y=tail.values, mode="lines",
                            name=name, line=dict(width=1.5, color=color))
    if not hy.empty:
        tail = data.tail_years(hy, years)
        theme.recession_bands(fig, rec, start=tail.index.min(),
                              end=tail.index.max())
    theme.plot(theme.style_fig(fig, "OAS OVER TREASURIES (%)",
                                    height=320),
                    use_container_width=True)
    theme.note("What the bond market charges for default risk, index-"
               "wide — the real thing, not a proxy. HY under ~3.5%% = "
               "priced for perfection; a fast widening while equities "
               "hold = credit smelling trouble first (it usually does). "
               "This is the fundamentals view; HYG/LQD on the Market "
               "page is the same idea in tradeable-price form — when "
               "they disagree, that's a Notebook entry.")

    if not hy.empty and not ig.empty:
        diff = (hy - ig).dropna()
        tail = data.tail_years(diff, years)
        fig = go.Figure(go.Scatter(x=tail.index, y=tail.values,
                                   mode="lines",
                                   line=dict(width=1.6,
                                             color=theme.PURPLE)))
        theme.plot(theme.style_fig(fig, "HY MINUS IG — THE JUNK "
                                             "PREMIUM (pp)", height=240),
                        use_container_width=True)
        theme.note("Compression = reach-for-yield, risk appetite high. "
                   "Rapid widening = flight to quality WITHIN credit — "
                   "often visible before the equity index reacts.")
