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

st.set_page_config(page_title="Futures — Desk", page_icon="▪",
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


st.divider()

# ----------------------------------------------------- positioning ----
theme.panel_bar("Positioning — CFTC Commitments of Traders",
                "official weekly filings · Tier 1\u20132")
cot_root = st.selectbox(
    "Contract", list(data.COT_CODES),
    format_func=lambda r: f"{data.COT_CODES[r][1]} ({r})",
    key="cot_root")
code, cot_name, cot_kind = data.COT_CODES[cot_root]
spec_label = data._COT_DATASETS[cot_kind][3]
cot = data.cot_series(code, cot_kind)
if cot.empty:
    st.warning("CFTC data unavailable — the public API may be busy; "
               "try again shortly.")
else:
    net = cot["net_mm"]
    tail5 = data.tail_years(net, 5)
    pct = float((net.tail(260).rank(pct=True)).iloc[-1] * 100)
    fig = go.Figure(go.Scatter(
        x=tail5.index, y=tail5.values, mode="lines",
        line=dict(width=1.6, color=theme.BLUE), fill="tozeroy",
        fillcolor="rgba(77,166,255,0.10)"))
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1))
    theme.plot(theme.style_fig(
        fig, f"{cot_name.upper()} — {spec_label} NET POSITION "
             f"(CONTRACTS, 5Y)", height=300))
    if pct >= 90:
        theme.readout(theme.AMBER,
                      f"Net {net.iloc[-1]:+,.0f} contracts — "
                      f"{pct:.0f}th percentile of 5y. CROWDED LONG — "
                      f"fuel for a squeeze the other way.")
    elif pct <= 10:
        theme.readout(theme.AMBER,
                      f"Net {net.iloc[-1]:+,.0f} contracts — "
                      f"{pct:.0f}th percentile of 5y. CROWDED SHORT — "
                      f"fuel for a squeeze higher.")
    else:
        theme.readout(theme.GREEN,
                      f"Net {net.iloc[-1]:+,.0f} contracts — "
                      f"{pct:.0f}th percentile of 5y. Positioning "
                      f"unremarkable.")
    theme.note("Reported, not estimated: funds file these positions "
               "with the CFTC every week (Tuesday's data, released "
               "Friday — mind the lag). Crowding is a FRAGILITY read, "
               "not a timing signal: extremes mark where a squeeze has "
               "fuel, and extremes can extend for months. Two reports, "
               "two speculator definitions: commodities show MANAGED "
               "MONEY vs commercials (the people holding the barrels "
               "and bushels — usually the ones who know something); "
               "financials show LEVERAGED FUNDS (hedge funds/CTAs) vs "
               "dealers and asset managers. One famous trap in the "
               "financials: a large leveraged-fund SHORT in Treasury "
               "futures is often the cash-futures basis trade, not a "
               "directional bet against bonds — read Treasury COT "
               "extremes with that asterisk attached.")
