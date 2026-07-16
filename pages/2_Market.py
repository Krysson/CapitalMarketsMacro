"""Market Dashboard — Book III, Ch. 5: trend, participation, cross-asset."""
import plotly.graph_objects as go
import streamlit as st

from desk import data

st.set_page_config(page_title="Market — Desk", page_icon="📈", layout="wide")
st.title("Market Dashboard")

period = st.selectbox("Lookback", ["6mo", "1y", "2y", "5y"], index=1)
hist = data.market_history(period=period)

if hist.empty:
    st.error("Market data unavailable — Yahoo Finance may be rate-limiting. "
             "Try again in a minute.")
    st.stop()


def ratio_chart(num, den, title, note):
    if num not in hist or den not in hist:
        st.warning(f"{title}: data missing")
        return
    r = (hist[num] / hist[den]).dropna()
    ma50 = r.rolling(50).mean()
    fig = go.Figure()
    fig.add_scatter(x=r.index, y=r.values, mode="lines", name=title,
                    line=dict(width=1.8, color="#8a4abd"))
    fig.add_scatter(x=ma50.index, y=ma50.values, mode="lines", name="50d MA",
                    line=dict(width=1, color="#999", dash="dot"))
    fig.update_layout(title=title, height=280,
                      margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(note)


# ---- Trend: SPX with the MA ribbon ----
spx = hist["^GSPC"].dropna()
fig = go.Figure()
fig.add_scatter(x=spx.index, y=spx.values, mode="lines", name="S&P 500",
                line=dict(width=2, color="#e8e8e8"))
for win, color in [(20, "#1e9e4a"), (50, "#4a7dbd"), (200, "#d64545")]:
    ma = spx.rolling(win).mean()
    fig.add_scatter(x=ma.index, y=ma.values, mode="lines", name=f"SMA {win}",
                    line=dict(width=1.1, color=color))
fig.update_layout(title="S&P 500 — trend vs 20/50/200-day", height=380,
                  margin=dict(l=10, r=10, t=40, b=10),
                  legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig, use_container_width=True)

above200 = spx.iloc[-1] > spx.rolling(200).mean().iloc[-1]
st.markdown(f"**Trend check:** price is currently "
            f"{'**above** ✅' if above200 else '**below** ❌'} the 200-day.")

st.divider()
c1, c2 = st.columns(2)
with c1:
    ratio_chart("RSP", "SPY", "RSP / SPY — equal weight vs cap weight",
                "Rising = broad participation. Falling = narrow leadership. "
                "This is the breadth proxy; TradingView still carries the "
                "full internals (S5TH, ADD).")
with c2:
    ratio_chart("HYG", "LQD", "HYG / LQD — credit risk appetite",
                "Falling = high yield underperforming investment grade — "
                "credit smelling trouble before equities admit it.")

st.divider()
st.subheader("Cross-asset (normalized)")
sel = st.multiselect(
    "Compare", options=list(data.MARKET_TICKERS.keys()),
    default=["^GSPC", "GC=F", "CL=F", "DX-Y.NYB", "BTC-USD"],
    format_func=lambda t: data.MARKET_TICKERS[t])
if sel:
    fig = go.Figure()
    for t in sel:
        s = hist[t].dropna()
        if len(s) > 1:
            fig.add_scatter(x=s.index, y=(s / s.iloc[0] - 1) * 100,
                            mode="lines", name=data.MARKET_TICKERS[t],
                            line=dict(width=1.6))
    fig.update_layout(height=380, yaxis_title="% change over lookback",
                      margin=dict(l=10, r=10, t=20, b=10),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
