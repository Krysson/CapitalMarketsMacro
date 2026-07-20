"""Global — world equity indices and FX crosses. WEI <GO> / FXC <GO>.

The desk's international window: every major index board and a G8 cross
matrix, both from free delayed data. Time-zone honesty applies: while
New York trades, Asia's numbers are yesterday's close — the board is a
relay race, not a snapshot.
"""
import pandas as pd
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Global — Desk", page_icon="🌐",
                   layout="wide")
theme.header(
    "BOOK III · GLOBAL",
    "World Indices & FX",
    "WEI on the real machine is world equity indices; FXC is the cross "
    "matrix. Same idea here, free and delayed. Read the relay: Asia "
    "hands to Europe hands to New York — divergence between the legs is "
    "the information.")

board = data.global_board()


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


# ------------------------------------------------- world index board ----
theme.panel_bar("World equity indices", "delayed · local closes")
if board.empty:
    st.error("Index data unavailable — try again shortly.")
else:
    rows = []
    for region, members in data.GLOBAL_INDICES.items():
        for tkr, name in members:
            if tkr in board.columns:
                s = board[tkr].dropna()
                if s.empty:
                    continue
                rows.append({"Region": region, "Index": name,
                             "Last": round(float(s.iloc[-1]), 1),
                             "1d %": ret(s, 1), "1m %": ret(s, 21),
                             "YTD %": ytd(s)})
    df = pd.DataFrame(rows)
    pct = ["1d %", "1m %", "YTD %"]
    st.dataframe(
        df.style.map(
            lambda v: f"color: {theme.GREEN if v > 0 else theme.RED}"
            if isinstance(v, float) else "", subset=pct,
        ).format({"Last": "{:,.1f}", **{c: "{:+.2f}" for c in pct}},
                 na_rep="—"),
        hide_index=True, height=min(680, 40 + 36 * len(df)),
        use_container_width=True)

    ytds = df["YTD %"].dropna()
    if len(ytds):
        n_up = int((ytds > 0).sum())
        theme.readout(
            theme.GREEN if n_up > len(ytds) / 2 else theme.AMBER,
            f"{n_up} of {len(ytds)} indices positive YTD — "
            + ("global risk appetite broad." if n_up > len(ytds) / 2
               else "gains concentrated — a US-only rally is a "
                    "different animal than a global one."))
    theme.note("US leadership vs the world is a regime in itself. When "
               "EAFE and EM confirm a US rally, it's liquidity-driven "
               "and durable-until-it-isn't; when the US rises alone, "
               "check the dollar below — a strong dollar starves the "
               "rest of the world of exactly the liquidity the Macro "
               "page measures.")

st.divider()

# ---------------------------------------------------- FX cross matrix ----
theme.panel_bar("FX cross matrix", "row = 1 unit of · col = priced in")
if not board.empty and "DX-Y.NYB" in board.columns:
    dxy = board["DX-Y.NYB"].dropna()
    d = ret(dxy, 21)
    if d is not None:
        theme.readout(
            theme.AMBER if d > 0 else theme.GREEN,
            f"DXY {float(dxy.iloc[-1]):,.1f} · {d:+.2f}% over ~1 month — "
            + ("dollar TIGHTENING the global tide."
               if d > 0 else "dollar easing — tailwind for risk & EM."))

cross, chg = data.fx_matrix()
if cross.empty:
    st.warning("FX data unavailable — try again shortly.")
else:
    def color_cell(base: str, quote: str) -> str:
        try:
            v = chg.loc[base, quote]
        except Exception:
            return ""
        if base == quote or pd.isna(v):
            return f"color: {theme.MUTED}"
        return f"color: {theme.GREEN if v > 0 else theme.RED}"

    styled = cross.style.format("{:,.4g}").apply(
        lambda col: [color_cell(b, col.name) for b in cross.index],
        axis=0)
    st.dataframe(styled, use_container_width=True,
                 height=40 + 36 * len(cross))
    theme.note("Triangulated from USD pairs (Yahoo, delayed) — read a "
               "row as 'one unit of this buys…'. Green = that cross "
               "rose vs yesterday. The crosses that matter most to the "
               "desk: USDJPY (the carry trade's heartbeat — violent "
               "yen strength = carry unwinding, risk-off everywhere) "
               "and EURUSD (the dollar's biggest counterweight). CNY "
               "is managed — read its moves as policy, not markets.")
