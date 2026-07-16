"""Capital Markets Desk — Summary page."""
import streamlit as st

from desk import data, signals

st.set_page_config(page_title="Capital Markets Desk", page_icon="📟",
                   layout="wide")

st.title("Capital Markets Desk")
st.caption(
    "Green = rising / loose · Red = falling / tight · Yellow = mixed. "
    "Colors show direction, not good vs. bad. Quick-glance heuristics for a "
    "learning desk — not trading signals or investment advice."
)

with st.spinner("Pulling FRED data…"):
    bundle = data.macro_bundle()

sigs = signals.compute_signals(bundle)

if all(s.loading for s in sigs):
    st.warning(
        "No FRED data loaded. If this persists, add a FRED_API_KEY in "
        "Streamlit secrets (App settings → Secrets):\n\n"
        '`FRED_API_KEY = "your_key_here"`'
    )

cols = st.columns(4)
for col, s in zip(cols, sigs):
    with col:
        st.markdown(
            f"""
            <div style="border-radius:12px;padding:18px 16px;background:{s.color}22;
                        border:1px solid {s.color};min-height:120px">
              <div style="font-size:0.8rem;letter-spacing:0.08em;
                          text-transform:uppercase;opacity:0.8">{s.category}</div>
              <div style="font-size:1.5rem;font-weight:700;color:{s.color}">
                {s.label}</div>
              <div style="opacity:0.75">score {s.score} / 4</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

left, right = st.columns([3, 2])

with left:
    st.subheader("Under the hood")
    st.caption("The four checks behind each signal.")
    for s in sigs:
        with st.expander(f"{s.category} — {s.label} ({s.score}/4)"):
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
        import pandas as pd

        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.map(
                lambda v: f"color: {'#1e9e4a' if v > 0 else '#d64545'}"
                if isinstance(v, float) else "",
                subset=["Chg %"],
            ),
            hide_index=True, height=430, use_container_width=True,
        )

st.caption(
    "Data: FRED (St. Louis Fed) and Yahoo Finance, delayed. "
    "Pages: Macro · Market · Volatility · Notebook — see sidebar."
)
