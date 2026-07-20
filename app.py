"""Capital Markets Desk — Summary page."""
import pandas as pd
import streamlit as st

from desk import data, signals, theme

st.set_page_config(page_title="Capital Markets Desk", page_icon="📟",
                   layout="wide")

theme.header(
    "THE FREE DESK · DAILY CIRCUIT",
    "Capital Markets Desk",
    "Green = rising / loose · Red = falling / tight · Yellow = mixed. "
    "Colors show direction, not good vs. bad — quick-glance heuristics for a "
    "learning desk, not trading signals or investment advice.")

with st.spinner("Pulling FRED data…"):
    bundle = data.macro_bundle()

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
            <div style="border-radius:10px;padding:18px 16px;
                        background:{theme.PANEL};
                        border-left:4px solid {s.color};min-height:176px">
              <div class="desk-eyebrow" style="color:{theme.MUTED}">
                {s.category}</div>
              <div style="font-family:'Spectral',serif;font-size:1.45rem;
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
                icon = "✅" if c.passed else ("❌" if c.passed is False else "⏳")
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
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.map(
                lambda v: f"color: {theme.GREEN if v > 0 else theme.RED}"
                if isinstance(v, float) else "",
                subset=["Chg %"],
            ).format({"Last": "{:,.2f}", "Chg %": "{:+.2f}"}),
            hide_index=True, height=430, use_container_width=True,
        )

st.markdown('<div class="desk-note">Data: FRED (St. Louis Fed) · Yahoo '
            'Finance, delayed · Pages: Macro / Market / Volatility / '
            'Notebook in the sidebar</div>', unsafe_allow_html=True)
