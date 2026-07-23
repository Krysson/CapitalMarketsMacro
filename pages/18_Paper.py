"""Paper Desk — where ideas that cleared the gates get tested.

The reader stops observing and starts acting: Book III's loop closes
here. learn → scan → gate → pitch → TEST → post-mortem. The ticket is
the fifth gate's enforcement — it refuses any order arriving without
its generator, its gates, and its kill-switch sentence.
"""
import json

import pandas as pd
import streamlit as st

from desk import paper, theme

st.set_page_config(page_title="Paper — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · THE PAPER DESK",
    "Paper Desk",
    "Simulated capital, real discipline. Fills at the desk's mark plus "
    "honest slippage; futures at real contract multipliers; no order "
    "without a kill switch. Turn LIVE on (top right) while managing. "
    "Training desk — paper results are tuition, not evidence of edge.")

book = paper.load_book()
open_pos = [p for p in book["positions"] if p["status"] == "open"]
closed = [p for p in book["positions"] if p["status"] == "closed"]

# one mark pass per page load
marks = {p["symbol"]: paper.mark(p["symbol"]) for p in open_pos}
stats = paper.book_stats(book, marks)

# ------------------------------------------------------------ the book --
pnl = stats["total_pnl"]
theme.readout(
    theme.GREEN if pnl >= 0 else theme.RED,
    f"EQUITY ${stats['equity']:,.0f} · cash ${book['cash']:,.0f} · "
    f"P&L {pnl:+,.0f} ({pnl / book['start_cash'] * 100:+.2f}%) · "
    f"unrealized {stats['unrealized']:+,.0f} · realized "
    f"{stats['realized']:+,.0f} · slippage paid "
    f"${stats['slippage_paid']:,.0f} · {stats['n_open']} open / "
    f"{stats['n_closed']} closed")
theme.note("Slippage paid is tracked on purpose: it is the tax every "
           "idea pays twice, and watching it accumulate teaches sizing "
           "faster than any chapter. Started at "
           f"${book['start_cash']:,.0f}.")

st.warning("Storage note: like the Notebook, this book is a local file "
           "that resets on redeploy — **export it regularly** and "
           "restore to continue.")

# ------------------------------------------------------ open positions --
if open_pos:
    theme.panel_bar("Open positions", f"{len(open_pos)} working")
    rows = []
    for p in open_pos:
        px = marks.get(p["symbol"])
        sign = 1 if p["side"] == "LONG" else -1
        u = ((px - p["entry"]) * sign * p["qty"] * p["mult"]
             if px is not None else None)
        rows.append({
            "ID": p["id"], "Symbol": p["symbol"], "Side": p["side"],
            "Qty": p["qty"], "Entry": p["entry"],
            "Mark": px, "Unrealized $": u,
            "Generator": p["generator"].split(" ")[0],
            "Kill switch": p["kill_switch"][:60]})
    df = pd.DataFrame(rows).set_index("ID")
    st.dataframe(
        theme.neg_red(df.style.format(
            {"Qty": "{:g}", "Entry": "{:,.4f}", "Mark": "{:,.4f}",
             "Unrealized $": "{:+,.0f}"}, na_rep="—")),
        use_container_width=True, height=min(420, 60 + 36 * len(df)))
    theme.note("The kill switch rides next to the P&L on purpose: the "
               "question is never 'is it up?' but 'has the thing I "
               "said would prove me wrong happened?' If it has and "
               "you're still holding, the post-mortem writes itself.")
    cc1, cc2, cc3 = st.columns([2.2, 3.2, 1.2])
    sel = cc1.selectbox("Close position",
                        [p["id"] + " · " + p["symbol"] for p in open_pos])
    pm = cc2.text_input("Exit note (did the kill switch fire? honored?)",
                        placeholder="e.g. falsifier hit Tue — honored, "
                                    "out same day")
    if cc3.button("CLOSE", use_container_width=True):
        ok, msg = paper.close_position(book, sel.split(" · ")[0], pm)
        (st.success if ok else st.error)(msg)
        if ok:
            paper.save_book(book)
            st.rerun()

# ----------------------------------------------------------- the ticket --
theme.panel_bar("Order ticket — the fifth gate, enforced",
                "no kill switch, no order")
with st.form("ticket", clear_on_submit=False):
    t1, t2, t3, t4 = st.columns([2, 1.2, 1.2, 2])
    sym = t1.text_input("Symbol", placeholder="SPY · ES=F · EURUSD=X "
                                              "· BTC-USD")
    side = t2.selectbox("Side", ["LONG", "SHORT"])
    qty = t3.number_input("Qty (contracts/shares/units)",
                          min_value=0.0, value=0.0, step=1.0)
    gen = t4.selectbox("Generator (the idea's source)", paper.GENERATORS,
                       index=None, placeholder="Which scan produced it?")
    gates = st.multiselect("Gates passed (all five, or it's a "
                           "watchlist entry — not an order)",
                           paper.GATES)
    ks = st.text_input(
        "Kill switch — the canonical sentence",
        placeholder="Wrong if [observable] does [thing], known within "
                    "[timeframe]")
    thesis = st.text_area("Thesis (two sentences max — the mispricing "
                          "and the catalyst)", height=70)
    submitted = st.form_submit_button("SUBMIT ORDER",
                                      use_container_width=True)
if submitted:
    ok, msg = paper.open_position(
        book, symbol=sym, side=side, qty=qty, generator=gen or "",
        gates=gates, kill_switch=ks, thesis=thesis)
    (st.success if ok else st.error)(msg)
    if ok:
        paper.save_book(book)
        st.rerun()
theme.note("Futures fill at real contract multipliers — ES is $50 a "
           "point, CL is 1,000 barrels, GC is 100 ounces — so 'one "
           "contract' is a position, not a lottery ticket; the "
           "notional will teach you that once. Slippage is charged "
           "against you on every fill (a tick on futures, basis "
           "points elsewhere). Options land in v4.1 — until then, "
           "express tail views via proxies and say so in the thesis. "
           "Marks are as fresh as the data layer: LIVE toggle on "
           "while managing.")

# ------------------------------------------------------ closed / ledger --
if closed:
    theme.panel_bar("Closed — the record", f"{len(closed)} trades")
    rows = [{"Closed": p.get("closed", "")[:10], "Symbol": p["symbol"],
             "Side": p["side"], "Qty": p["qty"], "Entry": p["entry"],
             "Exit": p.get("exit"), "Realized $": p.get("realized"),
             "Generator": p["generator"].split(" ")[0],
             "Exit note": p.get("post_mortem", "")[:50]}
            for p in closed]
    dfc = pd.DataFrame(rows)
    st.dataframe(
        theme.neg_red(dfc.style.format(
            {"Qty": "{:g}", "Entry": "{:,.4f}", "Exit": "{:,.4f}",
             "Realized $": "{:+,.2f}"}, na_rep="—")),
        hide_index=True, use_container_width=True,
        height=min(420, 60 + 36 * len(dfc)))
    by_gen = (dfc.groupby("Generator")["Realized $"]
              .agg(["count", "sum"]).sort_values("sum", ascending=False))
    st.dataframe(theme.neg_red(
        by_gen.rename(columns={"count": "Trades", "sum": "Realized $"})
        .style.format({"Realized $": "{:+,.2f}"})),
        use_container_width=True)
    theme.note("P&L by generator — over enough trades this table tells "
               "you which scans YOU read well, which is more valuable "
               "than which scans are 'best'. Small samples for months; "
               "read counts before sums, and grade reasoning in the "
               "Notebook, not just outcomes here.")

# ------------------------------------------------------ export / danger --
st.divider()
e1, e2, e3 = st.columns([1.6, 2.2, 1])
e1.download_button("EXPORT BOOK (JSON)", json.dumps(book, indent=2),
                   file_name="paper_book.json")
up = e2.file_uploader("Restore book", type="json",
                      label_visibility="collapsed")
if up is not None:
    try:
        b = json.loads(up.read())
        assert isinstance(b, dict) and "positions" in b
        paper.save_book(b)
        st.success("Book restored — refresh the page.")
    except Exception:
        st.error("Could not parse that file.")
if e3.button("RESET BOOK"):
    if st.session_state.get("confirm_reset"):
        paper.save_book(paper._empty())
        st.session_state.pop("confirm_reset", None)
        st.success("Fresh book. The old record is gone — which is why "
                   "the real one exports first.")
        st.rerun()
    else:
        st.session_state["confirm_reset"] = True
        st.warning("Press RESET BOOK again to confirm — this erases "
                   "everything.")
