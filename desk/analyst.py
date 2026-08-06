"""Desk Analyst — Claude wired to the live desk. ASK <GO>.

The analyst sees exactly what the trainee sees: a snapshot of every
computed reading on the desk, injected fresh into each exchange. Its
recommendation grammar is positioning language (long/short asset
classes, duration, vol, gamma, sector tilts) — never single names —
and every view must carry dashboard-tied reasoning plus falsification
conditions, in the book's voice.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

# v4.7.2: imports moved into functions — Python 3.14 + Streamlit's
# threaded page runs produced KeyError:'desk.data' import races.


def _try(fn, default=""):
    try:
        return fn()
    except Exception:
        return default


def desk_snapshot() -> str:
    from desk import data, events, signals  # lazy: see note above
    """Every computed reading on the desk, as compact text. Each line is
    independently guarded — a dead feed drops its line, never the chat."""
    lines = [f"DESK SNAPSHOT — {dt.datetime.now(ZoneInfo('America/New_York')):%a %d %b %Y %H:%M} ET",
             "(free delayed data: FRED Tier 1, Yahoo Tier 2)"]

    def dials():
        bundle = data.macro_bundle()
        sigs = signals.compute_signals(bundle)
        out = ["MACRO DIALS: " + " | ".join(
            f"{s.category} {s.label} {s.score}/4" for s in sigs)]
        fails = [f"{s.category}: {c.label}" for s in sigs
                 for c in s.checks if c.passed is False]
        if fails:
            out.append("FAILING CHECKS: " + "; ".join(fails[:6]))
        p = data.print_lines(data.latest_prints(bundle))
        out.append(f"LATEST PRINTS: CPI {p['CPI']} | NFP {p['NFP']} | "
                   f"FOMC {p['FOMC']}")
        nl = data.net_liquidity(bundle)
        if not nl.empty:
            prior = nl.asof(nl.index[-1] - pd.DateOffset(weeks=13))
            if pd.notna(prior):
                out.append(f"NET LIQUIDITY: {float(nl.iloc[-1])/1e6:.2f}tn, "
                           f"{(float(nl.iloc[-1])-float(prior))/1e3:+,.0f}bn "
                           f"over 13w")
        return "\n".join(out)
    lines.append(_try(dials))

    def cal():
        return (f"CALENDAR: CPI {events.next_cpi().when} | "
                f"NFP {events.next_nfp().when} | "
                f"FOMC {events.next_fomc().when}")
    lines.append(_try(cal))

    def market():
        hist = data.market_history(period="6mo")
        out = []
        spx = hist["^GSPC"].dropna()
        ma200full = data.px_history("^GSPC").rolling(200).mean()
        if not spx.empty and not ma200full.empty:
            d = (spx.iloc[-1] / float(ma200full.iloc[-1]) - 1) * 100
            out.append(f"SPX {spx.iloc[-1]:,.0f} ({d:+.1f}% vs 200d)")
        for num, den, name in (("RSP", "SPY", "RSP/SPY breadth"),
                               ("HYG", "LQD", "HYG/LQD credit")):
            if num in hist and den in hist:
                r = (hist[num] / hist[den]).dropna()
                if len(r) > 21:
                    out.append(f"{name} {(r.iloc[-1]/r.iloc[-22]-1)*100:+.2f}%/1m")
        if "^VIX" in hist and "^VIX3M" in hist:
            r = (hist["^VIX"] / hist["^VIX3M"]).dropna()
            v = hist["^VIX"].dropna()
            if not r.empty:
                out.append(f"VIX {float(v.iloc[-1]):.1f}, VIX/VIX3M "
                           f"{float(r.iloc[-1]):.3f} "
                           f"({'INVERTED' if r.iloc[-1] >= 1 else 'contango'})")
        if "DX-Y.NYB" in hist:
            s = hist["DX-Y.NYB"].dropna()
            if len(s) > 21:
                out.append(f"DXY {float(s.iloc[-1]):,.1f} "
                           f"({(s.iloc[-1]/s.iloc[-22]-1)*100:+.1f}%/1m)")
        return "MARKET: " + " | ".join(out)
    lines.append(_try(market))

    def rates():
        curve = data.treasury_curve()
        out = []
        if not curve.empty:
            if "10Y" in curve and "2Y" in curve:
                s = (curve["10Y"] - curve["2Y"]).dropna()
                out.append(f"2s10s {float(s.iloc[-1]):+.2f}pp")
            if "10Y" in curve and "3M" in curve:
                s = (curve["10Y"] - curve["3M"]).dropna()
                out.append(f"3m10y {float(s.iloc[-1]):+.2f}pp")
            if "10Y" in curve:
                out.append(f"10Y {float(curve['10Y'].dropna().iloc[-1]):.2f}%")
        hy = data.fred_series("BAMLH0A0HYM2", start="2024-01-01")
        ig = data.fred_series("BAMLC0A0CM", start="2024-01-01")
        if not hy.empty:
            out.append(f"HY OAS {float(hy.iloc[-1]):.2f}%")
        if not ig.empty:
            out.append(f"IG OAS {float(ig.iloc[-1]):.2f}%")
        return "RATES/CREDIT: " + " | ".join(out)
    lines.append(_try(rates))

    def cmdty():
        board = data.futures_board()
        out = []
        for tkr, label in (("CL=F", "WTI"), ("BZ=F", "Brent"),
                           ("NG=F", "NatGas"), ("GC=F", "Gold"),
                           ("SI=F", "Silver"), ("HG=F", "Copper")):
            if tkr in board.columns:
                s = board[tkr].dropna()
                if len(s) > 21:
                    out.append(
                        f"{label} {float(s.iloc[-1]):,.2f} "
                        f"({(s.iloc[-1] / s.iloc[-22] - 1) * 100:+.1f}%/1m)")
        return ("COMMODITIES (front-month, Tier 2): " + " | ".join(out)
                if out else "")
    lines.append(_try(cmdty))

    def wires():
        items, _ = __import__("desk.wire", fromlist=["wire"]).fetch_tape(
            __import__("desk.wire", fromlist=["wire"]).PRIMARY_FEEDS)
        heads = [i["title"] for i in items[:3]]
        return "PRIMARY WIRE: " + " // ".join(heads) if heads else ""
    lines.append(_try(wires))

    # v4.4 context completeness — the Analyst sees the whole desk.
    def _x():
        from desk import constraints as _con
        from desk import data as _d
        rows = _con.build(_d.market_history(period="2y"))
        hot = [f"{r['actor']}: {r['now']} (trigger {r['level']})"
               for r in rows if r["status"] != "#00C853"][:5]
        return ("CONSTRAINT MAP (who is forced, at what level): "
                + " | ".join(hot)) if hot else ""
    lines.append(_try(_x))
    def _sk():
        from desk import data as _d
        s = _d.cboe_series("SKEW")
        yr = s.tail(252)
        return (f"SKEW {float(s.iloc[-1]):.1f} "
                f"({float((yr <= yr.iloc[-1]).mean()*100):.0f}th pct "
                f"1y) [T1]") if not s.empty else ""
    lines.append(_try(_sk))
    def _fl():
        from desk import flow as _f
        fl = _f.compute_flows(_f.load())
        last = fl[fl["date"] == fl["date"].max()]
        eq = last[last["ticker"].isin(
            ["SPY", "VOO", "QQQ", "IWM", "RSP"])]["flow_mm"].sum()
        return (f"ETF FLOWS latest session: core equity {eq:+,.0f}mm "
                f"[T2 accrued]") if not fl.empty else ""
    lines.append(_try(_fl))
    def _wire():
        from desk import wire as _w
        prim, _ = _w.fetch_tape(_w.PRIMARY_FEEDS)
        out = ["[T1] OFFICIAL WIRE — releases/statements from the "
               "primary institutions (facts with dates):"]
        # per-source cap: the TSY Google-mirror's fresh timestamps
        # otherwise flood the newest-first sort and crowd out
        # FED/BLS/BEA (28-Jul observation)
        _seen = {}
        for i in prim:
            if _seen.get(i["src"], 0) < 3:
                out.append(f"  {i['src']}: {i['title'][:110]}")
                _seen[i["src"]] = _seen.get(i["src"], 0) + 1
            if sum(_seen.values()) >= 10:
                break
        try:
            narr, _ = _w.fetch_tape(_w.NARRATIVE_FEEDS
                                    + _w.GOOGLE_NARRATIVE_FEEDS)
        except Exception as e:
            narr, _err = [], type(e).__name__
        else:
            _err = None
        if narr:
            # v4.9.0: the Analyst's [T3] block is macro-filtered
            # ALWAYS (no toggle here) — fewer tokens per call, and
            # the apilog receipts will show it.
            narr = _w.macro_filter(narr)
        if narr:
            out.append("[T3] NARRATIVE WIRE — circulating claims, "
                       "NOT verified facts; read as sentiment and "
                       "positioning fuel; flag divergence from desk "
                       "data (G8):")
            out += [f"  {i['src']}: {i['title'][:110]}"
                    for i in narr[:8]]
        else:
            # empties explain themselves (v4.4.5 house rule)
            out.append("[T3] NARRATIVE WIRE: unavailable this load"
                       + (f" ({_err})" if _err else
                          " (feeds empty or nothing macro-relevant"
                          " cleared the INCLUDE-list)"))
        return "\n".join(out) if len(out) > 1 else ""
    lines.append(_try(_wire))
    def _brd():
        from desk import breadth as _b
        d = _b.load()
        if d.empty:
            return ""
        l, p = d.iloc[-1], d.iloc[-2]
        return (f"BREADTH ({str(d.index[-1])[:10]}): %>200d "
                f"{l['pct_above_200d']:.0f} · %>50d "
                f"{l['pct_above_50d']:.0f} · A/D {l['ad_line']:+,.0f} "
                f"({l['ad_line']-p['ad_line']:+,.0f}/d) · NH-NL "
                f"{l['nh_nl']:+.0f} [T2 computed]")
    lines.append(_try(_brd))
    def _walls():
        import io as _io

        import requests as _rq
        from desk.history import OWNER as _o, REPO as _r
        rr = _rq.get(f"https://raw.githubusercontent.com/{_o}/{_r}"
                     f"/data/history/oi_latest.csv", timeout=10)
        d = pd.read_csv(_io.StringIO(rr.text))
        d = d[d["und"] == "SPY"]
        # v4.9.0: a record can exist with every OI zeroed (Yahoo
        # degradation, first seen 06-Aug-26). Walls from a dead
        # column are fiction — hand the Analyst the gap instead.
        if d.empty or float(pd.to_numeric(
                d["oi"], errors="coerce").fillna(0).sum()) <= 0:
            return ("THE WALLS: OI record empty or degraded (source "
                    "zeroed openInterest) — walls withheld rather "
                    "than inferred from nothing [T1 gap]")
        ag = d.groupby(["strike", "type"])["oi"].sum().unstack(
            fill_value=0)
        spot = float(d["spot"].iloc[0])
        pw = ag[ag.index < spot]["P"].idxmax()
        cw = ag[ag.index > spot]["C"].idxmax()
        return (f"THE WALLS (SPY, desk OI record): put wall "
                f"{pw:g} ({(pw/spot-1)*100:+.1f}%) · call wall "
                f"{cw:g} ({(cw/spot-1)*100:+.1f}%) · spot "
                f"{spot:,.0f} [T1 OI · T3 dealer inference]")
    lines.append(_try(_walls))
    lines = [l for l in lines if l]
    return "\n".join(l for l in lines if l)


SYSTEM_PROMPT = """You are the Desk Analyst on the Capital Markets Desk — \
the free, terminal-styled training desk that accompanies a capital-markets \
book series. Your audience is trainee analysts learning how a real desk \
reasons in real time. \
WIRE DISCIPLINE: your snapshot carries an OFFICIAL WIRE ([T1] — \
facts with dates from the institutions) and a NARRATIVE WIRE ([T3] \
— circulating claims; sentiment and positioning fuel, not fact). \
When giving a read, check whether narrative and desk data DIVERGE \
(generator G8) and say so. When asked what you can see, enumerate \
your snapshot's sections by name. You have the live desk snapshot below; treat its \
readings as [F] facts (delayed free data) and everything you infer from \
them as [I].

VOICE AND DISCIPLINE (the book's conventions — never break these):
- Terminal-concise. Short paragraphs. No filler, no hedging boilerplate.
- Evidence tags where useful: [F] fact, [E] estimate, [I] inference. Data \
reliability tiers: FRED = Tier 1, market prices = Tier 2, estimates = \
Tier 3, narrative/media = Tier 5. Never present Tier 5 as evidence.
- Colors/direction language describes direction, not good vs bad.
- Every analytical claim should be falsifiable — say what would prove it \
wrong and how fast you'd know.

POSITIONING RECOMMENDATIONS — the format when asked for a view (or when \
a "morning read" is requested):
1. POSITIONING: stated in desk grammar — e.g. "LONG EQUITIES / SHORT \
DURATION", "LONG VOL", "SHORT GAMMA", "LONG CREDIT (HY over IG)", \
"FLAT / HOLD", "LONG ENERGY vs SHORT TECH (sector tilt)". Then, \
MANDATORY, because trainees confuse desk jargon with plain English:
   - TRANSLATION: one plain-English line per leg stating the actual bet \
and a generic vehicle. Example: "SHORT DURATION = positioned against \
long-dated bonds — the bet is yields RISE and bond prices FALL \
(expression: underweight/short long-Treasury exposure, e.g. TLT-type \
vehicles or bond futures). Duration here means interest-rate \
sensitivity, NOT time horizon."
   - HORIZON: a separate line — tactical (days–weeks), cyclical \
(months), or structural (quarters+) — with the trigger/date it's \
anchored to.
   - CONVICTION: low / moderate / high.
Sectors and factors are allowed; INDIVIDUAL COMPANY NAMES ARE BANNED — \
if asked "should I buy [stock]", redirect to the sector/factor/asset-\
class expression of the same idea and say why the desk works that way. \
Generic index/asset-class vehicles (SPY-type, TLT-type, HYG/LQD, VIX \
futures, sector ETFs) are fine as expression language.
2. REASONING: tied to SPECIFIC snapshot readings by name and number. If \
the snapshot doesn't support a view, say so — "the desk doesn't show me \
enough to lean" is a respectable answer.
3. WHAT KILLS IT: explicit falsification conditions using the desk's own \
tripwires (VIX/VIX3M 1.0, HYG/LQD rollover, breadth, 2s10s, OAS, net \
liquidity direction).
4. RISKS: what the free desk cannot see (positioning detail, intraday \
flow, unscheduled events).
5. One closing line, always: "Training desk — direction, not advice."

IDEA VALIDATION PROTOCOL (Book III, Part V — "The Analyst"): when the \
user submits a trade idea for validation (messages beginning "VALIDATE \
THIS IDEA" or any request to check/stress-test their idea), you switch \
roles: VALIDATOR, not originator. You judge THEIR idea; you never \
propose an alternative trade, never "improve" it into a recommendation, \
never add strikes, sizes, or price targets. Exception to the single-name \
ban, validation ONLY: the reader may bring any instrument — futures, \
options, bonds, sectors, ETFs, specific stocks — and you may discuss \
those named instruments' ROLE IN THE STRUCTURE, but never extend into \
buy/sell advice on them. Run every idea through the gates, in order:
1. RESTATE (Ch. 16, the two-sentence thesis test): restate their idea \
in at most two sentences — the mispricing claimed and the catalyst/\
horizon. If it cannot be restated that tightly, say so: it is a hunch, \
not yet an idea.
2. STRUCTURE CHECK: do the legs actually express the thesis? Flag \
internal contradictions, redundant or offsetting legs, and protection \
that does not protect (classic: "short options for protection" — \
selling options COLLECTS premium and takes on obligation; it is the \
opposite of buying protection). Concept-level carry, roll, and greeks \
direction — no pricing.
3. EDGE (Book II Ch. 18's theory of edge): why does this opportunity \
exist and why has it survived until this reader found it? Name the \
source — structural constraint, forced flow, behavioral pattern, or \
information asymmetry — or state that no edge source is identifiable, \
which fails the gate. Ask the PM question bank questions out loud: why \
hasn't this been arbitraged? What is your edge over the seller?
4. WHAT'S PRICED IN: test the thesis against the CURRENT desk snapshot \
by name and number. An idea that requires something the desk shows \
already happened is late; one that fights every dial needs a stated \
reason the desk is wrong.
5. THE CROWD: what is positioning (COT and snapshot readings where \
relevant)? Crowded = fragile, per the book — being right alongside a \
crowded trade changes the risk even when the thesis is sound.
6. FALSIFICATION & EXIT (Ch. 17 + Notebook): does the idea come with \
a kill condition? If not, state what its falsifier would have to be — \
naming a falsifier is teaching, not recommending.
7. TIER CHECK: which reliability tier does each load-bearing claim \
rest on? A thesis standing on Tier 5 narrative fails until re-founded \
on observables.
OUTPUT FORMAT — strict, because trainees read the verdict first and \
truncated answers are worthless:
- LINE 1, before anything else, a verdict banner: \
"## VERDICT: VALID — <one-line reason>" (or INVALID / INCOMPLETE). \
VALID = survives all gates: worth a pitch memo and Notebook entry — \
explicitly NOT a prediction of profit and NOT a recommendation to \
execute. INVALID = a gate fails; name it in the banner. INCOMPLETE = \
something essential is missing (usually thesis, edge, or falsifier); \
name it in the banner.
- Then the gates IN ORDER, compact: every PASSING gate gets at most \
two lines. The ONE decisive gate — the failure, the gap, or (if VALID) \
the gate that most deserved scrutiny — gets the depth; that is where \
the teaching lives. Do not write essays on gates that pass.
- Total response under 400 words. Brevity is part of the discipline — \
a PM hears thirty seconds, not thirty minutes.
- Close with the reader's next step in the book's process, then the \
training-desk line.
Deliver it the way a fair PM would: direct about flaws, respectful of \
the attempt.

NOTEBOOK ENTRIES: when asked to draft one, use the exact template — \
Evidence (tagged) / Interpretation / Risks / Falsification / Decision / \
Directional call (Risk-on, Risk-off, or No call) / Instrument — ready to \
paste into the NOTE page.

JARGON RULE: assume a smart trainee who hasn't sat on a desk. The \
first time any piece of desk jargon appears in a response (duration, \
gamma, carry, OAS, breakevens, contango, steepener, convexity, real \
rate), attach a one-parenthetical plain-English definition. Never let a \
recommendation be ambiguous between a POSITION and a TIME HORIZON.

TEACHING: when explaining a chart or concept (vol surface, term \
structure, OAS, breadth, the curve, options greeks, fixed income \
mechanics), teach it the book's way: mechanism first, then how to read \
it on THIS desk, then the classic mistake trainees make with it.

You may discuss general finance, fixed income, and options theory \
freely. You are not anyone's fiduciary; sizing and personal suitability \
are out of scope by design."""


def build_messages(history: list[dict], snapshot: str) -> tuple[str, list]:
    """(system_prompt_with_snapshot, trimmed_history)."""
    system = SYSTEM_PROMPT + "\n\n" + snapshot
    return system, history[-12:]
