"""Flow Desk — the Sector Flow Tracker's automatable half, live.

Three layers, tiered honestly: the rotation monitor (Yahoo, Tier 2,
live now); FINRA's daily short-volume ratios (official filings, Tier
1, keyless, off-exchange only); and the desk's own ETF flow record —
Δshares × price, logged nightly by the snapshot bot to the data
branch, accruing from its first run exactly like the signal record.
What stays in the workbook: the BlockLog and the FINRA ATS paste —
real-time prints aren't free and the ATS files are login-gated and
weeks delayed by rule. The split is the design: app = automated
observables, workbook = manual flow log.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, flow, instflow, theme

st.set_page_config(page_title="Flow — Desk", page_icon="🌊", layout="wide")
theme.header(
    "BOOK III · CH. 15 · G6 — THE FLOW SCAN",
    "Flow Desk",
    "Money moving in ways price doesn't yet show. Single days are "
    "plumbing; the scan speaks only in streaks and divergences — and "
    "the WHY always carries an [I] tag.")

# ------------------------------------------------- rotation monitor ----
theme.panel_bar("Rotation monitor", "Yahoo · Tier 2 · live")
try:
    tickers = list(flow.FLOW_ETFS)
    import yfinance as yf
    raw = yf.download(tickers, period="3mo", interval="1d",
                      auto_adjust=True, progress=False,
                      group_by="column")
    closes = (raw["Close"] if "Close" in raw else raw).dropna(how="all")
    vols = raw["Volume"] if "Volume" in raw else pd.DataFrame()
except Exception:
    closes, vols = pd.DataFrame(), pd.DataFrame()

if closes.empty or "SPY" not in closes.columns:
    st.warning("Rotation data unavailable — Yahoo may be rate-limiting. "
               "Try again shortly.")
else:
    spy = closes["SPY"].dropna()
    rows = []
    for t in tickers:
        if t not in closes.columns:
            continue
        s = closes[t].dropna()
        if len(s) < 22:
            continue
        r1w = (float(s.iloc[-1]) / float(s.iloc[-6]) - 1) * 100
        r1m = (float(s.iloc[-1]) / float(s.iloc[-22]) - 1) * 100
        rs = r1m - (float(spy.iloc[-1]) / float(spy.iloc[-22]) - 1) * 100
        vratio = None
        if t in vols.columns:
            v = vols[t].dropna()
            if len(v) > 21 and float(v.iloc[-21:-1].mean()) > 0:
                vratio = float(v.iloc[-1]) / float(v.iloc[-21:-1].mean())
        rows.append({"Ticker": t, "Name": flow.FLOW_ETFS[t][0],
                     "Group": flow.FLOW_ETFS[t][1],
                     "1W %": r1w, "1M %": r1m, "vs SPY 1M": rs,
                     "Vol vs 20d": vratio})
    if rows:
        df = (pd.DataFrame(rows)
              .sort_values("vs SPY 1M", ascending=False)
              .set_index("Ticker"))
        st.dataframe(
            df.style.format({"1W %": "{:+.1f}", "1M %": "{:+.1f}",
                             "vs SPY 1M": "{:+.1f}",
                             "Vol vs 20d": "{:.2f}×"}, na_rep="—"),
            use_container_width=True, height=min(560, 60 + 35 * len(df)))
        lead, lag = df.index[0], df.index[-1]
        theme.readout(
            theme.AMBER,
            f"LEADERSHIP 1M vs SPY: {df.loc[lead, 'Name']} "
            f"{df.loc[lead, 'vs SPY 1M']:+.1f} leads · "
            f"{df.loc[lag, 'Name']} {df.loc[lag, 'vs SPY 1M']:+.1f} "
            f"lags. Volume above ~1.5× its 20-day average marks where "
            f"the activity is, not which direction it points.")
    theme.note("This replaces the workbook's RotationMonitor tab, live. "
               "Relative strength vs SPY is the rotation read; raw "
               "returns flatter everything in an up-tape. Rotation "
               "shows in flows DAYS before it shows in relative "
               "performance — which is why the flow record below "
               "exists.")

st.divider()

# ---------------------------------------------- FINRA short volume ----
theme.panel_bar("Short-volume ratios — FINRA Reg SHO daily",
                "Tier 1 · official · off-exchange only")
fs, fs_date = flow.finra_short()
if fs.empty:
    st.warning("FINRA daily file unreachable right now — it publishes "
               "each trading day; try again shortly.")
else:
    fs = fs.copy()
    fs["Name"] = fs["Symbol"].map(lambda s: flow.FLOW_ETFS[s][0])
    fs = fs.sort_values("short_ratio", ascending=False).set_index("Symbol")
    st.dataframe(
        fs[["Name", "ShortVolume", "TotalVolume", "short_ratio"]]
        .style.format({"ShortVolume": "{:,.0f}",
                       "TotalVolume": "{:,.0f}",
                       "short_ratio": "{:.1%}"}),
        use_container_width=True, height=min(560, 60 + 35 * len(fs)))
    hi = fs.iloc[0]
    theme.readout(
        theme.AMBER,
        f"{fs_date}: highest short share {hi['Name']} at "
        f"{hi['short_ratio']:.0%} of off-exchange volume. Around half "
        f"is NORMAL (market-maker hedging prints short) — the read is "
        f"outliers and multi-day drift, never the level alone.")
    theme.note("FINRA publishes per-symbol short volume for OFF-EXCHANGE "
               "(TRF/ADF/ORF) trades daily, free, same-day — a slice "
               "the workbook never had. It is not total market "
               "shorting: exchange volume isn't in it, and short "
               "volume ≠ short interest. A positioning tell, honestly "
               "bounded.")

st.divider()

# --------------------------------------------- the accrued flow record --
theme.panel_bar("ETF flow record — Δshares × price, accrued nightly",
                "Tier 2 · the desk's own data")
log = flow.load()
flows = flow.compute_flows(log)
if flows.empty:
    theme.readout(
        theme.YELLOW,
        "NO FLOW RECORD YET — accrual starts at the snapshot bot's "
        "next run and needs two runs before the first Δ exists.")
    st.markdown(
        "Fund-level ETF flows have no free historical feed — the paid "
        "aggregators license exactly this. So the desk does what it did "
        "for the signal record: **accrues its own**. Each night the bot "
        "logs shares outstanding × close for the 23-ETF set to "
        "`history/flows.csv` on the `data` branch; flow = Δshares × "
        "price (creations and redemptions) computes from day one "
        "forward. Nothing backfilled — the record is thin before it is "
        "long, and every row is a timestamped commit. Two runs from "
        "now, the first bars appear here.")
else:
    n_days = flows["date"].nunique()
    last_day = flows["date"].max()
    # latest-day group signature
    gd = flow.group_day(flows)
    if not gd.empty:
        fig = go.Figure(go.Bar(
            x=gd.index, y=gd["net_mm"],
            marker_color=[theme.GREEN if v >= 0 else theme.RED
                          for v in gd["net_mm"]]))
        theme.plot(theme.style_fig(
            fig, f"NET FLOW BY GROUP — {last_day:%d-%b-%Y} ($mm)",
            height=280, unified_hover=False),
            use_container_width=True)
        eq = float(gd.reindex(["Sector", "Broad"])["net_mm"].sum())
        fi = (float(gd.loc["Fixed Income", "net_mm"])
              if "Fixed Income" in gd.index else 0.0)
        sig = (eq <= -1500 and fi >= 500)
        theme.readout(
            theme.RED if sig else theme.GREEN,
            (f"ROTATION SIGNATURE — equity ${eq:,.0f}mm out, fixed "
             f"income ${fi:+,.0f}mm in: the July 15 pattern. Rotation "
             f"or distribution? Write the falsifier for each answer."
             if sig else
             f"Latest session: equity ${eq:+,.0f}mm, fixed income "
             f"${fi:+,.0f}mm — no rotation signature."))
    # streaks
    stk = flow.streaks(flows)
    if not stk.empty:
        st.dataframe(
            stk.set_index("ticker").style.format(
                {"total_mm": "{:+,.0f}", "days": "{:d}"}),
            use_container_width=True)
        theme.readout(
            theme.AMBER,
            f"LIVE STREAKS: {len(stk)} — ≥3 one-sided sessions and "
            f"≥$250mm cumulative. A streak against flat-or-opposite "
            f"price is the G6 candidate shape.")
    else:
        theme.readout(theme.GREEN,
                      f"No qualifying streaks ({n_days} sessions "
                      f"accrued) — quiet is information too.")
    # cumulative by group
    cum = (flows.groupby(["date", "group"])["flow_mm"].sum()
           .unstack().fillna(0).cumsum())
    fig2 = go.Figure()
    for col, colr in (("Sector", theme.AMBER), ("Broad", theme.TEXT),
                      ("Fixed Income", theme.BLUE),
                      ("Commodity", theme.YELLOW)):
        if col in cum.columns:
            fig2.add_scatter(x=cum.index, y=cum[col], mode="lines",
                             name=col, line=dict(width=1.6, color=colr))
    theme.plot(theme.style_fig(
        fig2, "CUMULATIVE NET FLOW SINCE ACCRUAL START ($mm)",
        height=320), use_container_width=True)
theme.note("Flow = Δ(shares outstanding) × price — creations and "
           "redemptions, the same arithmetic the paid aggregators "
           "sell. [T2]: Yahoo's shares figure can lag a day, which is "
           "why the scan trades streaks, never single prints. The "
           "record is live-accrued on the data branch — audit it in "
           "the git log. Big one-sided streaks and the "
           "equity-out/bonds-in signature also fire nightly "
           "desk-alert issues automatically.")

st.divider()

# ----------------------------------------- options OI footprints ----
theme.panel_bar("Options footprints — overnight OI jumps",
                "SPY & QQQ · Tier 1 observable, side unknown")
fp = instflow.load_footprints()
if fp.empty:
    theme.readout(
        theme.YELLOW,
        "NO FOOTPRINT RECORD YET — the bot stores tonight's chain and "
        "starts diffing tomorrow; footprints appear from run two.")
    st.markdown(
        "Open interest is the one options number institutions cannot "
        "hide: cleared positions, per strike, published daily. A strike "
        "whose OI jumps thousands of contracts overnight means real "
        "size was established there — observable by anyone who "
        "compared yesterday's chain to today's, which is exactly what "
        "the bot now does (near expiries, strikes within ±10% of "
        "spot). What the paid flow products add is *side inference* — "
        "sweep detection, aggressor tagging. This desk records the "
        "footprint and says honestly: size arrived; direction is your "
        "hypothesis to falsify.")
else:
    recent = fp.sort_values(["date", "d_oi"],
                            ascending=[False, False]).head(15).copy()
    recent["Date"] = recent["date"].dt.strftime("%d-%b")
    recent["Contract"] = (recent["und"] + " " + recent["expiry"].astype(str)
                          + " " + recent["strike"].map("{:g}".format)
                          + recent["type"])
    st.dataframe(
        recent[["Date", "Contract", "oi_prev", "oi_now", "d_oi",
                "prev_volume"]]
        .rename(columns={"oi_prev": "OI before", "oi_now": "OI after",
                         "d_oi": "Δ OI", "prev_volume": "Day's volume"})
        .style.format({"OI before": "{:,}", "OI after": "{:,}",
                       "Δ OI": "{:+,}", "Day's volume": "{:,}"}),
        hide_index=True, use_container_width=True,
        height=min(500, 40 + 36 * len(recent)))
    big = recent.iloc[0]
    theme.readout(
        theme.AMBER,
        f"LARGEST RECENT: {big['Contract']} {big['d_oi']:+,} contracts "
        f"overnight. Volume ≈ ΔOI = mostly fresh positioning; volume ≫ "
        f"ΔOI = churn with some closing. Side of initiation is NOT in "
        f"this data — say so in the Notebook entry.")
    theme.note("Footprints are Ch. 15's G6 in the options market: money "
               "moving in ways price doesn't yet show. Read them "
               "against skew (VOL page) and the strike's distance from "
               "spot — size at far-out-of-the-money puts near an event "
               "is a different sentence than size at-the-money. Every "
               "row is on the data branch, timestamped before whatever "
               "happens next. ≥20k-contract jumps also fire a nightly "
               "desk-alert issue.")

st.page_link("pages/15_Ideas.py",
             label="Streak forming? Run it through the eight "
                   "generators → Idea Desk", icon="⚡")
