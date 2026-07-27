"""Valuation (VAL) — the horizon anchor. Valuation is a HORIZON tool,
not a timing tool: it told you nothing useful about any given quarter
and almost everything about the coming decade."""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from desk import data, theme

st.set_page_config(page_title="Valuation — Desk", page_icon="▪",
                   layout="wide")
theme.header("BOOK II · VALUATION", "Valuation",
             "Long-horizon anchors from free primary sources. None of "
             "this times anything; all of it sets expectations.")

# Buffett indicator
try:
    g = data.fred_series("GDP", start="1990-01-01")
    w = data.fred_series("WILL5000PR", start="1990-01-01")
    src = "FRED WILL5000PR [T1]"
    if w.empty:
        # Wilshire ended its FRED partnership (2024) and the series
        # died — the TED-spread lesson, live. Yahoo still carries the
        # index level; proportional, labeled honestly.
        o = data.ohlc("^W5000", period="max")
        w = o["Close"] if not o.empty else w
        src = "Yahoo ^W5000 [T2] — FRED series discontinued"
    if not w.empty and not g.empty:
        g_d = g.reindex(w.index, method="ffill")
        buf = (w / g_d * 100).dropna()
        fig = go.Figure(go.Scatter(x=buf.index, y=buf.values,
                                   mode="lines",
                                   line=dict(width=1.8,
                                             color=theme.AMBER)))
        theme.plot(theme.style_fig(
            fig, "BUFFETT INDICATOR — TOTAL MARKET / GDP (%)",
            height=340, right_text=theme.fmt_last(buf),
            right_color=theme.AMBER), use_container_width=True)
        theme.note(f"Total market cap over GDP — Buffett's 'best "
                   f"single measure' line made him its namesake. "
                   f"Structurally higher margins and global revenues "
                   f"argue the old mean is stale — the honest debate "
                   f"to hold, not resolve. Source: {src}.")
    else:
        missing = ("GDP (FRED)" if g.empty else "") + \
                  (" and " if g.empty and w.empty else "") + \
                  ("Wilshire level (FRED + Yahoo both empty)"
                   if w.empty else "")
        st.warning(f"Buffett indicator skipped — no data for "
                   f"{missing}. Empty panels say why (v4.4.5 house "
                   f"rule).")
except Exception as e:
    st.warning(f"Buffett indicator skipped ({type(e).__name__}).")

# ERP proxy + dividend yield
try:
    prof = data.ticker_profile("SPY")
    pe = prof.get("trailingPE")
    dy = prof.get("dividendYield")
    d10 = data.fred_series("DGS10", start="2024-01-01")
    y10 = float(d10.dropna().iloc[-1]) if not d10.empty else None
    if pe and y10:
        ey = 100 / float(pe)
        theme.readout(
            theme.AMBER,
            f"EARNINGS YIELD (1/PE, SPY ttm) {ey:.2f}% · 10Y "
            f"{y10:.2f}% · ERP PROXY {ey - y10:+.2f}pp · SPY dividend "
            f"yield {float(dy or 0):.2f}%")
        theme.note("The equity risk premium proxy: what stocks earn "
                   "over the riskless rate. Near zero or negative = "
                   "you're paid nothing extra for equity risk — it "
                   "happened in 2000 and again recently; both times "
                   "the DECADE that followed obeyed it while the "
                   "quarters ignored it. [T2 earnings via Yahoo]")
except Exception:
    pass

theme.panel_bar("CAPE — the missing anchor, honestly", "no free feed")
st.markdown(
    '<div class="desk-note">Shiller\'s cyclically-adjusted P/E has no '
    'clean free API — his dataset lives as a spreadsheet at Yale '
    '(<a href="http://www.econ.yale.edu/~shiller/data.htm" '
    'target="_blank" style="color:#FF9F1C">econ.yale.edu/~shiller'
    '</a>) and multpl.com charts it. The desk links rather than '
    'scrapes: fragile scrapes that silently break are worse than an '
    'honest link. The reading: CAPE above ~30 has historically meant '
    'thin real returns over the following decade — a statement about '
    'DECADES, never about next quarter.</div>',
    unsafe_allow_html=True)
theme.note("Why no timing claims anywhere on this page: valuation "
           "mean-reverts on horizons longer than any position you'll "
           "hold, and the mechanism (multiple compression) can run "
           "through price OR through time. Book II's framing: "
           "valuation sets the runway, flows and regimes fly the "
           "plane.")
