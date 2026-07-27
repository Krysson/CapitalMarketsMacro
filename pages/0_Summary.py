"""Capital Markets Desk — Summary page (the desk's front door)."""
import json

import pandas as pd
import streamlit as st

from desk import data, events, signals, theme

st.set_page_config(page_title="Capital Markets Desk", page_icon="▪",
                   layout="wide")

# TradingView ticker tape — official free embed. Display-only glass:
# every computed signal below still runs on FRED / yfinance.
#
# GOTCHA (licensing, not syntax): Cboe indices (VIX), ICE's DXY, and
# TVC:US10Y are NOT licensed for third-party embeds — they render as
# "only available on TradingView". Embed-safe sources instead:
#   - CAPITALCOM:* — live CFD mirrors of DXY / VIX / 10Y yield
#   - FRED:*       — daily official values; proven in TradingView's own
#                    widget demos (FRED:SP500 etc.)
# If a CAPITALCOM symbol ever stops rendering, swap in the FRED fallback
# on the same line.
theme.header(
    "THE FREE DESK · SUMMARY",
    "Capital Markets Desk",
    "Green = rising / loose · Red = falling / tight · Yellow = mixed. "
    "Colors show direction, not good vs. bad — quick-glance heuristics for a "
    "learning desk, not trading signals or investment advice.")

with st.spinner("Pulling FRED data…"):
    bundle = data.macro_bundle()

cpi, nfp, fomc = events.next_cpi(), events.next_nfp(), events.next_fomc()
prints = data.print_lines(data.latest_prints(bundle))
e1, e2, e3 = st.columns(3)
for col, ev, blurb in (
    (e1, cpi, "the month's inflation print — vol event at 8:30 a.m."),
    (e2, nfp, "jobs day — the biggest labor print, 8:30 a.m."),
    (e3, fomc, "rate decision + presser — vol event at 2:00 p.m."),
):
    pline = prints.get(ev.name, "")
    print_html = (f'<div style="font-family:\'IBM Plex Mono\',monospace;'
                  f'font-size:0.78rem;color:{theme.YELLOW};'
                  f'margin-top:3px">{pline}</div>') if pline else ""
    with col:
        st.markdown(
            f'''
            <div style="border-radius:2px;padding:10px 14px;
                        background:{theme.PANEL};
                        border-left:3px solid {theme.AMBER};
                        margin-bottom:6px">
              <span class="desk-eyebrow" style="color:{theme.MUTED}">
                next {ev.name}</span>
              <span style="font-family:'IBM Plex Mono',monospace;
                           font-size:0.95rem;color:{theme.TEXT};
                           margin-left:10px">{ev.when}</span>
              {print_html}
              <div class="desk-note" style="margin-top:2px">{blurb}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

with st.expander("Full economic calendar — TradingView (display glass)"):
    theme.embed(
        """
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-events.js"
            async>
          {
            "colorTheme": "dark",
            "isTransparent": true,
            "width": "100%",
            "height": 450,
            "locale": "en",
            "importanceFilter": "0,1",
            "countryFilter": "us"
          }
          </script>
        </div>
        """,
        height=460)
    theme.note("Everything between the two anchors above — claims every "
               "Thursday, PCE, payrolls, auctions. The amber strip is "
               "computed from published schedules and is the desk's source "
               "of truth; this widget is glass for everything else.")

sigs = signals.compute_signals(bundle)

if all(s.loading for s in sigs):
    st.warning(
        "No FRED data loaded. If this persists, add a FRED_API_KEY in "
        "App settings → Secrets:  `FRED_API_KEY = \"your_key_here\"`")

# One representative 1y trace per card. All series already live in the
# bundle (net liquidity is derived from it), so this costs zero extra
# FRED calls. Sparklines render in amber — the house accent — rather
# than the card's score color, so the line doesn't imply a judgment.
SPARKS = {
    "Growth": (data.yoy_pct(bundle.get("PAYEMS", pd.Series(dtype=float))),
               "Payrolls YoY %"),
    "Inflation": (data.yoy_pct(bundle.get("PCEPILFE", pd.Series(dtype=float))),
                  "Core PCE YoY %"),
    "Policy": (bundle.get("DFEDTARU", pd.Series(dtype=float)),
               "Fed funds upper %"),
    "Liquidity": (data.net_liquidity(bundle) / 1_000_000,
                  "Net liquidity $tn"),
}

cols = st.columns(4)
for col, s in zip(cols, sigs):
    spark_series, spark_label = SPARKS.get(s.category,
                                           (pd.Series(dtype=float), ""))
    svg = theme.sparkline_svg(data.tail_years(spark_series, 1))
    spark_html = (f'{svg}<div class="desk-note" style="margin-top:4px">'
                  f'{spark_label} · 1y</div>') if svg else ""
    with col:
        st.markdown(
            f"""
            <div style="border-radius:2px;padding:18px 16px;
                        background:{theme.PANEL};
                        border-left:4px solid {s.color};min-height:176px">
              <div class="desk-eyebrow" style="color:{theme.MUTED}">
                {s.category}</div>
              <div style="font-family:'IBM Plex Mono',monospace;font-size:1.2rem;
                          font-weight:600;color:{s.color};line-height:1.2;
                          margin:4px 0 6px 0">{s.label}</div>
              <div class="desk-note">score {s.score} / 4</div>
              {spark_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

left, right = st.columns([3, 2])

with left:
    st.subheader("Under the hood")
    st.markdown('<div class="desk-caption">The four checks behind each '
                'signal.</div>', unsafe_allow_html=True)
    for s in sigs:
        with st.expander(f"{s.category} — {s.label}  ·  {s.score}/4"):
            for c in s.checks:
                icon = "✔" if c.passed else ("✘" if c.passed is False else "…")
                st.markdown(f"{icon} {c.label}")

with right:
    st.subheader("Cross-asset, today")
    hist = data.market_history(period="3mo")
    if hist.empty:
        st.warning("Market data unavailable (Yahoo Finance).")
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
            hide_index=True, height=430, use_container_width=True,
            on_select="rerun", selection_mode="single-row",
            key="sm_xa")
        picked = (ev.selection.rows if ev and hasattr(ev, "selection")
                  else [])
        if picked and picked[0] < len(syms):
            st.session_state["quote_query"] = ("yf", syms[picked[0]], "")
            st.switch_page("pages/6_Quote.py")

# ------------------------------------------------ bot status strip ----
# The one thing the app previously couldn't tell you: is the nightly
# bot alive? Computed from data already cached; fail-soft.
try:
    import datetime as _dt

    from desk import accrue as _acc
    _amsg = ""
    try:
        _amsg = _acc.run()
    except Exception:
        pass
    from desk import flow as _flow
    from desk import history as _history
    from desk import instflow as _inst
    _h = _history.load()
    _fl = _flow.compute_flows(_flow.load())
    _fp = _inst.load_footprints()
    if _h.empty:
        _line, _col = ("BOT: no record yet — run the snapshot workflow "
                       "once (README)"), theme.YELLOW
    else:
        _last = _h.index.max()
        _age = ((_dt.date.today() - _last.date()).days)
        _stale = _age > 4          # > long weekend = something's wrong
        _line = (f"BOT: last row {_last:%a %d-%b} · "
                 f"{len(_h)} session{'s' if len(_h) != 1 else ''} · "
                 f"flows {_fl['date'].nunique() if not _fl.empty else 0}"
                 f" session{'s' if _fl.empty or _fl['date'].nunique() != 1 else ''} · "
                 f"footprints {0 if _fp.empty else len(_fp)}")
        if _stale:
            _line += (f" · STALE ({_age}d old) — check the Actions tab")
        _col = theme.RED if _stale else theme.GREEN
    from desk.history import OWNER as _o, REPO as _r

    @st.cache_data(ttl=1800, show_spinner=False)
    def _open_alerts() -> int | None:
        try:
            import requests as _rq
            r = _rq.get(
                f"https://api.github.com/repos/{_o}/{_r}/issues",
                params={"labels": "desk-alert", "state": "open",
                        "per_page": 100}, timeout=10)
            if r.ok:
                return len(r.json())
        except Exception:
            pass
        return None

    _n = _open_alerts()
    _line += (" · alerts open: " + (str(_n) if _n is not None
                                    else "n/a"))
    if _n:
        _col = theme.YELLOW if _col == theme.GREEN else _col
    _links = (f' &nbsp;<a href="https://github.com/{_o}/{_r}/issues'
              f'?q=label%3Adesk-alert" target="_blank" '
              f'style="color:{theme.AMBER}">alerts</a> · '
              f'<a href="https://github.com/{_o}/{_r}/actions" '
              f'target="_blank" style="color:{theme.AMBER}">runs</a> · '
              f'<a href="https://github.com/{_o}/{_r}/tree/data" '
              f'target="_blank" style="color:{theme.AMBER}">record</a>')
    if _amsg:
        _line += " · APP-ACCRUAL: " + _amsg
    st.markdown(f'<div class="desk-note" style="color:{_col}">{_line}'
                f'{_links}</div>', unsafe_allow_html=True)
except Exception:
    pass

st.markdown('<div class="desk-note">Data: FRED (St. Louis Fed) · Yahoo '
            'Finance, delayed · TradingView tape is display glass · Pages: '
            'Daily Circuit / Macro / Market / Volatility / Notebook / '
            'Wire in '
            'the sidebar</div>', unsafe_allow_html=True)
