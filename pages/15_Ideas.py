"""Idea Desk — Ch. 15's gates & generators, wired to the live desk.

Two layers, deliberately separated the way the chapter separates them:
GATES are deterministic screens on live desk data — free to run, no
API cost — that surface CONDITIONS worth a look. The GENERATOR is
Claude, fed the snapshot plus the triggered gates, producing candidate
ideas in positioning grammar with mandatory falsification. Gates find
the weather; the generator drafts the pitch; the Notebook is where a
pitch becomes a position of record.

The whole page sits behind DESK_CHAT_PASSCODE — same gate as the Desk
Analyst — because the generator spends real API credits and because
idea flow is the desk's, not the casual reader's.
"""
import streamlit as st

from desk import analyst, data, history, signals, theme

st.set_page_config(page_title="Ideas — Desk", page_icon="⚡", layout="wide")
theme.header(
    "BOOK I · CH. 15 · IDEA GENERATION",
    "Idea Desk",
    "Gates scan the live desk for conditions; the generator drafts "
    "candidate ideas from what tripped. Every candidate is a hypothesis "
    "for the Notebook's gauntlet, never a recommendation. Training desk "
    "— direction, not advice.")

def _secret(name: str, default: str = "") -> str:
    """st.secrets.get RAISES when no secrets file exists at all (fine on
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


# ------------------------------------------------------------ the gates --
def run_gates() -> list[dict]:
    """Deterministic screens on live data. Each returns
    {name, status: TRIPPED|WATCH|QUIET, line}. All fail-soft."""
    out = []

    def add(name, status, line):
        out.append({"name": name, "status": status, "line": line})

    try:
        hist = data.market_history(period="6mo")
        vix = hist["^VIX"].dropna()
        v3m = hist["^VIX3M"].dropna()
        pair = hist[["^VIX", "^VIX3M"]].dropna()
        ratio = float(pair["^VIX"].iloc[-1] / pair["^VIX3M"].iloc[-1])
        s = ("TRIPPED" if ratio >= 1.0 else
             "WATCH" if ratio >= 0.95 else "QUIET")
        add("Vol regime tripwire", s,
            f"VIX/VIX3M {ratio:.3f} vs the 1.0 line — "
            + ("backwardation: front-end vol bid, stress regime."
               if ratio >= 1.0 else
               "approaching the line — a cross is the regime flip."
               if ratio >= 0.95 else
               "contango, resting state; no panic premium."))
    except Exception:
        pass

    def _ratio_1m(hist, num, den, name, up_txt, dn_txt, trip=-2.0):
        try:
            pair = hist[[num, den]].dropna()
            r = pair[num] / pair[den]
            chg = (float(r.iloc[-1]) / float(r.iloc[-22]) - 1) * 100
            s = ("TRIPPED" if chg <= trip else
                 "WATCH" if chg <= trip / 2 else "QUIET")
            add(name, s, f"{chg:+.2f}% over ~1 month — "
                + (dn_txt if chg <= trip / 2 else up_txt))
        except Exception:
            pass

    try:
        hist  # noqa: F821
        _ratio_1m(hist, "RSP", "SPY", "Breadth (RSP/SPY)",
                  "broad participation holding.",
                  "narrowing leadership — the first warning sign.")
        _ratio_1m(hist, "HYG", "LQD", "Credit confirm (HYG/LQD)",
                  "credit confirming risk appetite.",
                  "junk lagging quality — credit smelling trouble.")
    except Exception:
        pass

    try:
        bundle = data.macro_bundle()
        curve = bundle.get("T10Y2Y")
        if curve is not None and not curve.dropna().empty:
            c = curve.dropna()
            now, m1 = float(c.iloc[-1]), float(c.iloc[-22])
            crossed = (now > 0) != (m1 > 0)
            s = "TRIPPED" if crossed else (
                "WATCH" if abs(now) < 0.10 else "QUIET")
            add("Curve (2s10s)", s,
                f"{now:+.2f}pp now vs {m1:+.2f}pp a month ago — "
                + ("SIGN CHANGE — regime event for rates."
                   if crossed else
                   "hugging zero; a cross is the event."
                   if abs(now) < 0.10 else "no regime change."))
        nl = data.net_liquidity(bundle)
        if not nl.empty and len(nl) > 13:
            chg_bn = (float(nl.iloc[-1]) - float(nl.iloc[-14])) / 1e3
            s = ("TRIPPED" if chg_bn <= -150 else
                 "WATCH" if chg_bn <= -50 else "QUIET")
            add("Liquidity turn", s,
                f"Net liquidity {chg_bn:+,.0f}bn over 13 weeks — "
                + ("draining hard; the tide is going out."
                   if chg_bn <= -150 else
                   "leaking; watch the weekly prints."
                   if chg_bn <= -50 else "not a headwind."))
        sigs = signals.compute_signals(bundle)
        reds = [s_.category for s_ in sigs
                if not s_.loading and s_.score <= 1]
        add("Dial board", "TRIPPED" if reds else "QUIET",
            (f"RED: {', '.join(reds)} — a red dial is Ch. 15's "
             f"cheapest idea seed." if reds
             else " · ".join(f"{s_.category} {s_.score}/4"
                             for s_ in sigs) + " — no red dials."))
    except Exception:
        pass

    try:
        h = history.load()
        if not h.empty and len(h) > 1:
            flips = [d.title() for d in history.DIALS
                     if (history.category(h[f"{d}_score"].iloc[-1])
                         != history.category(h[f"{d}_score"].iloc[-2])
                         and history.category(
                             h[f"{d}_score"].iloc[-1]) is not None)]
            if flips:
                add("Fresh flips (record)", "TRIPPED",
                    f"{', '.join(flips)} changed color on the last "
                    f"recorded session — a fresh flip is exactly when "
                    f"an entry should exist.")
    except Exception:
        pass
    return out


theme.panel_bar("Gates — conditions on the live desk", "no API cost")
gates = run_gates()
if not gates:
    st.warning("No gates could run — data sources unreachable. "
               "Try again shortly.")
else:
    order = {"TRIPPED": 0, "WATCH": 1, "QUIET": 2}
    color = {"TRIPPED": theme.RED, "WATCH": theme.YELLOW,
             "QUIET": theme.GREEN}
    for g in sorted(gates, key=lambda x: order[x["status"]]):
        theme.readout(color[g["status"]],
                      f"{g['status']} · {g['name'].upper()} — {g['line']}")
theme.note("A gate is a CONDITION, not an idea: Ch. 15's point is that "
           "ideas come from divergences the crowd hasn't priced, and "
           "gates only tell you where to look. TRIPPED = look today; "
           "WATCH = look this week; QUIET = the machine has nothing "
           "for you here, which is information too.")

st.markdown(
    '<div class="desk-note">CH. 15 MACHINES — this page currently runs '
    'desk-native gates. To encode the chapter\'s own generators '
    '(screens, prompts, question banks) verbatim, paste the chapter '
    'text into the next build session and they slot in here.</div>',
    unsafe_allow_html=True)

st.divider()

# -------------------------------------------------------- the generator --
theme.panel_bar("Generator — candidate ideas from what tripped",
                "spends API credits")
api_key = _secret("ANTHROPIC_API_KEY")
if not api_key:
    st.error("No ANTHROPIC_API_KEY in app secrets — the generator "
             "needs the same key as the Desk Analyst.")
else:
    model = st.selectbox("Model", ["claude-sonnet-4-6",
                                   "claude-opus-4-8",
                                   "claude-haiku-4-5-20251001"])
    if st.button("⚡ Generate candidates", use_container_width=True):
        with st.spinner("Reading the desk…"):
            snapshot = analyst.desk_snapshot()
        gate_text = "\n".join(f"{g['status']}: {g['name']} — {g['line']}"
                              for g in gates)
        ask = (
            "IDEA GENERATION (Book I Ch. 15 mode). Below are the desk's "
            "gate readings. Produce 2-3 CANDIDATE ideas, prioritizing "
            "TRIPPED then WATCH gates; if everything is QUIET, say the "
            "honest thing — the machine has no edge today — and stop. "
            "For each candidate, strict format: THESIS (two sentences "
            "max — the mispricing and the catalyst/horizon), "
            "POSITIONING (desk grammar + plain-English translation), "
            "EVIDENCE (tied to snapshot readings by name and number, "
            "tiered), WHAT KILLS IT (falsification with the desk's own "
            "tripwires), CROWD (what positioning suggests). These are "
            "hypotheses for the Notebook's gauntlet, not "
            "recommendations. End with the training-desk line.\n\n"
            f"GATE READINGS:\n{gate_text}")
        system, hist_msgs = analyst.build_messages(
            [{"role": "user", "content": ask}], snapshot)
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            with st.chat_message("assistant", avatar="⚡"):
                with client.messages.stream(
                        model=model, max_tokens=1600,
                        system=system, messages=hist_msgs) as stream:
                    safe = (c.replace("$", "\\$")
                            for c in stream.text_stream)
                    reply = st.write_stream(safe)
            st.session_state["last_ideas"] = reply
        except Exception as ex:
            st.error(f"Generator failed: {type(ex).__name__} — check "
                     f"the API key and credits.")
    if st.session_state.get("last_ideas"):
        if st.button("→ Send to Notebook as evidence"):
            st.session_state["prefill_evidence"] = (
                "[GEN] Candidates from the Idea Desk — pick ONE and "
                "run the gauntlet:\n"
                + st.session_state["last_ideas"][:1500])
            st.switch_page("pages/4_Notebook.py")

theme.note("The generator drafts in the analyst's grammar: thesis, "
           "positioning, tiered evidence, mandatory falsification. Its "
           "output is raw material — Ch. 15's discipline is that an "
           "idea only becomes real by surviving the Notebook's gates, "
           "and only becomes record by being published there.")
