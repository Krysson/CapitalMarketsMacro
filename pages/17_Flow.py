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

st.set_page_config(page_title="Flow — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · CH. 15 · G6 — THE FLOW SCAN",
    "Flow Desk",
    "Money moving in ways price doesn't yet show. Single days are "
    "plumbing; the scan speaks only in streaks and divergences — and "
    "the WHY always carries an [I] tag.")

# ---------------------------------------- v4.9.1: flow scoreboard ----
# One-glance composite before the detail: every chip is a cached call
# the sections below make anyway, so this costs no extra fetches.
# Each chip fails soft to an em-dash with a reason.
_sb = st.columns(4)
def _chip(col, label, value, sub, color):
    col.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;'
        f'padding:8px 10px;background:{theme.PANEL};'
        f'border-left:3px solid {color};border-radius:2px">'
        f'<span style="color:{theme.MUTED};font-size:0.68rem;'
        f'letter-spacing:0.08em">{label}</span><br>'
        f'<span style="color:{theme.TEXT};font-size:1.02rem">'
        f'{value}</span><br>'
        f'<span style="color:{theme.MUTED};font-size:0.7rem">{sub}'
        f'</span></div>', unsafe_allow_html=True)
try:
    _f = flow.compute_flows(flow.load())
    _nm = flow.normalize_flows(_f, flow.load())
    if not _nm.empty and flow.flows_static(_f):
        _chip(_sb[0], "ETF FLOW", "—",
              f"source static (n={_f['date'].nunique()})", theme.RED)
    elif not _nm.empty:
        _t = _nm.iloc[0]
        _zs = (f"z {_t['z']:+.1f}" if pd.notna(_t["z"])
               else f"record n={int(_t['n_obs'])}")
        _chip(_sb[0], "ETF FLOW · LOUDEST", f"{_t['ticker']} "
              f"{_t['pct_aum']:+.2f}% AUM", _zs,
              theme.GREEN if _t["pct_aum"] >= 0 else theme.RED)
    else:
        _chip(_sb[0], "ETF FLOW", "—", "record building", theme.MUTED)
except Exception as _e:
    _chip(_sb[0], "ETF FLOW", "—", type(_e).__name__, theme.MUTED)
try:
    _svt, _svd = flow.finra_short()
    _svp = flow.shortvol_percentiles(flow.shortvol_history(), _svt)
    if not _svp.empty:
        _hi = _svp.sort_values("short_ratio",
                               ascending=False).iloc[0]
        _ps = (f"{_hi['pctl']:.0f}th pctl of own record"
               if pd.notna(_hi["pctl"])
               else f"record n={int(_hi['n_obs'])}")
        _chip(_sb[1], "SHORT VOL · HIGHEST",
              f"{_hi['Symbol']} {_hi['short_ratio']:.0%}", _ps,
              theme.AMBER)
    else:
        _chip(_sb[1], "SHORT VOL", "—", "file unreachable",
              theme.MUTED)
except Exception as _e:
    _chip(_sb[1], "SHORT VOL", "—", type(_e).__name__, theme.MUTED)
try:
    _ats = instflow.ats_weekly()
    if not _ats.empty:
        _wk = _ats["week"].max()
        _tw = (_ats[_ats["week"] == _wk]
               .sort_values("shares", ascending=False).iloc[0])
        _chip(_sb[2], "DARK POOL · HEAVIEST",
              f"{_tw['symbol']} {_tw['shares'] / 1e6:,.0f}M sh",
              f"wk of {str(_wk)[:10]}", theme.PURPLE)
    else:
        _chip(_sb[2], "DARK POOL", "—", "needs FINRA credential",
              theme.MUTED)
except Exception as _e:
    _chip(_sb[2], "DARK POOL", "—", type(_e).__name__, theme.MUTED)
try:
    _fpx = instflow.load_footprints()
    if not _fpx.empty:
        _ld = _fpx["date"].max()
        _tot = int(_fpx[_fpx["date"] == _ld]["d_oi"].abs().sum())
        _hst = (_fpx.groupby("date")["d_oi"]
                .apply(lambda s: s.abs().sum()))
        _fps = (f"{float((_hst < _tot).mean() * 100):.0f}th pctl "
                f"of {len(_hst)}d record" if len(_hst) >= 10
                else f"record n={len(_hst)}")
        _chip(_sb[3], "FOOTPRINTS · INTENSITY",
              f"{_tot:,} ΔOI", _fps, theme.AMBER)
    else:
        _chip(_sb[3], "FOOTPRINTS", "—", "record building",
              theme.MUTED)
except Exception as _e:
    _chip(_sb[3], "FOOTPRINTS", "—", type(_e).__name__, theme.MUTED)

theme.note("The scoreboard: the page's four instruments reduced to "
           "one line each, computed from the same cached calls the "
           "panels below make. ETF FLOW = the fund moving hardest "
           "relative to ITS OWN size (% of AUM), with its z-score "
           "once its record reaches 10 sessions. SHORT VOL = the "
           "highest off-exchange short ratio in the set, placed "
           "against that symbol's own accrued history. DARK POOL = "
           "the heaviest ATS name in the latest reported week (two "
           "weeks delayed by rule). FOOTPRINTS = total overnight "
           "|ΔOI| vs the record's own distribution. 'record n=X' "
           "means the yardstick is still accruing — the number "
           "exists, its context doesn't yet. Details, tiers, and "
           "caveats live in each panel below.")

st.divider()

# ---- v4.9.2: two-column reflow — the page reads as a desk, not a scroll ----
_row1l, _row1r = st.columns(2, gap="large")
with _row1l:
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
                theme.neg_red(
                    df.style.format({"1W %": "{:+.1f}", "1M %": "{:+.1f}",
                                     "vs SPY 1M": "{:+.1f}",
                                     "Vol vs 20d": "{:.2f}×"}, na_rep="—"),
                    subset=["1W %", "1M %", "vs SPY 1M"]),
                width="stretch", height=min(560, 60 + 35 * len(df)))
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
with _row1r:
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
            width="stretch", height=min(560, 60 + 35 * len(fs)))
        hi = fs.iloc[0]
        theme.readout(
            theme.AMBER,
            f"{fs_date}: highest short share {hi['Name']} at "
            f"{hi['short_ratio']:.0%} of off-exchange volume. Around half "
            f"is NORMAL (market-maker hedging prints short) — the read is "
            f"outliers and multi-day drift, never the level alone.")
        # v4.9.1: today vs the desk's own accrued record — the level is
        # structurally noisy; the departure from a symbol's own norm is
        # the read. Record accrues one session per app-load-day.
        _svh = flow.shortvol_history()
        _svp = flow.shortvol_percentiles(_svh, fs.reset_index())
        if not _svp.empty and _svp["pctl"].notna().any():
            _ext = _svp[_svp["pctl"].notna()].sort_values(
                "pctl", ascending=False)
            _top, _bot = _ext.iloc[0], _ext.iloc[-1]
            theme.readout(
                theme.PURPLE,
                f"VS OWN RECORD: {_top['Symbol']} at the "
                f"{_top['pctl']:.0f}th percentile of its accrued history "
                f"· {_bot['Symbol']} at the {_bot['pctl']:.0f}th. "
                f"Extremes against a symbol's OWN distribution are the "
                f"tell — the cross-sectional table above can't say that.")
        elif not _svh.empty:
            theme.note(f"Percentiles arrive at 10 accrued sessions per "
                       f"symbol — the record has "
                       f"{_svh['date'].nunique()} so far and grows one "
                       f"per trading day.")
        else:
            theme.note("Short-ratio record starts accruing with the next "
                       "morning accrual run — percentiles vs each "
                       "symbol's own history appear at 10 sessions.")
        theme.note("FINRA publishes per-symbol short volume for OFF-EXCHANGE "
                   "(TRF/ADF/ORF) trades daily, free, same-day — a slice "
                   "the workbook never had. It is not total market "
                   "shorting: exchange volume isn't in it, and short "
                   "volume ≠ short interest. A positioning tell, honestly "
                   "bounded.")

st.divider()

_row2l, _row2r = st.columns(2, gap="large")
with _row2l:
    # ------------------------------------------------ ATS dark venues ----
    theme.panel_bar("Dark-venue concentration — FINRA ATS weekly",
                    "Tier 1 · official · delayed 2 weeks by rule")
    ats = instflow.ats_weekly()
    if ats.empty:
        if instflow._finra_creds() is None:
            st.markdown(
                '<div class="desk-note">ATS data needs the free FINRA API '
                'credential — add FINRA_API_CLIENT_ID and FINRA_API_SECRET '
                'to the app secrets (setup in the README). Until then this '
                'stays the workbook\'s paste tab.</div>',
                unsafe_allow_html=True)
        else:
            st.warning("FINRA API unreachable or returned nothing — "
                       "credentials may need a re-check, or the API is "
                       "busy; try again shortly.")
    else:
        latest_wk = ats["week"].max()
        last = (ats[ats["week"] == latest_wk]
                .sort_values("shares", ascending=False).copy())
        last["Name"] = last["symbol"].map(
            lambda s: flow.FLOW_ETFS.get(s, (s,))[0])
        # v4.9.1: latest week vs each symbol's trailing-4-week average —
        # dark share LEVEL varies by name structurally; the change
        # against its own recent norm is the read.
        _wks = sorted(ats["week"].unique())
        _prior = ats[ats["week"].isin(_wks[-5:-1])]
        _avg4 = _prior.groupby("symbol")["shares"].mean()
        last["vs_4wk"] = [
            (float(r["shares"]) / float(_avg4[r["symbol"]]) - 1) * 100
            if r["symbol"] in _avg4 and _avg4[r["symbol"]] > 0
            else float("nan")
            for _, r in last.iterrows()]
        st.dataframe(
            last.set_index("symbol")[
                ["Name", "shares", "trades", "shares_per_trade",
                 "vs_4wk"]]
            .rename(columns={"shares": "ATS shares",
                             "trades": "ATS trades",
                             "shares_per_trade": "Shares/trade",
                             "vs_4wk": "vs 4-wk avg"})
            .style.format({"ATS shares": "{:,.0f}",
                           "ATS trades": "{:,.0f}",
                           "Shares/trade": "{:,.0f}",
                           "vs 4-wk avg": "{:+,.0f}%"}, na_rep="—"),
            width="stretch",
            height=min(560, 60 + 35 * len(last)))
        conc = instflow.ats_concentration(ats)
        if not conc.empty:
            lines = "; ".join(
                f"{r['symbol']} {r['spt_last']:,.0f}/trade vs "
                f"{r['spt_base']:,.0f} average ({r['ratio']:.2f}×)"
                for _, r in conc.iterrows())
            theme.readout(
                theme.AMBER,
                f"CONCENTRATION — week of {latest_wk:%d-%b}: {lines}. "
                f"Bigger average prints in the dark = bigger players "
                f"working the name.")
        else:
            theme.readout(theme.GREEN,
                          f"Week of {latest_wk:%d-%b}: no shares-per-trade "
                          f"outliers vs trailing averages — dark-venue "
                          f"activity looks routine.")
        theme.note("What this is: every Alternative Trading System — the "
                   "dark pools — must report weekly share and trade counts "
                   "per security to FINRA, published on a two-week delay "
                   "by rule. The single most useful column is "
                   "SHARES/TRADE: dark venues exist to hide size, so when "
                   "the average print in a name gets bigger, someone "
                   "large is working it — quiet accumulation or "
                   "distribution runs for weeks, which is why the delay "
                   "costs less than it sounds. This automates the "
                   "workbook's FINRA_ATS paste tab. [T1]")

    st.divider()

    # --------------------------------------------- the accrued flow record --
with _row2r:
    theme.panel_bar("ETF flow record — Δshares × price, accrued nightly",
                    "Tier 2 · the desk's own data")
    log = flow.load()
    flows = flow.compute_flows(log)
    _static = flow.flows_static(flows)
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
    elif _static:
        theme.readout(
            theme.RED,
            f"SOURCE DEGRADED — {flows['date'].nunique()} sessions "
            f"accrued and every flow is exactly $0: the shares-"
            f"outstanding source has been serving a static figure, so "
            f"Δshares is structurally zero. This is a dead input, not a "
            f"quiet market — real records have noise.")
        theme.note("Root cause (06-Aug post-mortem): Yahoo's quote-"
                   "endpoint shares figure is a rarely-refreshed display "
                   "number, and the snapshot ladder treated its answer "
                   "as success — so the fundamentals timeseries that "
                   "actually updates never ran. v4.9.2 inverts the "
                   "ladder (timeseries first, quote figures as "
                   "fallback). The record heals FORWARD from the first "
                   "session with real share updates; the zero rows stay "
                   "on the data branch as an honest scar. Charts, "
                   "streaks, and the measurement pass return when the "
                   "flows stop being silence.")
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
                width="stretch")
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
                theme.neg_red(stk.set_index("ticker").style.format(
                    {"total_mm": "{:+,.0f}", "days": "{:d}"})),
                width="stretch")
            theme.readout(
                theme.AMBER,
                f"LIVE STREAKS: {len(stk)} — ≥3 one-sided sessions and "
                f"≥$250mm cumulative. A streak against flat-or-opposite "
                f"price is the G6 candidate shape.")
        else:
            theme.readout(theme.GREEN,
                          f"No qualifying streaks ({n_days} sessions "
                          f"accrued) — quiet is information too.")
        # v4.9.1: the measurement pass — raw $mm makes SPY dwarf
        # everything by construction; each fund against its own size and
        # its own record is the honest yardstick.
        nm = flow.normalize_flows(flows, log)
        if not nm.empty:
            theme.panel_bar("Measurement pass — latest session, "
                            "normalized", "each fund vs its own size and "
                            "its own record")
            _nz = int(nm["z"].notna().sum())
            nm_show = nm.copy()
            # pre-format z: NaN must read as an em-dash, never "None"
            nm_show["z"] = nm_show["z"].map(
                lambda v: f"{v:+.1f}" if pd.notna(v) else "—")
            st.dataframe(
                theme.neg_red(
                    nm_show.set_index("ticker")[
                        ["name", "flow_mm", "pct_aum", "roll5_mm", "z",
                         "n_obs"]]
                    .rename(columns={"name": "Name", "flow_mm": "$mm",
                                     "pct_aum": "% AUM",
                                     "roll5_mm": "5-day $mm",
                                     "z": "z (own record)",
                                     "n_obs": "n"})
                    .style.format({"$mm": "{:+,.0f}", "% AUM": "{:+.2f}",
                                   "5-day $mm": "{:+,.0f}",
                                   "n": "{:d}"}, na_rep="—")),
                width="stretch",
                height=min(560, 60 + 35 * len(nm)))
            _ld1 = nm.iloc[0]
            theme.readout(
                theme.AMBER,
                f"LOUDEST VS ITSELF: {_ld1['ticker']} "
                f"{_ld1['pct_aum']:+.2f}% of AUM"
                + (f", z {_ld1['z']:+.1f} vs its own record"
                   if pd.notna(_ld1["z"]) else
                   f" (z arrives at 10 sessions; record has "
                   f"{int(_ld1['n_obs'])})")
                + f" · 5-day {_ld1['roll5_mm']:+,.0f}mm. SPY's raw "
                  f"millions can't say this — a small fund at +2% of "
                  f"AUM is a louder statement than SPY at +0.1%.")
            theme.note("% AUM = flow ÷ prior-day assets (Δshares ÷ "
                       "shares, arithmetic the record already holds). "
                       "The z-score is today against the fund's OWN "
                       "accrued distribution — honest small-n rule: no z "
                       "until 10 sessions, and n is printed so you know "
                       "how much record stands behind each number. The "
                       "5-day sum separates campaigns from single-print "
                       "plumbing. [T2 computed on the desk's own record]")
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
            height=320), width="stretch")
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
    # v4.9.1: size AND seriousness. Notional weights the contracts;
    # moneyness says how far from spot the bet sits (50k lottery
    # tickets and 50k at-the-monies are different sentences); the
    # CAMP flag marks a line loaded on 2+ of the last 5 record days
    # — repeated accumulation is a campaign, not a print.
    recent["notional_mm"] = (recent["d_oi"] * recent["strike"]
                             * 100 / 1e6)
    recent["mny"] = (recent["strike"] / recent["spot"] - 1) * 100
    _d5 = sorted(fp["date"].unique())[-5:]
    _keys = fp[fp["date"].isin(_d5)].groupby(
        ["und", "expiry", "strike", "type"])["date"].nunique()
    recent["camp"] = [
        "CAMP" if _keys.get((r["und"], r["expiry"], r["strike"],
                             r["type"]), 0) >= 2 else ""
        for _, r in recent.iterrows()]
    st.dataframe(
        recent[["Date", "Contract", "d_oi", "notional_mm", "mny",
                "camp", "prev_volume"]]
        .rename(columns={"d_oi": "Δ OI", "notional_mm": "Notional $mm",
                         "mny": "% from spot", "camp": "",
                         "prev_volume": "Day's volume"})
        .style.format({"Δ OI": "{:+,}", "Notional $mm": "{:+,.1f}",
                       "% from spot": "{:+.1f}", "Day's volume": "{:,}"}),
        hide_index=True, width="stretch",
        height=min(500, 40 + 36 * len(recent)))
    big = recent.iloc[0]
    theme.readout(
        theme.AMBER,
        f"LARGEST RECENT: {big['Contract']} {big['d_oi']:+,} contracts "
        f"overnight. Volume ≈ ΔOI = mostly fresh positioning; volume ≫ "
        f"ΔOI = churn with some closing. Side of initiation is NOT in "
        f"this data — say so in the Notebook entry.")
    theme.note("Notional = ΔOI × strike × 100: the dollar weight of "
               "the bet, so a far-out-of-the-money pile stops "
               "reading equal to an at-the-money one. CAMP = the "
               "same contract loaded on 2+ of the last 5 record "
               "days — accumulation with a memory. Both computed "
               "from the record you already keep. [T1 OI · T2 "
               "computed]")
    theme.note("Footprints are Ch. 15's G6 in the options market: money "
               "moving in ways price doesn't yet show. Read them "
               "against skew (VOL page) and the strike's distance from "
               "spot — size at far-out-of-the-money puts near an event "
               "is a different sentence than size at-the-money. Every "
               "row is on the data branch, timestamped before whatever "
               "happens next. ≥20k-contract jumps also fire a nightly "
               "desk-alert issue.")

# ---- v4.9.0: flow by expiry — a display cut of the same record ----
theme.panel_bar("Footprints by expiry",
                "same record · grouped by date the bet expires")
try:
    if fp.empty:
        theme.note("Appears with the footprint record — nothing to "
                   "group yet.")
    else:
        _last = fp["date"].max()
        _cut = fp[fp["date"] == _last].copy()
        _byx = (_cut.groupby(["und", "expiry", "type"])["d_oi"].sum()
                .unstack(fill_value=0).reset_index())
        for _c in ("C", "P"):
            if _c not in _byx:
                _byx[_c] = 0
        _byx["net"] = _byx["C"] + _byx["P"]
        _byx = _byx.sort_values("net", ascending=False)
        st.dataframe(
            _byx.rename(columns={"und": "Und", "expiry": "Expiry",
                                 "C": "Δ OI calls", "P": "Δ OI puts",
                                 "net": "Δ OI total"})
            .style.format({"Δ OI calls": "{:+,}", "Δ OI puts": "{:+,}",
                           "Δ OI total": "{:+,}"}),
            hide_index=True, width="stretch",
            height=min(420, 40 + 36 * len(_byx)))
        _top = _byx.iloc[0]
        theme.readout(
            theme.AMBER,
            f"CONCENTRATION: {_top['und']} {_top['expiry']} took "
            f"{int(_top['net']):+,} contracts of overnight OI "
            f"({str(_last)[:10]} diff). WHERE on the calendar size "
            f"lands is a statement about WHEN the bettor expects to "
            f"be right — same-week loading reads event-driven; "
            f"out-months read positional.")
        theme.note("A display cut of the footprint record above — no "
                   "new feed, same [T1] OI diffs, grouped by the date "
                   "the bet expires instead of by contract. Pairs "
                   "with the OpEx calendar (Calendar page): size "
                   "landing ON an expiration is pin-and-roll "
                   "mechanics; size landing past one is conviction "
                   "with a longer clock.")
except Exception as _e:
    theme.note(f"Expiry cut unavailable ({type(_e).__name__}).")

st.page_link("pages/15_Ideas.py",
             label="Streak forming? Run it through the eight "
                   "generators → Idea Desk")
