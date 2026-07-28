"""Idea Desk — Chapter 15's eight generators and five gates, live.

The chapter's thesis, encoded: ideas expire, generators don't. The
scans hunt time-stamped CHANGES — divergences that just opened,
positioning that just hit an extreme, catalysts inside the window,
tripwires that just crossed — so their output is timely by
construction. The desk automates every generator it can compute and
honestly labels MANUAL the ones that live in your own reading (the
constraint map, the flow tracker, the narrative ear).

The funnel is the chapter's five gates, and the bar does not move:
named edge source, dated why-now, written kill switch, honest
expression, survivable size. Most days zero candidates clear all five
— that is the system functioning. One generator firing is a question;
two firing on the same object is a candidate. The scan log — one line
per generator, ESPECIALLY the "nothing" lines — is the professional
product, and it ships to the Notebook in one click.

Passcode-gated (DESK_CHAT_PASSCODE): the generator spends API credits,
and idea flow is the desk's, not the casual reader's.
"""
import datetime as dt

import streamlit as st

from desk import (analyst, constraints, data, events, history,
                  signals, theme)

st.set_page_config(page_title="Ideas — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · CH. 15 · FINDING THE TRADE",
    "Idea Desk",
    "Eight generators, run like farming, not lightning. One firing is a "
    "question; two on the same object is a candidate; five gates decide "
    "what's pitch-ready. \"Nothing clears the bar today\" is a "
    "professional answer. Training desk — direction, not advice.")


def _secret(name: str, default: str = "") -> str:
    """st.secrets.get RAISES when no secrets file exists (fine on
    Cloud, fatal locally) — wrap it so the page runs anywhere."""
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


# ------------------------------------------------------- the passcode ----
passcode = _secret("DESK_CHAT_PASSCODE")
if passcode and not st.session_state.get("ideas_ok"):
    entered = st.text_input("Desk passcode", type="password")
    if entered and entered == passcode:
        st.session_state["ideas_ok"] = True
        st.rerun()
    elif entered:
        st.error("Wrong passcode.")
    st.stop()
if not passcode:
    st.markdown('<div class="desk-note" style="color:#FFD75E">No '
                'DESK_CHAT_PASSCODE set — anyone who finds this public '
                'page can run the generator on your API credits. Add '
                'one in secrets.</div>', unsafe_allow_html=True)


# ----------------------------------------------------- the 8 generators --
# Each returns {name, status, line, lies} — status in
# TRIPPED / WATCH / QUIET / MANUAL. All fail-soft; a dead feed drops
# its automated reading, never the page.

def run_generators() -> list[dict]:
    out = []

    def add(name, status, line, lies):
        out.append({"name": name, "status": status,
                    "line": line, "lies": lies})

    hist = mkt = None
    try:
        mkt = data.market_history(period="1y")
    except Exception:
        pass
    try:
        hist = history.load()
    except Exception:
        pass

    # G1 — Divergence: gauges that normally agree, disagreeing fresh.
    try:
        msgs, status = [], "QUIET"
        spx = mkt["^GSPC"].dropna()
        spx_1m = (float(spx.iloc[-1]) / float(spx.iloc[-22]) - 1) * 100
        for num, den, label in (("RSP", "SPY", "breadth (RSP/SPY)"),
                                ("HYG", "LQD", "credit (HYG/LQD)")):
            pair = mkt[[num, den]].dropna()
            r = pair[num] / pair[den]
            r_1m = (float(r.iloc[-1]) / float(r.iloc[-22]) - 1) * 100
            if spx_1m > 0 and r_1m < -1.0:
                msgs.append(f"index +{spx_1m:.1f}% while {label} "
                            f"{r_1m:+.1f}% over ~1m — fresh disagreement")
                status = "TRIPPED"
        mv = mkt[["^MOVE", "^VIX"]].dropna()
        if len(mv) > 22:
            move_1m = (float(mv["^MOVE"].iloc[-1])
                       / float(mv["^MOVE"].iloc[-22]) - 1) * 100
            vix_1m = (float(mv["^VIX"].iloc[-1])
                      / float(mv["^VIX"].iloc[-22]) - 1) * 100
            if move_1m - vix_1m > 10:
                msgs.append(f"bond vol {move_1m:+.0f}% vs equity vol "
                            f"{vix_1m:+.0f}% over ~1m — the bond market "
                            f"refusing to celebrate")
                status = "TRIPPED"
        add("G1 · Divergence scan", status,
            "; ".join(msgs) if msgs else
            f"price, breadth, credit, and the two vol markets currently "
            f"agree (SPX {spx_1m:+.1f}% 1m) — no fresh disagreements.",
            "resolves in EITHER direction, and can stretch for quarters "
            "— why-now is 'it just widened past X' or a dated resolver, "
            "never 'it exists'.")
    except Exception:
        add("G1 · Divergence scan", "MANUAL",
            "market data unreachable — run RSP/SPY, HYG/LQD, "
            "MOVE-vs-VIX, breadth-vs-price by eye.",
            "resolves in either direction; duration can be quarters.")

    # G2 — Crowding: COT five-year percentiles on core contracts.
    try:
        flags, quiet = [], []
        for code in ("ES", "ZN", "VX", "CL"):
            cftc, label, kind = data.COT_CODES[code]
            df = data.cot_series(cftc, kind)
            if df.empty or len(df) < 60:
                continue
            s = df["net_mm"].tail(260)
            pct = float((s <= s.iloc[-1]).mean() * 100)
            if pct >= 95 or pct <= 5:
                side = "long" if pct >= 95 else "short"
                flags.append(f"{label} speculative net at the "
                             f"{pct:.0f}th pct — crowded {side}; "
                             f"asymmetric reaction to news")
            else:
                quiet.append(f"{code} {pct:.0f}th")
        add("G2 · Crowding scan",
            "TRIPPED" if flags else "QUIET",
            "; ".join(flags) if flags else
            ("no 5y-percentile extremes on core contracts ("
             + ", ".join(quiet) + ")." if quiet else
             "COT unreachable — check the Futures page."),
            "crowded trades are crowded because they're WORKING and can "
            "work for years — a conditions read, not a signal; it "
            "trades only when another generator supplies the dated "
            "trigger (the yen, July 2024).")
    except Exception:
        add("G2 · Crowding scan", "MANUAL",
            "COT unreachable — read percentiles on the Futures page.",
            "an extreme alone is a wood-chipper; needs a dated trigger.")

    # G3 — Catalyst: what's inside 14 days; the mispricing is manual.
    try:
        evs = []
        for f, tag in ((events.next_cpi, "CPI"), (events.next_nfp, "NFP"),
                       (events.next_fomc, "FOMC")):
            d = f().days_until
            if d is not None and 0 <= d <= 14:
                evs.append(f"{tag} in {d}d")
        add("G3 · Catalyst scan",
            "WATCH" if evs else "QUIET",
            (("inside the window: " + ", ".join(evs) + " — now the real "
              "question: what's PRICED for it (event-day options), and "
              "is the priced distribution the wrong size or shape?")
             if evs else
             "nothing scheduled inside 14 days — the calendar carries "
             "no edge anyway; only its mispricing does."),
            "the calendar ALWAYS offers a trade and most events are "
            "priced correctly — 'CPI is Thursday' is a fact, not an "
            "idea; scheduled vol is noise until proven otherwise.")
    except Exception:
        add("G3 · Catalyst scan", "MANUAL",
            "event calendar unreachable — check the ECO page.",
            "most scheduled events are priced correctly.")

    # G4 — Constraint map: rewards actual reading; the desk can only
    # keep the standing question in front of you.
    try:
        _hot = [r for r in constraints.build(
            data.market_history(period="2y"))
            if r["status"] != theme.GREEN]
    except Exception:
        _hot = []
    if _hot:
        _rb = any(r["status"] == theme.RED for r in _hot)
        add("G4 · Constraint-map scan",
            "TRIPPED" if _rb else "WATCH",
            "Trigger zones live — "
            + "; ".join(f"{r['actor'].split(' (')[0]}: {r['now']}"
                        for r in _hot[:3]) + ". "
            "The map computed it — now do "
            "the reading the machine can't (whose flow, how big, "
            "already in price?).",
            "the map's thresholds are estimates — a level being near "
            "does not mean the flow is large, or that it isn't "
            "already priced.")
    else:
        add("G4 · Constraint-map scan", "MANUAL — map all green",
        "standing question — did anything in the news change WHO is "
        "forced to do WHAT, at WHAT level? Margin methodologies, "
        "mandates, index rules, collateral triggers. Map entries go to "
        "the Notebook tagged [E] with a zone, not a level.",
        "timing, chronically — a mapped spring is a watchlist entry, "
        "not a position; it graduates when price nears the trigger or "
        "a catalyst makes it imminent (LDI, 2022; short-vol, 2017-18).")

    # G5 — Regime transition: the desk's tripwires, pre-decided.
    try:
        msgs, status = [], "QUIET"
        pair = mkt[["^VIX", "^VIX3M"]].dropna()
        ratio = float(pair["^VIX"].iloc[-1] / pair["^VIX3M"].iloc[-1])
        if ratio >= 1.0:
            msgs.append(f"VIX/VIX3M {ratio:.3f} — INVERTED: the "
                        f"calm-regime playbook is void (Feb 24, 2020)")
            status = "TRIPPED"
        elif ratio >= 0.95:
            msgs.append(f"VIX/VIX3M {ratio:.3f} — approaching the 1.0 "
                        f"line")
            status = "WATCH"
        spx = mkt["^GSPC"].dropna()
        ma200 = spx.rolling(200).mean()
        above = float(spx.iloc[-1]) >= float(ma200.iloc[-1])
        was_above = float(spx.iloc[-6]) >= float(ma200.iloc[-6])
        if above != was_above:
            msgs.append(f"price crossed the 200-day this week "
                        f"({'above' if above else 'below'}) — trend "
                        f"regime changed")
            status = "TRIPPED"
        bundle = data.macro_bundle()
        curve = bundle.get("T10Y2Y")
        if curve is not None and not curve.dropna().empty:
            c = curve.dropna()
            if (float(c.iloc[-1]) > 0) != (float(c.iloc[-6]) > 0):
                msgs.append("2s10s changed sign this week — rates "
                            "regime event")
                status = "TRIPPED"
        if hist is not None and not hist.empty and len(hist) > 1:
            flips = [d.title() for d in history.DIALS
                     if (history.category(hist[f"{d}_score"].iloc[-1])
                         != history.category(hist[f"{d}_score"].iloc[-2])
                         and history.category(
                             hist[f"{d}_score"].iloc[-1]) is not None)]
            if flips:
                msgs.append(f"dial flip on the record: {', '.join(flips)}")
                status = "TRIPPED"
        if not msgs:
            msgs.append(f"no crossings — VIX/VIX3M {ratio:.3f}, price "
                        f"{'above' if above else 'below'} the 200-day, "
                        f"dials unchanged")
        add("G5 · Regime-transition scan", status, "; ".join(msgs),
            "whipsaw — crossings re-cross, some inversions last two "
            "days; the discipline is symmetric pre-commitment and "
            "small size at fresh crossings.")
    except Exception:
        add("G5 · Regime-transition scan", "MANUAL",
            "tripwire data unreachable — check VOL and RATES pages.",
            "whipsaw; symmetric pre-commitment is the protection.")

    # G6 — Flow anomaly: automated from the desk's accrued record;
    # the BlockLog half stays manual by nature.
    try:
        from desk import flow as _flow
        fl = _flow.compute_flows(_flow.load())
        if fl.empty:
            raise ValueError("no record yet")
        stk = _flow.streaks(fl)
        gd = _flow.group_day(fl)
        eq = float(gd.reindex(["Sector", "Broad"])["net_mm"].sum()) \
            if not gd.empty else 0.0
        fi = (float(gd.loc["Fixed Income", "net_mm"])
              if not gd.empty and "Fixed Income" in gd.index else 0.0)
        msgs, status = [], "QUIET"
        if not stk.empty:
            top = stk.iloc[0]
            msgs.append(f"{len(stk)} live streak(s) — biggest "
                        f"{top['name']} ${top['total_mm']:+,.0f}mm "
                        f"over {top['days']} sessions")
            status = "TRIPPED"
        if eq <= -1500 and fi >= 500:
            msgs.append(f"rotation signature TODAY: equity "
                        f"${eq:,.0f}mm out / fixed income "
                        f"${fi:+,.0f}mm in (the July 15 pattern)")
            status = "TRIPPED"
        if not msgs:
            msgs.append(f"no streaks or signatures on "
                        f"{fl['date'].nunique()} accrued sessions")
        msgs.append("manual remainder: the BlockLog — clustered "
                    "one-sided prints vs the midpoint")
        add("G6 · Flow-anomaly scan", status, "; ".join(msgs),
            "noise, constantly — rebalances, expiries, one fund's "
            "plumbing; the scan speaks only in streaks and "
            "divergences, and the WHY always carries an [I] tag.")
    except Exception:
        add("G6 · Flow-anomaly scan", "MANUAL",
            "flow record not accrued yet (FLOW page explains) — "
            "meanwhile: any STREAK in the workbook? Any flow-vs-price "
            "divergence extending? Single days don't count (July 15, "
            "2026: −$3bn QQQ / +$1.9bn fixed income on a flat tape "
            "was day one of the signature).",
            "noise, constantly — rebalances, expiries, one fund's "
            "plumbing; the scan speaks only in streaks and "
            "divergences, and the WHY always carries an [I] tag.")

    # G7 — Relative value: extremes on the desk's ratio pairs.
    try:
        flags, readings = [], []
        for num, den, label in (("RSP", "SPY", "RSP/SPY"),
                                ("HYG", "LQD", "HYG/LQD")):
            pair = mkt[[num, den]].dropna()
            r = pair[num] / pair[den]
            pct = float((r <= r.iloc[-1]).mean() * 100)
            readings.append(f"{label} {pct:.0f}th pct (1y)")
            if pct <= 10 or pct >= 90:
                flags.append(f"{label} at the {pct:.0f}th percentile "
                             f"of its 1y range — extreme, but an "
                             f"extreme is an observation, not an "
                             f"activation")
        add("G7 · Relative-value scan",
            "WATCH" if flags else "QUIET",
            "; ".join(flags) if flags else
            "no ratio extremes (" + ", ".join(readings) + ").",
            "'stretched' is not a catalyst and relationships re-rate "
            "permanently — the concentration spread kept stretching "
            "for two YEARS past its 2023 extreme; RV clears the funnel "
            "only paired with a dated driver.")
    except Exception:
        add("G7 · Relative-value scan", "MANUAL",
            "ratio data unreachable — read the pairs on MKT and GC.",
            "stretched is not a catalyst.")

    # G8 — Narrative gap: dials vs the loudest story; the ear is yours.
    try:
        sigs = signals.compute_signals(data.macro_bundle())
        board = " · ".join(f"{s.category} {s.label} {s.score}/4"
                           for s in sigs if not s.loading)
        add("G8 · Narrative-gap scan", "MANUAL",
            f"the instrument panel reads: {board}. Now the manual "
            f"half — what OBSERVABLE does today's loudest story "
            f"implicitly predict, and is it cooperating? (Jan 2023: "
            f"'recession imminent' vs claims at historic lows — the "
            f"gap was the idea.)",
            "sometimes the story is EARLY, not wrong (credit, 2007) — "
            "define in advance which observable converts it from "
            "noise to signal, then respect it. Contrarianism without "
            "a kill switch is a personality disorder, not a strategy.")
    except Exception:
        add("G8 · Narrative-gap scan", "MANUAL",
            "dials unreachable — the scan still runs: story vs "
            "observable, gap = candidate.",
            "sometimes the story is early, not wrong.")
    return out


theme.panel_bar("The eight generators", "Ch. 15 §2 · scans, not signals")
gens = run_generators()
order = {"TRIPPED": 0, "WATCH": 1, "MANUAL": 2, "QUIET": 3}
color = {"TRIPPED": theme.RED, "WATCH": theme.YELLOW,
         "MANUAL": theme.BLUE, "QUIET": theme.GREEN}
for g in sorted(gens, key=lambda x: order[x["status"]]):
    theme.readout(color[g["status"]],
                  f"{g['status']} · {g['name'].upper()} — {g['line']}")
    theme.note(f"How it lies: {g['lies']}")

fired = [g["name"].split("·")[1].strip() for g in gens
         if g["status"] == "TRIPPED"]
if len(fired) >= 2:
    theme.readout(theme.AMBER,
                  f"COINCIDENCE CHECK — {len(fired)} generators firing "
                  f"({', '.join(fired)}). Are any two firing on the "
                  f"SAME OBJECT? One scan firing is a question; two on "
                  f"the same object is a candidate.")

st.divider()

# ------------------------------------------------------- the scan log ----
constraints.render(data.market_history(period="2y"))
st.divider()

theme.panel_bar("The scan log — one line per generator",
                "the empty lines make the full ones credible")
GEN_KEYS = [("g1", "G1 Divergence"), ("g2", "G2 Crowding"),
            ("g3", "G3 Catalyst"), ("g4", "G4 Constraint map"),
            ("g5", "G5 Regime"), ("g6", "G6 Flow"),
            ("g7", "G7 Relative value"), ("g8", "G8 Narrative gap")]
auto = {f"g{i+1}": g["line"] for i, g in enumerate(gens)}
for key, _ in GEN_KEYS:
    if f"log_{key}" not in st.session_state:
        st.session_state[f"log_{key}"] = auto.get(key, "nothing")

with st.form("scanlog", clear_on_submit=False):
    for key, label in GEN_KEYS:
        st.text_input(label, key=f"log_{key}")
    cands = st.text_area(
        "Candidates + gate status", height=110, key="log_cands",
        placeholder="e.g. rotation-out-of-mega-cap (G6+G1). Gates: "
                    "edge ✓ (crowding meets dated flow turn) · why-now "
                    "✓ (yesterday) · kill switch ✓ (flows reverse or "
                    "RSP/SPY rolls over in 2w) · expression ✓ · "
                    "survivable ✓ — WATCH-WITH-INTENT, needs one more "
                    "day of streak.  …or, proudly: NOTHING CLEARS THE "
                    "BAR TODAY.")
    sent = st.form_submit_button("SEND SCAN LOG TO THE NOTEBOOK")
if sent:
    stamp = dt.datetime.now().strftime("%a %d %b %Y %H:%M")
    lines = [f"SCAN LOG — {stamp} (Ch. 15 drill)"]
    lines += [f"{label}: {st.session_state.get(f'log_{key}', 'nothing')}"
              for key, label in GEN_KEYS]
    lines.append(f"Candidates & gates: "
                 f"{st.session_state.get('log_cands') or 'none — '}"
                 f"nothing clears the bar today."
                 if not st.session_state.get("log_cands")
                 else f"Candidates & gates: "
                      f"{st.session_state.get('log_cands')}")
    st.session_state["prefill_evidence"] = "\n".join(lines)
    st.switch_page("pages/4_Notebook.py")
theme.note("The chapter's five gates, verbatim — a candidate passes "
           "ALL of them or goes to the watchlist: (1) NAME THE EDGE "
           "SOURCE — constrained, forced, anchored, or genuinely new; "
           "'people haven't noticed' means people have noticed. "
           "(2) DATE THE WHY-NOW — identical three months ago = fails. "
           "(3) WRITE THE KILL SWITCH — 'wrong if [observable] does "
           "[thing], known within [timeframe]'. (4) FIND THE "
           "EXPRESSION — a payoff that honestly matches the thesis. "
           "(5) CONFIRM SURVIVABLE — a size exists where being wrong "
           "is tuition. Most days, zero candidates clear all five — "
           "that is the system functioning.")

st.divider()

# -------------------------------------------------------- the generator --
theme.panel_bar("Generator — Claude runs the scans with you",
                "spends API credits")
api_key = _secret("ANTHROPIC_API_KEY")
if not api_key:
    st.error("No ANTHROPIC_API_KEY in app secrets — the generator "
             "needs the same key as the Desk Analyst.")
else:
    model = st.selectbox("Model", ["claude-sonnet-4-6",
                                   "claude-opus-4-8",
                                   "claude-haiku-4-5-20251001"])
    if st.button("RUN THE FUNNEL ON TODAY'S SCANS",
                 use_container_width=True):
        with st.spinner("Reading the desk…"):
            snapshot = analyst.desk_snapshot()
        gen_text = "\n".join(
            f"{g['status']}: {g['name']} — {g['line']}" for g in gens)
        ask = (
            "IDEA GENERATION — Book III Ch. 15 mode, strictly. Below "
            "are today's eight generator readings from the live desk. "
            "Your job is the chapter's funnel, not creativity:\n"
            "1. Identify COINCIDENCES — two or more generators firing "
            "on the SAME OBJECT. One scan firing is a question; only a "
            "coincidence is a candidate.\n"
            "2. For each candidate (0-2 of them, never forced), march "
            "it through the FIVE GATES by name: (1) edge source — "
            "constrained / forced / anchored / genuinely new; (2) "
            "dated why-now; (3) kill switch in the canonical sentence "
            "('wrong if [observable] does [thing], known within "
            "[timeframe]'); (4) honest expression in positioning "
            "grammar with plain-English translation; (5) survivable — "
            "does a tuition-sized version exist? A candidate failing "
            "ANY gate goes to the WATCHLIST with a note naming what "
            "would activate it.\n"
            "3. Tag every load-bearing claim [T1]/[T2]/[E]/[I].\n"
            "4. If nothing coincides or nothing clears the gates, say "
            "the chapter's sentence proudly: 'Nothing clears the bar "
            "today' — and list what was checked. That output is a "
            "SUCCESS, not a failure; never force a pitch.\n"
            "End with the training-desk line.\n\n"
            f"TODAY'S GENERATOR READINGS:\n{gen_text}")
        system, hist_msgs = analyst.build_messages(
            [{"role": "user", "content": ask}], snapshot)
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            with st.chat_message("assistant"):
                with client.messages.stream(
                        model=model, max_tokens=1700,
                        system=system, messages=hist_msgs) as stream:
                    safe = (c.replace("$", "\\$")
                            for c in stream.text_stream)
                    reply = st.write_stream(safe)
                try:
                    from desk import apilog
                    _u = stream.get_final_message().usage
                    apilog.log("funnel", _u.input_tokens,
                               _u.output_tokens)
                    st.caption(f"receipt: {_u.input_tokens:,} in / "
                               f"{_u.output_tokens:,} out · logged")
                except Exception:
                    pass
            st.session_state["last_ideas"] = reply
        except Exception as ex:
            st.error(f"Generator failed: {type(ex).__name__} — check "
                     f"the API key and credits.")
    if st.session_state.get("last_ideas"):
        if st.button("→ Send verdicts to the Notebook"):
            st.session_state["prefill_evidence"] = (
                "[GEN] Ch. 15 funnel output — candidates & watchlist:\n"
                + st.session_state["last_ideas"][:1500])
            st.switch_page("pages/4_Notebook.py")

theme.note("Base rates, from the chapter: eight scans daily produce "
           "candidates daily, and most days zero clear all five gates. "
           "Across a week, several will. 'Nothing clears the bar, and "
           "here's what I checked' builds a career; forced pitches end "
           "one — a movable bar is the most expensive trait an analyst "
           "can have. Practice on history: every worked example is a "
           "dated Time Machine exercise (TM <GO>).")
