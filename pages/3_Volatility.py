"""Volatility Dashboard — Book III, Ch. 6: the observable vol complex."""
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Volatility — Desk", page_icon="🌪️", layout="wide")
theme.header("BOOK III · CH. 6", "Volatility Dashboard",
             "The observable, Tier 1 half of the options dashboard. Dealer "
             "positioning / GEX are inferred, paid data — deliberately absent.")

hist = data.market_history(period="2y")
if hist.empty:
    st.error("Market data unavailable — try again shortly.")
    st.stop()

cols = st.columns(5)
for col, (tkr, name) in zip(cols, [("^VIX", "VIX"), ("^VIX3M", "VIX 3M"),
                                   ("^VVIX", "VVIX"), ("^MOVE", "MOVE"),
                                   ("^SKEW", "SKEW")]):
    s = hist.get(tkr)
    if s is not None and not s.dropna().empty:
        s = s.dropna()
        chg = data.pct_chg(s)
        col.metric(name, f"{s.iloc[-1]:.2f}",
                   f"{chg:+.2f}%" if chg is not None else None,
                   delta_color="inverse")

theme.note("VIX = 30-day S&P insurance price (teens calm, 20s stressed, "
           "30+ panic) · VVIX = vol of vol · MOVE = the bond market's VIX — "
           "rates often lead equities · SKEW = crash-insurance premium. "
           "Deltas shown red when rising: rising vol is risk-off.")

st.divider()

# ---- term structure ratio: the tripwire ----
if "^VIX" in hist and "^VIX3M" in hist:
    ratio = (hist["^VIX"] / hist["^VIX3M"]).dropna()
    fig = go.Figure()
    fig.add_scatter(x=ratio.index, y=ratio.values, mode="lines",
                    name="VIX / VIX3M",
                    line=dict(width=1.8, color=theme.AMBER))
    fig.add_hline(y=1.0, line=dict(color=theme.RED, width=1.5, dash="dash"),
                  annotation_text="inversion — regime tripwire",
                  annotation_position="top left")
    st.plotly_chart(
        theme.style_fig(fig, "VIX / VIX3M term-structure ratio  (below 1 = "
                             "contango / calm · above 1 = inverted / stress)",
                        height=320),
        use_container_width=True)
    last = ratio.iloc[-1]
    st.markdown(f"**Current: {last:.2f}** — "
                + ("🟢 contango, near-term risk priced calm."
                   if last < 0.95 else
                   ("🟡 flattening — watch closely." if last < 1.0
                    else "🔴 **inverted** — the market is paying up for "
                         "near-term protection.")))
    theme.note("The regime tripwire. Normally near-term vol is cheaper than "
               "3-month vol (ratio below 1). A push above 1.0 means the "
               "market pays MORE for immediate protection — the signature "
               "of stress arriving, and where the standing alert lives.")

st.divider()

st.subheader("SPY implied-volatility skew (live from the options chain)")
st.markdown('<div class="desk-caption">IV by strike, expiration nearest 45 '
            'days. The upward slope to the left IS the skew — crash '
            'insurance priced richer than upside.</div>',
            unsafe_allow_html=True)
curve, expiry = data.spy_skew_curve()
if curve.empty:
    st.warning("Options chain unavailable right now (Yahoo rate-limits this "
               "endpoint). Try refresh in a minute.")
else:
    fig = go.Figure()
    for typ, color in [("put", theme.RED), ("call", theme.GREEN)]:
        d = curve[curve.type == typ].sort_values("moneyness")
        fig.add_scatter(x=d.moneyness, y=d.impliedVolatility * 100,
                        mode="markers", name=f"{typ}s",
                        marker=dict(size=5, color=color, opacity=0.65))
    fig.add_vline(x=100, line=dict(color=theme.MUTED, width=1, dash="dot"),
                  annotation_text="spot")
    fig.update_layout(xaxis_title="strike as % of spot",
                      yaxis_title="implied volatility (%)")
    st.plotly_chart(
        theme.style_fig(fig, f"SPY options — expiration {expiry}",
                        height=380, unified_hover=False),
        use_container_width=True)
    theme.note("Left side high = puts pricier than calls — the market pays "
               "up for downside. A steepening left wing = growing crash "
               "premium; a flattening one = complacency. This curve IS the "
               "SKEW index, in raw contract prices.")

st.divider()

st.subheader("SPY implied-volatility surface (term × strike)")
st.markdown('<div class="desk-caption">The skew above is one slice; the '
            'surface is all of them — IV across both strike and time. '
            'Built on demand: four chain calls against a rate-limited '
            'endpoint.</div>', unsafe_allow_html=True)
if st.button("Build surface — 4 chain calls"):
    st.session_state["iv_surface"] = True
if st.session_state.get("iv_surface"):
    surf, spot = data.spy_iv_surface()
    if surf.empty:
        st.warning("Chains unavailable (Yahoo rate limit) — try again "
                   "in a minute.")
    else:
        import numpy as np
        surf = surf.copy()
        surf["bin"] = (surf["moneyness"] / 2.5).round() * 2.5
        grid = (surf.groupby(["dte", "bin"])["impliedVolatility"]
                .mean().mul(100).unstack().sort_index())
        fig = go.Figure(go.Heatmap(
            z=grid.values, x=list(grid.columns),
            y=[f"{d}d" for d in grid.index],
            colorscale=[[0, "#0D0D0D"], [0.5, "#B45F1B"],
                        [1, "#FFD75E"]],
            colorbar=dict(title="IV %", tickfont=dict(size=10))))
        fig.update_layout(xaxis_title="strike as % of spot",
                          yaxis_title="days to expiry")
        st.plotly_chart(theme.style_fig(fig, "IV SURFACE — OTM PUTS "
                                             "LEFT, OTM CALLS RIGHT",
                                        height=340,
                                        unified_hover=False),
                        use_container_width=True)
        atm = (surf[(surf.moneyness > 97.5) & (surf.moneyness < 102.5)]
               .groupby("dte")["impliedVolatility"].mean().mul(100)
               .sort_index())
        if len(atm) > 1:
            fig = go.Figure(go.Scatter(
                x=[f"{d}d" for d in atm.index], y=atm.values,
                mode="lines+markers",
                line=dict(width=1.8, color=theme.AMBER)))
            st.plotly_chart(theme.style_fig(fig, "ATM TERM STRUCTURE "
                                                 "(IV %)", height=240),
                            use_container_width=True)
        theme.note("Read it in two directions. Left-to-right at any row "
                   "= the skew (bright left wing = crash premium). "
                   "Bottom-to-top at any column = the term structure — "
                   "normally brighter with time (contango); a bright "
                   "SHORT-dated row means near-term event risk is "
                   "priced, the surface's version of the VIX/VIX3M "
                   "tripwire. A lone bright cell at one expiry = a "
                   "known date (CPI, FOMC) wearing its price.")

st.divider()

st.subheader("The complex over time")
SERIES_NOTES = {
    "^VIX": "Mean-reverting by construction: it spends years in the teens "
            "and days in the 40s. Spikes mark fear extremes — often better "
            "contrarian markers than trend signals.",
    "^VVIX": "The price of options ON the VIX. Above ~110 = hedgers paying "
             "up for volatility convexity even if VIX itself looks calm — "
             "an early-nerves gauge.",
    "^MOVE": "Treasury volatility. When MOVE spikes while VIX sleeps, the "
             "bond market sees something equities don't — check the event "
             "calendar (CPI, FOMC, auctions) first, regime second.",
    "^SKEW": "Demand for deep out-of-the-money puts, ~110–150 range. High "
             "readings = tail insurance persistently bid. Poor timing tool, "
             "good context tool — read it alongside VIX and PCC, never "
             "alone.",
}
pick = st.selectbox("Series", ["^VIX", "^VVIX", "^MOVE", "^SKEW"],
                    format_func=lambda t: data.MARKET_TICKERS[t])
series_ohlc = data.ohlc(pick, period="2y")
fig = go.Figure()
if not series_ohlc.empty and series_ohlc["Open"].notna().sum() > 50:
    fig.add_trace(theme.candles(series_ohlc, data.MARKET_TICKERS[pick]))
    fig.update_layout(xaxis_rangeslider_visible=False)
    height = 360
else:
    s = hist[pick].dropna()
    fig.add_scatter(x=s.index, y=s.values, mode="lines",
                    line=dict(width=1.6, color=theme.BLUE))
    height = 300
st.plotly_chart(theme.style_fig(fig, height=height, unified_hover=False),
                use_container_width=True)
theme.note(SERIES_NOTES[pick])
