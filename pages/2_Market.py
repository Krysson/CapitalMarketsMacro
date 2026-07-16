"""Market Dashboard — Book III, Ch. 5: trend, participation, cross-asset."""
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Market — Desk", page_icon="📈", layout="wide")
theme.header("BOOK III · CH. 5", "Market Dashboard",
             "Trend, participation, and cross-asset confirmation.")

period = st.selectbox("Lookback", ["6mo", "1y", "2y", "5y"], index=1)
hist = data.market_history(period=period)

if hist.empty:
    st.error("Market data unavailable — Yahoo Finance may be rate-limiting. "
             "Try again in a minute.")
    st.stop()

# ---- Trend: SPX candlesticks with the MA ribbon ----
spx_ohlc = data.ohlc("^GSPC", period=period)
spx = hist["^GSPC"].dropna()
fig = go.Figure()
if not spx_ohlc.empty:
    fig.add_trace(theme.candles(spx_ohlc, "S&P 500"))
else:
    fig.add_scatter(x=spx.index, y=spx.values, mode="lines", name="S&P 500",
                    line=dict(width=2, color=theme.TEXT))
for win, color in [(20, theme.GREEN), (50, theme.BLUE), (200, theme.RED)]:
    ma = spx.rolling(win).mean()
    fig.add_scatter(x=ma.index, y=ma.values, mode="lines", name=f"SMA {win}",
                    line=dict(width=1.1, color=color))
fig.update_layout(xaxis_rangeslider_visible=False)
st.plotly_chart(
    theme.style_fig(fig, "S&P 500 — trend vs 20 / 50 / 200-day",
                    height=420, unified_hover=False),
    use_container_width=True)

above200 = spx.iloc[-1] > spx.rolling(200).mean().iloc[-1]
st.markdown(f"**Trend check:** price is currently "
            f"{'**above** ✅' if above200 else '**below** ❌'} the 200-day.")
theme.note("Price above a rising 200-day = uptrend regime; below = defense. "
           "Ribbon order (20 over 50 over 200) and slope show trend health; "
           "long candle wicks show sessions where conviction failed.")

st.divider()


def ratio_chart(num, den, title, note):
    if num not in hist or den not in hist:
        st.warning(f"{title}: data missing")
        return
    r = (hist[num] / hist[den]).dropna()
    ma50 = r.rolling(50).mean()
    fig = go.Figure()
    fig.add_scatter(x=r.index, y=r.values, mode="lines", name="ratio",
                    line=dict(width=1.8, color=theme.PURPLE))
    fig.add_scatter(x=ma50.index, y=ma50.values, mode="lines", name="50d MA",
                    line=dict(width=1, color=theme.MUTED, dash="dot"))
    st.plotly_chart(theme.style_fig(fig, title, height=290),
                    use_container_width=True)
    theme.note(note)


c1, c2 = st.columns(2)
with c1:
    ratio_chart("RSP", "SPY", "RSP / SPY — equal weight vs cap weight",
                "Rising = broad participation · Falling = narrow leadership. "
                "Breadth proxy; full internals (S5TH, ADD) live on TradingView.")
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
    palette = [theme.TEXT, theme.AMBER, theme.BLUE, theme.GREEN,
               theme.PURPLE, theme.RED, theme.MUTED]
    for i, t in enumerate(sel):
        s = hist[t].dropna()
        if len(s) > 1:
            fig.add_scatter(x=s.index, y=(s / s.iloc[0] - 1) * 100,
                            mode="lines", name=data.MARKET_TICKERS[t],
                            line=dict(width=1.6,
                                      color=palette[i % len(palette)]))
    fig.update_layout(yaxis_title="% change over lookback")
    st.plotly_chart(theme.style_fig(fig, height=380),
                    use_container_width=True)
    theme.note("Confirmation check: does the rest of the world agree with "
               "equities? Stocks rising alone — while copper, credit, and "
               "crypto sag — is a divergence worth a Notebook entry. Broad "
               "agreement = regime confirmation.")
