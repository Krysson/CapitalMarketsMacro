"""Futures — the commodity board and the shape of the curve. CTM <GO>.

Front-month continuous contracts via Yahoo (delayed, Tier 2). The =F
tickers are chained front months: fine for direction and levels, but
long histories contain roll artifacts — never backtest on them. The
term-structure section quotes real individual contract months, which is
where the actual information lives (contango vs backwardation).
Note the mnemonic collision, resolved the desk's way: GC routes to
Rates (graph curves); gold the metal is GC=F, right here on the board.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Futures — Desk", page_icon="🌾",
                   layout="wide")
theme.header(
    "BOOK III · FUTURES",
    "Futures & Commodities",
    "Front-month board by complex, then the part that pays rent: term "
    "structure. Prices delayed (Yahoo, Tier 2) · direction, not advice.")

board = data.futures_board()
if board.empty:
    st.error("Futures data unavailable — Yahoo may be rate-limiting. "
             "Try again shortly.")
    st.stop()


def ret(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    if len(s) <= n:
        return None
    return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100


def ytd(s: pd.Series) -> float | None:
    s = s.dropna()
    if s.empty:
        return None
    yr = s[s.index.year == s.index[-1].year]
    if len(yr) < 2:
        return None
    return (yr.iloc[-1] / yr.iloc[0] - 1) * 100


rows = []
for complex_, contracts in data.FUTURES_COMPLEXES.items():
    for tkr, name in contracts:
        if tkr in board.columns:
            s = board[tkr].dropna()
            if s.empty:
                continue
            rows.append({"Complex": complex_, "Contract": name,
                         "Tkr": tkr, "Last": round(float(s.iloc[-1]), 2),
                         "1d %": ret(s, 1), "1m %": ret(s, 21),
                         "YTD %": ytd(s)})
df = pd.DataFrame(rows)
theme.panel_bar("Front-month board", f"{len(df)} contracts · delayed")
pct_cols = ["1d %", "1m %", "YTD %"]
st.dataframe(
    df.style.map(
        lambda v: f"color: {theme.GREEN if v > 0 else theme.RED}"
        if isinstance(v, float) else "", subset=pct_cols,
    ).format({"Last": "{:,.2f}", **{c: "{:+.2f}" for c in pct_cols}},
             na_rep="—"),
    hide_index=True, height=min(700, 40 + 36 * len(df)),
    use_container_width=True)
theme.note("Read complexes, not single names. Energy + copper rising "
           "together = real demand (growth confirmation for the Circuit); "
           "gold alone rising = a hedge bid, not an economy. Grains and "
           "softs are weather and policy first, macro second — respect "
           "the seasonality before reading a macro story into corn.")

st.divider()

# --------------------------------------------------------- detail ----
all_contracts = [(t, n) for grp in data.FUTURES_COMPLEXES.values()
                 for t, n in grp]
pick = st.selectbox("Contract detail", [t for t, _ in all_contracts],
                    format_func=lambda t: dict(all_contracts)[t])
ohlc = data.ohlc(pick, period="1y")
if not ohlc.empty:
    close = ohlc["Close"]
    fig = go.Figure()
    fig.add_trace(theme.candles(ohlc, pick))
    for win, colr in ((50, theme.BLUE), (200, theme.RED)):
        ma = close.rolling(win).mean()
        fig.add_scatter(x=ma.index, y=ma.values, mode="lines",
                        name=f"SMA {win}",
                        line=dict(width=1.1, color=colr))
    fig.update_layout(xaxis_rangeslider_visible=False)
    theme.plot(
        theme.style_fig(fig, f"{dict(all_contracts)[pick]} ({pick}) — "
                             f"1Y FRONT-MONTH", height=380,
                        unified_hover=False),
        use_container_width=True)
    theme.note("Continuous front-month: the chained series rolls from "
               "contract to contract, so long-run levels carry roll "
               "artifacts. Trust the shape and the trend; don't compute "
               "multi-year returns off this line.")
else:
    st.warning("Chart unavailable for this contract right now.")

st.divider()

# --------------------------------------------------- term structure ----
theme.panel_bar("Term structure", "real contract months, quoted live")
CURVE_NAMES = {"CL": "WTI Crude", "NG": "Nat Gas", "GC": "Gold",
               "SI": "Silver", "HG": "Copper", "ZC": "Corn",
               "ZS": "Soybeans", "ZW": "Wheat"}
root = st.selectbox("Curve", list(CURVE_NAMES),
                    format_func=lambda r: f"{CURVE_NAMES[r]} ({r})")
if st.button(f"Build {CURVE_NAMES[root]} curve — 6 quote calls"):
    st.session_state["fut_curve_root"] = root
if st.session_state.get("fut_curve_root"):
    r = st.session_state["fut_curve_root"]
    curve = data.futures_curve(r)
    if len(curve) < 2:
        st.warning(f"Couldn't resolve enough {CURVE_NAMES[r]} contract "
                   f"months (Yahoo rate limit or listing gap) — try "
                   f"again in a minute.")
    else:
        front, back = curve.price.iloc[0], curve.price.iloc[-1]
        shape = "BACKWARDATION" if back < front else "CONTANGO"
        color = theme.RED if shape == "BACKWARDATION" else theme.GREEN
        fig = go.Figure(go.Scatter(
            x=curve.contract, y=curve.price, mode="lines+markers",
            line=dict(width=2, color=theme.AMBER),
            marker=dict(size=6)))
        theme.plot(
            theme.style_fig(fig, f"{CURVE_NAMES[r]} — LISTED MONTHS",
                            height=300),
            use_container_width=True)
        st.markdown(
            f'<div style="font-family:\'IBM Plex Mono\',monospace;'
            f'color:{color}">{shape} — back month '
            f'{(back / front - 1) * 100:+.1f}% vs front</div>',
            unsafe_allow_html=True)
        theme.note("The curve's slope is the market's inventory report. "
                   "CONTANGO (upward) = supply comfortable; holders get "
                   "paid nothing to own it now, and rolling a long "
                   "position BLEEDS (negative roll yield — why commodity "
                   "ETFs underperform spot). BACKWARDATION (downward) = "
                   "scarcity NOW; the market pays a premium for prompt "
                   "delivery — historically the bullish configuration. "
                   "Gold is the exception: it's a currency wearing a "
                   "commodity costume, so its curve is just interest "
                   "rates and almost always in contango.")
