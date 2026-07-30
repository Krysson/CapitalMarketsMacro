"""THE OVERNIGHT RECAP (REC/RECAP) — yesterday in English, computed.
Deterministic diff of the desk's own records; free, self-updating.
NARRATE turns facts into prose for one API call (receipt logged)."""
import datetime as dt
import io

import pandas as pd
import requests
import streamlit as st

from desk import breadth, history, theme, wire

st.set_page_config(page_title="Recap — Desk", page_icon="▪",
                   layout="wide")
theme.header("BOOK III · THE OVERNIGHT RECAP", "Overnight Recap",
             "What changed since the last session, assembled from the "
             "record — dials, tape, internals, flows, wire. "
             "Deterministic and free; NARRATE costs one press.")

facts = []
try:
    h = history.load()
    dates = list(h.index[-2:])
    sel = st.selectbox("As of", list(reversed([str(d)[:10] for d in
                       h.index[-30:]])), index=0)
    i = [str(d)[:10] for d in h.index].index(sel)
    row, prev = h.iloc[i], (h.iloc[i - 1] if i > 0 else h.iloc[i])
    facts.append(f"SESSION {sel} (vs {str(h.index[i-1])[:10]})")
    # dials
    flips = []
    for d in ("growth", "inflation", "policy", "liquidity"):
        a, b = int(prev[f"{d}_score"]), int(row[f"{d}_score"])
        if a != b:
            flips.append(f"{d.upper()} {a}/4 → {b}/4")
    facts.append("DIALS: " + ("; ".join(flips) if flips
                 else "no flips — the regime held"))
    # tape
    dspx = (row["spx"] / prev["spx"] - 1) * 100
    facts.append(f"TAPE: SPX {row['spx']:,.0f} ({dspx:+.2f}%) · VIX "
                 f"{row['vix']:.1f} ({row['vix']-prev['vix']:+.1f}) · "
                 f"VIX/VIX3M {row['vix_vix3m']:.2f} "
                 f"({row['vix_vix3m']-prev['vix_vix3m']:+.02f}) · "
                 f"NetLiq {row['net_liq_tn']:.2f}tn")
    if row["vix_vix3m"] >= 1.0 > prev["vix_vix3m"]:
        facts.append("THRESHOLD: VIX/VIX3M crossed ABOVE 1.00 — the "
                     "regime tripwire fired")
except Exception as e:
    facts.append(f"signals record unavailable ({type(e).__name__})")
try:
    b = breadth.load()
    if not b.empty and len(b) >= 2:
        l, p = b.iloc[-1], b.iloc[-2]
        facts.append(
            f"INTERNALS ({str(b.index[-1])[:10]}): %>200d "
            f"{l['pct_above_200d']:.0f} ({l['pct_above_200d']-p['pct_above_200d']:+.0f}) · "
            f"%>50d {l['pct_above_50d']:.0f} · A/D "
            f"{l['ad_line']:+,.0f} ({l['ad_line']-p['ad_line']:+,.0f} "
            f"on the day) · NH−NL {l['nh_nl']:+.0f}")
except Exception:
    pass
try:
    from desk.history import OWNER, REPO
    r = requests.get(f"https://raw.githubusercontent.com/{OWNER}/"
                     f"{REPO}/data/history/oi_footprints.csv",
                     timeout=12)
    if r.ok and r.text.strip():
        fp = pd.read_csv(io.StringIO(r.text))
        recent = fp[fp["date"] == fp["date"].max()]
        if not recent.empty:
            big = recent.nlargest(3, "d_oi")
            facts.append("FOOTPRINTS (" + str(recent["date"].iloc[0])
                         + "): " + "; ".join(
                f"{r_['und']} {r_['expiry']} {r_['strike']:g}"
                f"{r_['type']} +{int(r_['d_oi']):,} OI"
                for _, r_ in big.iterrows()))
except Exception:
    pass
try:
    items, _ = wire.fetch_tape(wire.PRIMARY_FEEDS)
    seen = {}
    heads = []
    for it in items:
        if seen.get(it["src"], 0) < 2:
            heads.append(f"{it['src']}: {it['title'][:90]}")
            seen[it["src"]] = seen.get(it["src"], 0) + 1
        if len(heads) >= 6:
            break
    if heads:
        facts.append("OFFICIAL WIRE: " + " // ".join(heads))
except Exception:
    pass

for f in facts:
    st.markdown(f'<div class="desk-note">{f}</div>',
                unsafe_allow_html=True)
theme.note("Every line above is computed from the desk's own records "
           "— pick any date the record covers. The recap is the Time "
           "Machine's daily edition.")

st.divider()
with st.expander("NARRATE — one API call turns the facts into prose"):
    pw = st.text_input("Passcode", type="password", key="rec_pw")
    if st.button("NARRATE THE SESSION"):
        try:
            if pw != st.secrets.get("DESK_CHAT_PASSCODE", None):
                st.error("Passcode required (same as the Idea Desk).")
            else:
                from anthropic import Anthropic
                client = Anthropic(
                    api_key=st.secrets["ANTHROPIC_API_KEY"])
                with st.chat_message("assistant"):
                    with client.messages.stream(
                        model="claude-sonnet-4-5", max_tokens=900,
                        system="You are the overnight desk anchor for "
                        "a training desk. Turn these computed facts "
                        "into a tight, plain-English morning recap — "
                        "three short paragraphs max: what changed, "
                        "why it matters, what to watch today. No "
                        "advice; direction and mechanism only. Facts "
                        "are the only source — invent nothing.",
                        messages=[{"role": "user",
                                   "content": "\n".join(facts)}]
                    ) as stream:
                        safe = (c.replace("$", "\\$")
                                for c in stream.text_stream)
                        st.write_stream(safe)
                    try:
                        from desk import apilog
                        u = stream.get_final_message().usage
                        apilog.log("recap", u.input_tokens,
                                   u.output_tokens)
                        st.caption(f"receipt: {u.input_tokens:,} in "
                                   f"/ {u.output_tokens:,} out")
                    except Exception:
                        pass
        except Exception as ex:
            st.error(f"Narration failed ({type(ex).__name__}) — "
                     f"check key/credits.")
