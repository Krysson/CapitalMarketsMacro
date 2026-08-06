"""Watchlist (WL/MON) — the funnel's parking lot, scored."""
import pandas as pd
import streamlit as st

from desk import theme, watchlist

st.set_page_config(page_title="Watchlist — Desk", page_icon="▪",
                   layout="wide")
theme.header("BOOK III · WATCHLIST", "Watchlist",
             "Candidates that failed a gate, themes waiting on a "
             "catalyst, levels being stalked. '% since added' scores "
             "your watching. Checked at the morning read — a "
             "watchlist you don't read daily is a graveyard.")

items = watchlist.load()
with st.form("wladd", clear_on_submit=True):
    c1, c2, c3 = st.columns([1.4, 3, 1])
    sym = c1.text_input("Symbol", placeholder="XLE · ZN=F · BTC-USD")
    reason = c2.text_input("Why watching (required)",
                           placeholder="failed gate 2 — no dated "
                                       "why-now; revisit into Aug CPI")
    gen = c3.selectbox("Source", [""] + [g for g in
                       __import__("desk.paper", fromlist=["p"]).GENERATORS])
    trig = st.text_input("Becomes actionable if (optional)",
                         placeholder="reclaims the 50-day · OAS > 3.2")
    if st.form_submit_button("PARK IT"):
        ok, msg = watchlist.add(items, sym, reason, gen, trig)
        (st.success if ok else st.error)(msg)
        if ok:
            watchlist.save(items)
            st.rerun()

if not items:
    st.markdown('<div class="desk-note">Empty. The Idea Desk\'s '
                'rejects and the Quote page\'s ADD button feed this '
                'list.</div>', unsafe_allow_html=True)
else:
    df = watchlist.table(items)
    ev = st.dataframe(
        theme.neg_red(df.style.format(
            {"@ Add": "{:,.2f}", "Last": "{:,.2f}",
             "Since %": "{:+.1f}"}, na_rep="—")),
        hide_index=True, width="stretch",
        height=min(560, 60 + 36 * len(df)),
        on_select="rerun", selection_mode="single-row", key="wl_tbl")
    picked = (ev.selection.rows if ev and hasattr(ev, "selection")
              else [])
    if picked:
        st.session_state["quote_query"] = ("yf",
                                           df.iloc[picked[0]]["Symbol"],
                                           "")
        st.switch_page("pages/6_Quote.py")
    rm = st.selectbox("Remove", [""] + [i["symbol"] for i in items])
    if rm and st.button("REMOVE " + rm):
        watchlist.save([i for i in items if i["symbol"] != rm])
        st.rerun()
    theme.note("Click a row to open it on the Quote page. Entries "
               "with triggers get checked at the 7:45 read — the "
               "desk does not alert on these (your file, your eyes; "
               "promising surveillance that can't happen would be a "
               "lie).")
