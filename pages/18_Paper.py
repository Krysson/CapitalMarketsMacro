"""Paper Desk v4.2 — the blotter, brackets, spreads, options."""
import datetime as dt
import json

import pandas as pd
import streamlit as st

from desk import paper, theme

st.set_page_config(page_title="Paper — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · THE PAPER DESK",
    "Paper Desk",
    "Simulated capital, real discipline. Stops and targets are "
    "evaluated whenever the desk looks — a stop is an intention, not "
    "a guarantee; gaps fill at the gap. Options: long single-leg "
    "SPY/QQQ, marked at mid, charged the spread, settled at intrinsic "
    "on expiry. Turn LIVE on while managing.")

book = paper.load_book()
events = paper.reconcile(book)
if events:
    paper.save_book(book)
    for e in events:
        st.warning("RECONCILED · " + e)

open_pos = [p for p in book["positions"] if p["status"] == "open"]
closed = [p for p in book["positions"] if p["status"] == "closed"]

syms = set()
for p in open_pos:
    if p["class"] == "SPREAD":
        syms.update(l["symbol"] for l in p["legs"])
    elif p["class"] == "OPTION":
        pass
    else:
        syms.add(p["symbol"])
marks_map = {s: paper.mark(s) for s in syms}
prior_map = {s: paper.prior_close(s) for s in syms}
for p in open_pos:                       # option marks at bid (exit side)
    if p["class"] == "OPTION":
        q = paper.option_quote(**{k: p["opt"][k2] for k, k2 in
                                  (("und", "und"), ("expiry", "exp"),
                                   ("strike", "k"), ("cp", "cp"))})
        marks_map[p["symbol"]] = q[2] if q else None
        prior_map[p["symbol"]] = None

stats = paper.blotter_stats(book, marks_map, prior_map)

pnl = stats["total_pnl"]
theme.readout(
    theme.GREEN if pnl >= 0 else theme.RED,
    f"EQUITY ${stats['equity']:,.0f} · cash ${book['cash']:,.0f} · "
    f"day {stats['day']:+,.0f} · P&L {pnl:+,.0f} "
    f"({pnl / book['start_cash'] * 100:+.2f}%) · gross "
    f"${stats['gross']:,.0f} · net {stats['net']:+,.0f} · slippage "
    f"${stats['slippage_paid']:,.0f} · {stats['n_open']} open / "
    f"{stats['n_closed']} closed")
theme.note("GROSS is how big you really are; NET is which way you "
           "lean — a calendar spread is large gross, tiny net, which "
           "is the point of the structure. DAY marks against prior "
           f"closes. Book started at ${book['start_cash']:,.0f}.")
st.warning("Local file — resets on redeploy. **Export regularly.**")

# ---------------------------------------------------------- open blotter
if open_pos:
    theme.panel_bar("Open blotter", f"{len(open_pos)} working")
    rows = []
    for p in open_pos:
        m = marks_map.get(p["symbol"]) if p["class"] != "SPREAD" else None
        if p["class"] == "SPREAD":
            u = sum((marks_map.get(l["symbol"], l["entry"]) - l["entry"])
                    * (1 if l["side"] == "LONG" else -1)
                    * p["qty"] * l["mult"] for l in p["legs"])
            basis = mv = None
            dayp = sum((marks_map.get(l["symbol"], 0)
                        - (prior_map.get(l["symbol"]) or
                           marks_map.get(l["symbol"], 0)))
                       * (1 if l["side"] == "LONG" else -1)
                       * p["qty"] * l["mult"] for l in p["legs"]
                       if marks_map.get(l["symbol"]))
        else:
            sign = 1 if p["side"] == "LONG" else -1
            basis = p["entry"] * p["qty"] * p["mult"]
            mv = (m * p["qty"] * p["mult"]) if m else None
            u = ((m - p["entry"]) * sign * p["qty"] * p["mult"]
                 if m else None)
            pc = prior_map.get(p["symbol"])
            dayp = ((m - pc) * sign * p["qty"] * p["mult"]
                    if (m and pc) else None)
        days = (dt.date.today()
                - dt.date.fromisoformat(p["opened"][:10])).days
        rows.append({
            "ID": p["id"], "Symbol": p["symbol"], "Side": p["side"],
            "Qty": p["qty"], "Days": days, "Entry": p["entry"] or None,
            "Mark": m, "Basis $": basis, "Value $": mv,
            "Day $": dayp, "Unrl $": u,
            "Unrl %": (u / basis * 100) if (u is not None and basis)
            else None,
            "Wt %": (abs(mv) / stats["equity"] * 100)
            if (mv and stats["equity"]) else None,
            "Stop": p.get("stop"), "Tgt": p.get("target"),
            "Gen": p["generator"].split(" ")[0],
            "Kill switch": p["kill_switch"][:48]})
    df = pd.DataFrame(rows).set_index("ID")
    st.dataframe(
        theme.neg_red(df.style.format(
            {"Qty": "{:g}", "Entry": "{:,.4f}", "Mark": "{:,.4f}",
             "Basis $": "{:,.0f}", "Value $": "{:,.0f}",
             "Day $": "{:+,.0f}", "Unrl $": "{:+,.0f}",
             "Unrl %": "{:+.1f}", "Wt %": "{:.1f}",
             "Stop": "{:g}", "Tgt": "{:g}"}, na_rep="—")),
        width="stretch", height=min(430, 60 + 36 * len(df)))
    cc1, cc2, cc3 = st.columns([2.2, 3.2, 1.2])
    sel = cc1.selectbox("Close",
                        [p["id"] + " · " + p["symbol"] for p in open_pos])
    pm = cc2.text_input("Exit note (kill switch fire? honored?)")
    if cc3.button("CLOSE", width="stretch"):
        ok, msg = paper.close_position(book, sel.split(" · ")[0], pm)
        (st.success if ok else st.error)(msg)
        if ok:
            paper.save_book(book)
            st.rerun()

# ------------------------------------------------------------- tickets
theme.panel_bar("Order ticket — the fifth gate, enforced",
                "no kill switch, no order")
tab_o, tab_s = st.tabs(["OUTRIGHT / OPTION", "FUTURES SPREAD"])
with tab_o, st.form("ticket", clear_on_submit=False):
    t1, t2, t3, t4 = st.columns([2.4, 1, 1.2, 2])
    sym = t1.text_input("Symbol", placeholder="SPY · ES=F · EURUSD=X · "
                                              "SPY 2026-09-18 700 C")
    side = t2.selectbox("Side", ["LONG", "SHORT"])
    qty = t3.number_input("Qty", min_value=0.0, value=0.0, step=1.0)
    gen = t4.selectbox("Generator", paper.GENERATORS, index=None,
                       placeholder="Which scan produced it?")
    gates = st.multiselect("Gates passed (all five)", paper.GATES)
    ks = st.text_input("Kill switch — 'wrong if [observable] does "
                       "[thing], known within [timeframe]'")
    s1, s2 = st.columns(2)
    stop = s1.number_input("Stop (0 = none) — translate the kill "
                           "switch into a price if it has one",
                           min_value=0.0, value=0.0)
    tgt = s2.number_input("Target (0 = none)", min_value=0.0, value=0.0)
    thesis = st.text_area("Thesis (two sentences)", height=68)
    sub = st.form_submit_button("SUBMIT ORDER", width="stretch")
if sub:
    ok, msg = paper.open_position(
        book, symbol=sym, side=side, qty=qty, generator=gen or "",
        gates=gates, kill_switch=ks, thesis=thesis,
        stop=stop or None, target=tgt or None)
    (st.success if ok else st.error)(msg)
    if ok:
        paper.save_book(book)
        st.rerun()
with tab_s, st.form("spread", clear_on_submit=False):
    l1, l2, l3 = st.columns([2, 2, 1])
    a = l1.text_input("Leg 1", placeholder="CLV26.NYM")
    sa = l1.selectbox("Side 1", ["LONG", "SHORT"])
    b = l2.text_input("Leg 2", placeholder="CLU26.NYM")
    sb = l2.selectbox("Side 2", ["SHORT", "LONG"])
    q = l3.number_input("Qty per leg", min_value=0.0, value=0.0, step=1.0)
    gen2 = st.selectbox("Generator ", paper.GENERATORS, index=None)
    gates2 = st.multiselect("Gates passed (all five) ", paper.GATES)
    ks2 = st.text_input("Kill switch — one switch, one thesis: the "
                        "RELATIONSHIP is the trade")
    th2 = st.text_area("Thesis ", height=68)
    sub2 = st.form_submit_button("SUBMIT SPREAD", width="stretch")
if sub2:
    ok, msg = paper.open_spread(
        book, leg1=a, side1=sa, leg2=b, side2=sb, qty=q,
        generator=gen2 or "", gates=gates2, kill_switch=ks2, thesis=th2)
    (st.success if ok else st.error)(msg)
    if ok:
        paper.save_book(book)
        st.rerun()
theme.note("Futures fill at real multipliers; options fill at "
           "ask/sell at bid — the spread IS the cost, charged "
           "honestly. Futures OPTIONS have no free feed: express via "
           "ETF-option proxies (TLT for rates, GLD for gold, USO for "
           "crude — note the roll drag) or read the listed ones on "
           "the TradingView glass. Manual marks are never coming: "
           "self-reported marks are where paper books lie.")

# ------------------------------------------------------- closed blotter
if closed:
    theme.panel_bar("Closed — the record", f"{len(closed)} trades")
    rows = []
    for p in closed:
        d0 = dt.date.fromisoformat(p["opened"][:10])
        d1 = dt.date.fromisoformat(p["closed"][:10])
        mae, mfe = paper.mae_mfe(p)
        basis = (p["entry"] * p["qty"] * p["mult"]
                 if p["class"] != "SPREAD" else None)
        rows.append({"Closed": p["closed"][:10], "Symbol": p["symbol"],
                     "Side": p["side"], "Days": (d1 - d0).days,
                     "Entry": p["entry"] or None, "Exit": p.get("exit"),
                     "Realized $": p.get("realized"),
                     "Ret %": (p.get("realized", 0) / basis * 100)
                     if basis else None,
                     "MAE $": mae, "MFE $": mfe,
                     "Why": p.get("close_reason", "MANUAL"),
                     "Gen": p["generator"].split(" ")[0]})
    dfc = pd.DataFrame(rows)
    st.dataframe(theme.neg_red(dfc.style.format(
        {"Qty": "{:g}", "Entry": "{:,.4f}", "Exit": "{:,.4f}",
         "Realized $": "{:+,.2f}", "Ret %": "{:+.1f}",
         "MAE $": "{:+,.0f}", "MFE $": "{:+,.0f}"}, na_rep="—")),
        hide_index=True, width="stretch",
        height=min(430, 60 + 36 * len(dfc)))
    theme.note("MAE is the kill-switch auditor: if your max adverse "
               "excursion blew through the level your switch named "
               "and the trade survived to profit, you didn't honor "
               "the switch — you got bailed out, and the blotter "
               "says so. Daily-bar granularity, honestly computed.")
    sc = paper.gen_scorecard(closed)
    if not sc.empty:
        st.dataframe(theme.neg_red(sc.set_index("Generator").style.format(
            {"Win %": "{:.0f}", "Avg win": "{:+,.0f}",
             "Avg loss": "{:+,.0f}", "Profit factor": "{:.2f}",
             "Expectancy": "{:+,.0f}", "Total": "{:+,.2f}"},
            na_rep="—")), width="stretch")
        theme.note("Read COUNTS before sums — small samples for "
                   "months. This table tells you which scans YOU "
                   "read well, which beats knowing which scans are "
                   "'best'.")
    st.download_button(
        "EXPORT BLOTTER (CSV)", dfc.to_csv(index=False),
        file_name="paper_blotter.csv")

# --------------------------------------------------------------- admin
st.divider()
if book.get("log"):
    with st.expander("Activity log"):
        for line in book["log"][:40]:
            st.markdown(f'<div class="desk-note">{line}</div>',
                        unsafe_allow_html=True)
e1, e2, e3 = st.columns([1.6, 2.2, 1.6])
e1.download_button("EXPORT BOOK (JSON)", json.dumps(book, indent=2),
                   file_name="paper_book.json")
up = e2.file_uploader("Restore book", type="json",
                      label_visibility="collapsed")
if up is not None:
    try:
        b = json.loads(up.read())
        assert isinstance(b, dict) and "positions" in b
        paper.save_book(b)
        st.success("Book restored — refresh.")
    except Exception:
        st.error("Could not parse that file.")
with e3:
    cash0 = st.number_input("Reset with capital $", min_value=10_000.0,
                            value=float(paper.DEFAULT_CASH),
                            step=100_000.0)
    if st.button("RESET BOOK"):
        if st.session_state.get("confirm_reset"):
            paper.save_book(paper._empty(cash0))
            st.session_state.pop("confirm_reset", None)
            st.rerun()
        else:
            st.session_state["confirm_reset"] = True
            st.warning("Press again to confirm — erases everything.")
