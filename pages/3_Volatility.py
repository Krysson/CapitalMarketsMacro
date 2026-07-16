"""Volatility Dashboard — Book III, Ch. 6: the observable vol complex."""
import plotly.graph_objects as go
import streamlit as st

from desk import data

st.set_page_config(page_title="Volatility — Desk", page_icon="🌪️", layout="wide")
st.title("Volatility Dashboard")
st.caption("The observable, Tier 1 half of the options dashboard. Dealer "
           "positioning / GEX are inferred, paid data — deliberately absent.")

hist = data.market_history(period="2y")
if hist.empty:
    st.error("Market data unavailable — try again shortly.")
    st.stop()

# ---- headline metrics ----
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

st.divider()

# ---- term structure ratio: the tripwire ----
if "^VIX" in hist and "^VIX3M" in hist:
    ratio = (hist["^VIX"] / hist["^VIX3M"]).dropna()
    fig = go.Figure()
    fig.add_scatter(x=ratio.index, y=ratio.values, mode="lines",
                    name="VIX / VIX3M", line=dict(width=1.8, color="#e0a83c"))
    fig.add_hline(y=1.0, line=dict(color="#d64545", width=1.5, dash="dash"),
                  annotation_text="inversion — regime tripwire",
                  annotation_position="top left")
    fig.update_layout(title="VIX / VIX3M term structure ratio "
                            "(below 1 = contango/calm, above 1 = inverted/stress)",
                      height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)
    last = ratio.iloc[-1]
    st.markdown(f"**Current: {last:.2f}** — "
                + ("🟢 contango, near-term risk priced calm."
                   if last < 0.95 else
                   ("🟡 flattening — watch closely." if last < 1.0
                    else "🔴 **inverted** — the market is paying up for "
                         "near-term protection.")))

st.divider()

# ---- live skew curve ----
st.subheader("SPY implied-volatility skew (live from the options chain)")
st.caption("IV by strike for the expiration nearest 45 days out. The upward "
           "slope to the left IS the skew — crash insurance priced richer "
           "than upside. This is the SKEW index, seen in raw contract prices.")
curve, expiry = data.spy_skew_curve()
if curve.empty:
    st.warning("Options chain unavailable right now (Yahoo rate limits this "
               "endpoint aggressively). Try refresh in a minute.")
else:
    fig = go.Figure()
    for typ, color in [("put", "#d64545"), ("call", "#1e9e4a")]:
        d = curve[curve.type == typ].sort_values("moneyness")
        fig.add_scatter(x=d.moneyness, y=d.impliedVolatility * 100,
                        mode="markers", name=f"{typ}s",
                        marker=dict(size=5, color=color, opacity=0.6))
    fig.add_vline(x=100, line=dict(color="#888", width=1, dash="dot"),
                  annotation_text="spot")
    fig.update_layout(title=f"SPY options — expiration {expiry}",
                      xaxis_title="strike as % of spot",
                      yaxis_title="implied volatility (%)",
                      height=380, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- history of the complex ----
st.subheader("The complex over time")
pick = st.selectbox("Series", ["^VIX", "^VVIX", "^MOVE", "^SKEW"],
                    format_func=lambda t: data.MARKET_TICKERS[t])
s = hist[pick].dropna()
fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                           line=dict(width=1.6, color="#4a7dbd")))
fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10))
st.plotly_chart(fig, use_container_width=True)
