"""Market Dashboard — Book III, Ch. 5: trend, participation, cross-asset."""
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

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
theme.plot(
    theme.style_fig(fig, "S&P 500 — trend vs 20 / 50 / 200-day",
                    height=420, unified_hover=False),
    use_container_width=True)

ma200 = spx.rolling(200).mean().iloc[-1]
dist = (spx.iloc[-1] / ma200 - 1) * 100
theme.readout(
    theme.GREEN if dist >= 0 else theme.RED,
    f"SPX {spx.iloc[-1]:,.0f} — {abs(dist):.1f}% "
    f"{'ABOVE' if dist >= 0 else 'BELOW'} the 200-day ({ma200:,.0f}). "
    f"{'Uptrend regime.' if dist >= 0 else 'Defensive regime.'}")
theme.note("Price above a rising 200-day = uptrend regime; below = defense. "
           "Ribbon order (20 over 50 over 200) and slope show trend health; "
           "long candle wicks show sessions where conviction failed.")

st.divider()


def ratio_chart(num, den, title, note, up_txt, dn_txt):
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
    theme.plot(theme.style_fig(fig, title, height=290),
                    use_container_width=True)
    if len(r) > 21:
        d = (r.iloc[-1] / r.iloc[-22] - 1) * 100
        theme.readout(theme.GREEN if d > 0 else theme.AMBER,
                      f"{r.iloc[-1]:.4f} · {d:+.2f}% over ~1 month — "
                      + (up_txt if d > 0 else dn_txt))
    theme.note(note)


c1, c2 = st.columns(2)
with c1:
    ratio_chart("RSP", "SPY", "RSP / SPY — equal weight vs cap weight",
                "Rising = broad participation · Falling = narrow leadership. "
                "Breadth proxy; full internals (S5TH, ADD) live on TradingView.",
                "the average stock is keeping up. BROAD participation.",
                "cap-weight leading. NARROW leadership — the index is "
                "being carried, not lifted.")
with c2:
    ratio_chart("HYG", "LQD", "HYG / LQD — credit risk appetite",
                "Falling = high yield underperforming investment grade — "
                "credit smelling trouble before equities admit it.",
                "credit CONFIRMING risk appetite.",
                "credit DISSENTING — junk lagging quality.")

with st.expander("S&P 500 heatmap — TradingView (display glass)"):
    components.html(
        """
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js"
            async>
          {
            "dataSource": "SPX500",
            "exchanges": [],
            "grouping": "sector",
            "blockSize": "market_cap_basic",
            "blockColor": "change",
            "hasTopBar": false,
            "isDataSetEnabled": false,
            "isZoomEnabled": true,
            "hasSymbolTooltip": true,
            "colorTheme": "dark",
            "isTransparent": true,
            "locale": "en",
            "width": "100%",
            "height": 480
          }
          </script>
        </div>
        """,
        height=490)
    theme.note("The RSP/SPY ratio, drawn as a picture. Index green while "
               "the map is mostly red — a few giant blocks doing all the "
               "lifting — IS narrow leadership. Block size = market cap, "
               "so your eye weighs stocks exactly the way SPY does; RSP "
               "weighs every block equally.")

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
    theme.plot(theme.style_fig(fig, height=380),
                    use_container_width=True)
    theme.note("Confirmation check: does the rest of the world agree with "
               "equities? Stocks rising alone — while copper, credit, and "
               "crypto sag — is a divergence worth a Notebook entry. Broad "
               "agreement = regime confirmation.")


st.divider()
with st.expander("Live SPX — TradingView (display glass)"):
    components.html(
        """
        <div class="tradingview-widget-container">
          <div id="tv_spx"></div>
          <script src="https://s3.tradingview.com/tv.js"></script>
          <script>
          new TradingView.widget({
            "container_id": "tv_spx",
            "symbol": "FOREXCOM:SPXUSD",
            "interval": "D",
            "timezone": "America/New_York",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "hide_top_toolbar": false,
            "hide_legend": false,
            "allow_symbol_change": true,
            "width": "100%",
            "height": 500
          });
          </script>
        </div>
        """,
        height=510)
    theme.note("Official TradingView embed — live intraday glass, useful "
               "for watching a session unfold. Display only: every "
               "computed check on this desk still runs on FRED and Yahoo "
               "data, so a widget outage never touches the signals.")
