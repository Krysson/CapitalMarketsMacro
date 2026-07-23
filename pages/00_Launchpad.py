"""Launchpad — everything at once, nothing scrolls far, no prose.

The teaching notes live on the other pages; this one is pure glass and
numbers, tiled the way the machine tiles them. BLP <GO>.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, events, signals, theme, wire

st.set_page_config(page_title="Launchpad — Desk", page_icon="▪",
                   layout="wide")
theme.header("BOOK III · LAUNCHPAD", "Launchpad")

bundle = data.macro_bundle()
sigs = signals.compute_signals(bundle)
hist = data.market_history(period="1y")
nl = data.net_liquidity(bundle)


def col_series(t: str) -> pd.Series:
    if hist.empty or t not in hist.columns:
        return pd.Series(dtype=float)
    return hist[t].dropna()


def mini(s: pd.Series, title: str, color: str, hline: float | None = None,
         fmt: str = "{:,.2f}") -> None:
    if s.empty:
        theme.panel_bar(title, "—")
        st.markdown('<div class="desk-note">no data</div>',
                    unsafe_allow_html=True)
        return
    theme.panel_bar(title, fmt.format(float(s.iloc[-1])))
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines",
                               line=dict(width=1.4, color=color)))
    if hline is not None:
        fig.add_hline(y=hline, line=dict(color=theme.RED, width=1,
                                         dash="dash"))
    theme.plot(theme.style_fig(fig, None, height=150),
                    use_container_width=True,
                    config={"displayModeBar": False})


# ------------------------------------------------ row A: dials + dates --
cols = st.columns([1, 1, 1, 1, 1.4])
for c, s in zip(cols, sigs):
    with c:
        st.markdown(
            f'<div style="border-radius:2px;padding:8px 10px;'
            f'background:{theme.PANEL};border-left:3px solid {s.color};'
            f'min-height:64px">'
            f'<span class="desk-eyebrow" style="color:{theme.MUTED}">'
            f'{s.category}</span><br>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;'
            f'color:{s.color};font-size:0.92rem">{s.label} · {s.score}/4'
            f'</span></div>', unsafe_allow_html=True)
with cols[4]:
    prints = data.print_lines(data.latest_prints(bundle))
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between">'
        f'<span style="color:{theme.AMBER}">{ev.name}</span>'
        f'<span style="color:{theme.TEXT}">{ev.when}</span></div>'
        + (f'<div style="color:{theme.YELLOW};font-size:0.7rem;'
           f'text-align:right;margin:-1px 0 3px 0">'
           f'{prints[ev.name]}</div>' if prints.get(ev.name) else "")
        for ev in (events.next_cpi(), events.next_nfp(),
                   events.next_fomc()))
    st.markdown(
        f'<div style="border-radius:2px;padding:8px 10px;'
        f'background:{theme.PANEL};border-left:3px solid {theme.AMBER};'
        f'min-height:64px;font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.78rem">{rows}</div>', unsafe_allow_html=True)

# ---------------------------------------------------- row B: mini charts --
b1, b2, b3, b4 = st.columns(4)
with b1:
    mini(col_series("^GSPC"), "SPX · 1Y", theme.TEXT)
with b2:
    vix, v3 = col_series("^VIX"), col_series("^VIX3M")
    r = (vix / v3).dropna() if not vix.empty and not v3.empty \
        else pd.Series(dtype=float)
    mini(r, "VIX/VIX3M", theme.PURPLE, hline=1.0, fmt="{:.3f}")
with b3:
    rsp, spy = col_series("RSP"), col_series("SPY")
    r = (rsp / spy).dropna() if not rsp.empty and not spy.empty \
        else pd.Series(dtype=float)
    mini(r, "RSP/SPY", theme.BLUE, fmt="{:.4f}")
with b4:
    h, l = col_series("HYG"), col_series("LQD")
    r = (h / l).dropna() if not h.empty and not l.empty \
        else pd.Series(dtype=float)
    mini(r, "HYG/LQD", theme.GREEN, fmt="{:.4f}")

# ---------------------------------- row C: table · liquidity · headlines --
c1, c2, c3 = st.columns([2, 1.4, 2])

with c1:
    theme.panel_bar("Cross-asset", "1d chg")
    if hist.empty:
        st.warning("Market data unavailable.")
    else:
        rows = []
        for tkr, name in data.MARKET_TICKERS.items():
            if tkr in hist.columns:
                chg = data.pct_chg(hist[tkr])
                last = hist[tkr].dropna()
                if chg is not None and not last.empty:
                    rows.append({"Instrument": name,
                                 "Last": round(float(last.iloc[-1]), 2),
                                 "Chg %": round(chg, 2)})
        syms = [t for t, n in data.MARKET_TICKERS.items()
                if t in hist.columns
                and data.pct_chg(hist[t]) is not None
                and not hist[t].dropna().empty]
        df = pd.DataFrame(rows)
        ev = st.dataframe(
            df.style.map(
                lambda v: f"color: {theme.GREEN if v > 0 else theme.RED}"
                if isinstance(v, float) else "",
                subset=["Chg %"],
            ).format({"Last": "{:,.2f}", "Chg %": "{:+.2f}"}),
            hide_index=True, height=390, use_container_width=True,
            on_select="rerun", selection_mode="single-row",
            key="lp_xa")
        picked = (ev.selection.rows if ev and hasattr(ev, "selection")
                  else [])
        if picked and picked[0] < len(syms):
            st.session_state["quote_query"] = ("yf", syms[picked[0]], "")
            st.switch_page("pages/6_Quote.py")

with c2:
    mini(data.tail_years(nl, 2) / 1_000_000, "Net liquidity $tn",
         theme.AMBER)
    spark = data.yoy_pct(bundle.get("PCEPILFE", pd.Series(dtype=float)))
    mini(data.tail_years(spark, 2), "Core PCE YoY %", theme.YELLOW,
         fmt="{:.2f}")

with c3:
    theme.panel_bar("Wire", "3 primary + 5 media · TOP <GO>")
    items, dead = wire.fetch_tape(wire.PRIMARY_FEEDS
                                  + wire.NARRATIVE_FEEDS)
    if dead:
        st.markdown(f'<div class="desk-note" style="color:{theme.RED}">'
                    f'FEED DOWN: {", ".join(dead)}</div>',
                    unsafe_allow_html=True)
    if items:
        # Reserved slots, not raw recency: media feeds print dozens of
        # headlines a day, the agencies a few a week — pure newest-first
        # would bury the primary tape every day. Primary leads, always.
        primary = {s for s, _ in wire.PRIMARY_FEEDS}
        prim = [it for it in items if it["src"] in primary][:3]
        narr = [it for it in items if it["src"] not in primary][:5]
        lines = []
        for it in prim + narr:
            colr = theme.AMBER if it["src"] in primary else theme.PURPLE
            stamp = (it["when"].strftime("%d-%b %H:%M") if it["when"]
                     else "--:--")
            title = it["title"].replace("<", "&lt;").replace(">", "&gt;")
            lines.append(
                f'<div style="padding:2px 0;border-bottom:1px solid '
                f'rgba(232,230,225,0.06);white-space:nowrap;'
                f'overflow:hidden;text-overflow:ellipsis">'
                f'<span style="color:{theme.MUTED}">{stamp}</span>'
                f'<span style="color:{colr};margin:0 8px">{it["src"]}'
                f'</span>'
                f'<a href="{it["link"]}" target="_blank" style="color:'
                f'{theme.TEXT};text-decoration:none">{title}</a></div>')
        st.markdown(
            f'<div style="font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:0.76rem;background:{theme.PANEL};'
            f'padding:8px 12px;border-radius:0 0 2px 2px">'
            + "".join(lines) + "</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="desk-note">wire unreachable</div>',
                    unsafe_allow_html=True)


# ------------------------------------------------ row D: the map ------
st.divider()
nav = [
    ("pages/0_Summary.py", "Summary"),
    ("pages/0_Daily_Circuit.py", "Circuit"),
    ("pages/1_Macro.py", "Macro"),
    ("pages/2_Market.py", "Market"),
    ("pages/3_Volatility.py", "Vol"),
    ("pages/7_Rates.py", "Rates"),
    ("pages/8_Futures.py", "Futures"),
    ("pages/9_Global.py", "Global"),
    ("pages/17_Flow.py", "Flow"),
    ("pages/6_Quote.py", "Quote"),
    ("pages/5_Wire.py", "Wire"),
    ("pages/13_Calendar.py", "Calendar"),
    ("pages/10_Fed.py", "Fed"),
    ("pages/4_Notebook.py", "Notebook"),
    ("pages/15_Ideas.py", "Ideas"),
    ("pages/18_Paper.py", "Paper"),
    ("pages/12_Desk_Analyst.py", "Analyst"),
    ("pages/14_History.py", "History"),
    ("pages/11_Time_Machine.py", "Time Machine"),
    ("pages/16_Help.py", "Help"),
]
ncols = st.columns(7)
for i, (path, label) in enumerate(nav):
    with ncols[i % 7]:
        st.page_link(path, label=label)
st.markdown('<div class="desk-note">Everything on one screen above; '
            'everything one click away below. Alert tripwires run '
            'nightly on their own — the active rules and how to tune '
            'them are on the Help page.</div>', unsafe_allow_html=True)
