"""Time Machine — the desk as of any past date. TM <GO>.

Macro data via ALFRED vintages: what the numbers said THEN, before
revisions. Market data truncated to the date (prices don't revise).
The point is decision training: read the desk cold, commit to a call,
then open the envelope.
"""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, signals, theme

st.set_page_config(page_title="Time Machine — Desk", page_icon="▪",
                   layout="wide")
theme.header(
    "BOOK III · TIME MACHINE",
    "Time Machine",
    "The desk rewound. Macro series are ALFRED vintages — the data as "
    "it was KNOWN that day, before revisions. Prices are simply cut at "
    "the date. Read it cold, write your call, THEN open 'what happened "
    "next'.")

PRESETS = {
    "Sep 16, 2019 — repo spike eve": dt.date(2019, 9, 16),
    "Feb 21, 2020 — pre-COVID top": dt.date(2020, 2, 21),
    "Mar 23, 2020 — the bottom": dt.date(2020, 3, 23),
    "Jan 3, 2022 — the peak": dt.date(2022, 1, 3),
    "Jun 15, 2022 — 75bp era": dt.date(2022, 6, 15),
    "Mar 9, 2023 — SVB weekend eve": dt.date(2023, 3, 9),
}
c1, c2 = st.columns([2, 1])
preset = c1.selectbox("Case file", ["(pick a date below)"]
                      + list(PRESETS))
asof = c2.date_input("As of", PRESETS.get(preset, dt.date(2019, 9, 16)),
                     min_value=dt.date(2008, 1, 1),
                     max_value=dt.date.today() - dt.timedelta(days=30))
asof_ts = pd.Timestamp(asof)
asof_str = str(asof)

# ------------------------------------------------ vintage macro dials ----
with st.spinner(f"Rewinding to {asof:%d %b %Y}…"):
    bundle = data.vintage_bundle(asof_str)
have_vintage = any(not s.empty for s in bundle.values())
if have_vintage:
    sigs = signals.compute_signals(bundle)
    chips = st.columns(4)
    for c, s in zip(chips, sigs):
        with c:
            st.markdown(
                f'<div style="border-radius:2px;padding:10px 12px;'
                f'background:{theme.PANEL};border-left:3px solid '
                f'{s.color}"><span class="desk-eyebrow" style="color:'
                f'{theme.MUTED}">{s.category}</span><br>'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;'
                f'color:{s.color};font-size:0.95rem">{s.label} · '
                f'{s.score}/4</span></div>', unsafe_allow_html=True)
    theme.note(f"The four dials computed from the vintage — this is "
               f"what the desk would have shown on {asof:%d %b %Y}. "
               f"Revisions that came later do not exist here; neither "
               f"does the knowledge of what NBER eventually said.")
    nl = data.net_liquidity(bundle)
    if not nl.empty:
        s = data.tail_years(nl, 3) / 1_000_000
        fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                                   line=dict(width=2,
                                             color=theme.AMBER)))
        theme.plot(theme.style_fig(fig, "NET LIQUIDITY AS KNOWN THEN "
                                        "($TN)", height=260))
else:
    st.info("Vintage macro needs a FRED_API_KEY in secrets (ALFRED "
            "endpoint). Market sections below still work — prices "
            "don't revise.")

st.divider()

# --------------------------------------------- markets, cut at the date --
tick_map = {"^GSPC": ("S&P 500", theme.TEXT),
            "^VIX": ("VIX", theme.PURPLE)}
spx = data.px_history("^GSPC")[:asof_ts]
vix = data.px_history("^VIX")[:asof_ts]
v3m = data.px_history("^VIX3M")[:asof_ts]
m1, m2 = st.columns(2)
with m1:
    if not spx.empty:
        s = data.tail_years(spx, 2)
        ma200 = spx.rolling(200).mean().reindex(s.index)
        fig = go.Figure()
        fig.add_scatter(x=s.index, y=s.values, mode="lines",
                        name="SPX", line=dict(width=1.8,
                                              color=theme.TEXT))
        fig.add_scatter(x=ma200.index, y=ma200.values, mode="lines",
                        name="200d", line=dict(width=1,
                                               color=theme.RED))
        theme.plot(theme.style_fig(fig, "SPX — AS OF DATE", height=280))
        d200 = (s.iloc[-1] / spx.rolling(200).mean().iloc[-1] - 1) * 100
        theme.readout(theme.GREEN if d200 >= 0 else theme.RED,
                      f"SPX {s.iloc[-1]:,.0f} — {abs(d200):.1f}% "
                      f"{'ABOVE' if d200 >= 0 else 'BELOW'} the 200-day.")
with m2:
    if not vix.empty and not v3m.empty:
        r = (vix / v3m).dropna()
        if not r.empty:
            s = data.tail_years(r, 1)
            fig = go.Figure(go.Scatter(x=s.index, y=s.values,
                                       mode="lines",
                                       line=dict(width=1.6,
                                                 color=theme.PURPLE)))
            fig.add_hline(y=1.0, line=dict(color=theme.RED, width=1,
                                           dash="dash"))
            theme.plot(theme.style_fig(fig, "VIX/VIX3M — AS OF DATE",
                                       height=280))
            last = float(r.iloc[-1])
            theme.readout(theme.GREEN if last < 1 else theme.RED,
                          f"VIX/VIX3M = {last:.3f} — "
                          + ("contango." if last < 1
                             else "INVERTED — stress regime."))
    elif not vix.empty:
        theme.readout(theme.MUTED, "VIX3M history starts ~2009-2010 on "
                                   "Yahoo — ratio unavailable this far "
                                   "back.")

theme.note("Now do the exercise properly: Analyst's Notebook template, "
           "on paper or on the NOTE page — Evidence, Interpretation, "
           "Risks, Falsification, Decision — BEFORE opening the "
           "envelope below. The value of the machine is that you can't "
           "un-know the future; the discipline is pretending you can.")

with st.expander("SEALED — What happened next — open AFTER you've written "
                 "your call"):
    full = data.px_history("^GSPC")
    fwd = data.fwd_from_series(full, asof_ts, (5, 21, 63, 126))
    if fwd:
        cells = st.columns(len(fwd))
        for c, (h, v) in zip(cells, fwd.items()):
            label = {5: "1W", 21: "1M", 63: "3M", 126: "6M"}[h]
            with c:
                st.markdown(
                    f'<div style="background:{theme.PANEL};'
                    f'padding:8px 12px;border-radius:2px;border-left:'
                    f'3px solid '
                    f'{theme.GREEN if v > 0 else theme.RED};'
                    f'font-family:\'IBM Plex Mono\',monospace">'
                    f'<span class="desk-eyebrow" style="color:'
                    f'{theme.MUTED}">SPX +{label}</span><br>'
                    f'<span style="color:'
                    f'{theme.GREEN if v > 0 else theme.RED};'
                    f'font-size:1rem">{v:+.1f}%</span></div>',
                    unsafe_allow_html=True)
        after = full[full.index > asof_ts]
        if len(after) > 5:
            s = after.head(126)
            fig = go.Figure(go.Scatter(x=s.index, y=s.values,
                                       mode="lines",
                                       line=dict(width=1.8,
                                                 color=theme.YELLOW)))
            theme.plot(theme.style_fig(fig, "THE ENVELOPE — SPX, NEXT "
                                            "6 MONTHS", height=260))
    else:
        st.markdown('<div class="desk-note">Not enough forward history '
                    'yet for this date.</div>', unsafe_allow_html=True)
    theme.note("Grade yourself honestly: right for the right reason, "
               "right for the wrong reason, or wrong. Only the first "
               "one compounds.")
