"""Market Dashboard — Book III, Ch. 5: trend, participation, cross-asset."""
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Market — Desk", page_icon="▪", layout="wide")
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
theme.plot(theme.style_fig(
    fig, "S&P 500 — trend vs 20 / 50 / 200-day",
    height=300, unified_hover=False,
    right_text=(f"{float(spx.iloc[-1]):,.2f}  "
                f"{(float(spx.iloc[-1]) / float(spx.iloc[-2]) - 1) * 100:+.2f}%"
                "  · delayed"),
    right_color=(theme.GREEN if spx.iloc[-1] >= spx.iloc[-2]
                 else theme.RED)),
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

st.divider()
st.subheader("Cross-asset (normalized)")
sel = st.multiselect(
    "Compare", options=list(data.MARKET_TICKERS.keys()),
    default=["^GSPC", "GC=F", "CL=F", "DX-Y.NYB", "IWM"],
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
# The two pieces of glass belong side by side — the heatmap is the
# cross-section, the live chart is the time series of the same object.
theme.panel_bar("The glass — TradingView (display only)",
                "heatmap + live SPX, adjacent by design")
# HOUSE RULE: Live SPX is ALWAYS the first (default) tab — do not
# reorder. (Reverted once by a build from a stale local copy.)
tab_spx, tab_hm = st.tabs(["Live SPX", "S&P 500 heatmap"])
with tab_hm:
    theme.embed(
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
with tab_spx:
    theme.embed(
        """
        <div class="tradingview-widget-container">
          <div id="tv_spx"></div>
          <script src="https://s3.tradingview.com/tv.js"></script>
          <script>
          new TradingView.widget({
            "container_id": "tv_spx",
            "symbol": "SPX500USD",
          "studies": ["STD;MA%1Ribbon"],
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

# --------------------------------------------- breadth internals (v4.4)
st.divider()
from desk import breadth as _breadth

theme.panel_bar("BREADTH INTERNALS — S&P 500 MEMBERS",
                "computed nightly by the bot · S&P-scoped, not NYSE")
_bf = _breadth.load()
if _bf.empty:
    st.markdown('<div class="desk-note">No breadth record yet — the '
                'nightly bot computes member internals and backfills '
                'a full year on its FIRST successful run (the batch '
                'download endpoint is the one Yahoo doesn\'t block '
                'from runners). Check tomorrow.</div>',
                unsafe_allow_html=True)
else:
    _spx = hist.get("^GSPC", pd.Series(dtype=float)).dropna()
    b1, b2 = st.columns(2)
    with b1:
        figb = go.Figure()
        figb.add_scatter(x=_bf.index, y=_bf["pct_above_200d"],
                         mode="lines", name="% > 200d",
                         line=dict(width=1.8, color=theme.AMBER))
        figb.add_scatter(x=_bf.index, y=_bf["pct_above_50d"],
                         mode="lines", name="% > 50d",
                         line=dict(width=1.2, color=theme.BLUE))
        theme.plot(theme.style_fig(
            figb, "% OF MEMBERS ABOVE 200D / 50D", height=300,
            right_text=f"{_bf['pct_above_200d'].iloc[-1]:.0f}% · "
                       f"{_bf['pct_above_50d'].iloc[-1]:.0f}%",
            right_color=theme.AMBER), use_container_width=True)
        theme.note("Under 50% above the 200-day while the index sits "
                   "near highs = a market carried by few — the "
                   "generals-without-soldiers pattern. [T2 computed]")
        fign = go.Figure(go.Bar(x=_bf.index, y=_bf["nh_nl"],
                                marker_color=[theme.GREEN if v >= 0
                                              else theme.RED
                                              for v in _bf["nh_nl"]]))
        theme.plot(theme.style_fig(
            fign, "NEW 52W HIGHS − NEW LOWS", height=240,
            right_text=f"{_bf['nh_nl'].iloc[-1]:+.0f}",
            right_color=theme.GREEN if _bf['nh_nl'].iloc[-1] >= 0
            else theme.RED), use_container_width=True)
    with b2:
        figa = go.Figure()
        figa.add_scatter(x=_bf.index, y=_bf["ad_line"], mode="lines",
                         name="Cumulative A/D",
                         line=dict(width=1.8, color=theme.BLUE))
        if not _spx.empty:
            sp = _spx.reindex(_bf.index).dropna()
            figa.add_scatter(x=sp.index, y=sp.values, mode="lines",
                             name="SPX", yaxis="y2",
                             line=dict(width=1.1, color=theme.MUTED))
            figa.update_layout(yaxis2=dict(overlaying="y", side="left",
                                           showgrid=False,
                                           showticklabels=False))
        theme.plot(theme.style_fig(
            figa, "CUMULATIVE ADVANCE-DECLINE vs SPX", height=300,
            right_text=f"{_bf['ad_line'].iloc[-1]:+.0f}",
            right_color=theme.BLUE), use_container_width=True)
        theme.note("THE confirmation chart: price at new highs while "
                   "the A/D line isn't = narrowing participation — "
                   "the desk's RSP/SPY read, member-counted. Same "
                   "index both lines, apples to apples. [T2]")
        try:
            _spdrs = [t for t in ("XLB", "XLC", "XLE", "XLF", "XLI",
                                  "XLK", "XLP", "XLRE", "XLU", "XLV",
                                  "XLY") if t in hist.columns]
            _above = sum(
                1 for t in _spdrs
                if hist[t].dropna().iloc[-1]
                > hist[t].dropna().rolling(200).mean().iloc[-1])
            theme.readout(
                theme.GREEN if _above >= 8 else
                theme.YELLOW if _above >= 5 else theme.RED,
                f"SECTOR PARTICIPATION: {_above}/{len(_spdrs)} SPDRs "
                f"above their own 200-day.")
        except Exception:
            pass
