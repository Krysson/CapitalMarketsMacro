"""Analyst's Notebook — Evidence → Interpretation → Risks → Falsification."""
import datetime as dt
import json
from pathlib import Path

import streamlit as st

import pandas as pd

from desk import data, theme

st.set_page_config(page_title="Notebook — Desk", page_icon="📓", layout="wide")
theme.header("BOOK I · CH. 15", "Analyst's Notebook",
             "Evidence → Interpretation → Risks → Falsification → Decision. "
             "Tag evidence [F] fact, [E] estimate, [I] inference.")

STORE = Path("notebook_entries.json")


def load() -> list[dict]:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text())
        except Exception:
            return []
    return []


def save(entries: list[dict]) -> None:
    STORE.write_text(json.dumps(entries, indent=2))


entries = load()

st.warning(
    "Storage note: on Streamlit Community Cloud this file resets whenever the "
    "app redeploys or restarts. **Download your notebook regularly** and "
    "re-upload to restore.", icon="💾")

with st.form("entry", clear_on_submit=True):
    st.subheader("New entry")
    date = st.date_input("Date", dt.date.today())
    evidence = st.text_area("Evidence", height=140,
                            placeholder="[F] SPX −0.8%, ADD +564, RSP/SPY +1.4% …")
    interpretation = st.text_area("Interpretation", height=110)
    risks = st.text_area("Risks to this read", height=80)
    falsification = st.text_area(
        "Falsification — what proves it wrong, how fast would I know?",
        height=80)
    decision = st.text_input("Decision", placeholder="No action. Carry X forward.")
    cc1, cc2 = st.columns(2)
    call = cc1.selectbox("Directional call (feeds the post-mortem "
                         "scorecard)", ["No call", "Risk-on", "Risk-off"])
    instrument = cc2.text_input("Instrument (optional — default ^GSPC)",
                                placeholder="^GSPC")
    if st.form_submit_button("Save entry"):
        entries.insert(0, {
            "date": str(date), "evidence": evidence,
            "interpretation": interpretation, "risks": risks,
            "falsification": falsification, "decision": decision,
            "call": call, "instrument": instrument.strip() or "^GSPC",
        })
        save(entries)
        st.success("Saved.")

st.divider()

if entries:
    md_lines = []
    for e in entries:
        md_lines += [f"## {e['date']}", "",
                     f"**Evidence**\n\n{e['evidence']}", "",
                     f"**Interpretation**\n\n{e['interpretation']}", "",
                     f"**Risks**\n\n{e['risks']}", "",
                     f"**Falsification**\n\n{e['falsification']}", "",
                     f"**Decision** — {e['decision']}", "", "---", ""]
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download notebook (markdown)",
                       "\n".join(md_lines),
                       file_name="analysts_notebook.md")
    c2.download_button("⬇️ Download backup (JSON)",
                       json.dumps(entries, indent=2),
                       file_name="notebook_backup.json")

uploaded = st.file_uploader("Restore from a previous JSON backup", type="json")
if uploaded is not None:
    try:
        restored = json.loads(uploaded.read())
        save(restored)
        st.success(f"Restored {len(restored)} entries — refresh the page.")
    except Exception:
        st.error("Could not parse that file.")

# ------------------------------------------------- post-mortem desk ----
graded_pool = [e for e in entries
               if e.get("call") in ("Risk-on", "Risk-off")]
if graded_pool:
    st.divider()
    theme.panel_bar("Post-mortem scorecard",
                    "your calls vs what the market then did")
    auto_hits, auto_total = 0, 0
    rows = []
    for e in graded_pool:
        tkr = e.get("instrument", "^GSPC")
        s = data.px_history(tkr)
        fwd = data.fwd_from_series(s, pd.Timestamp(e["date"]))
        r1m = fwd.get(21)
        hit = None
        if r1m is not None:
            hit = (r1m > 0) == (e["call"] == "Risk-on")
            auto_total += 1
            auto_hits += int(hit)
        rows.append((e, tkr, fwd, hit))
    if auto_total:
        pct = auto_hits / auto_total * 100
        theme.readout(
            theme.GREEN if pct >= 55 else
            (theme.AMBER if pct >= 45 else theme.RED),
            f"Directional hit rate: {auto_hits}/{auto_total} calls "
            f"right at 1 month ({pct:.0f}%). Coin-flip is 50 — the "
            f"scorecard only means something after ~20 calls.")
    for e, tkr, fwd, hit in rows:
        mark = ("✔" if hit else "✘") if hit is not None else "…"
        with st.expander(f"{mark} {e['date']} · {e['call']} · {tkr} — "
                         f"{(e.get('decision') or '')[:50]}"):
            if fwd:
                cells = st.columns(len(fwd))
                for c, (h, v) in zip(cells, fwd.items()):
                    lbl = {5: "1W", 21: "1M", 63: "3M"}.get(h, f"{h}d")
                    with c:
                        st.markdown(
                            f'<div style="background:{theme.PANEL};'
                            f'padding:6px 10px;border-radius:2px;'
                            f'font-family:\'IBM Plex Mono\',monospace">'
                            f'<span class="desk-eyebrow" style="color:'
                            f'{theme.MUTED}">{tkr} +{lbl}</span><br>'
                            f'<span style="color:'
                            f'{theme.GREEN if v > 0 else theme.RED}">'
                            f'{v:+.2f}%</span></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="desk-note">Too recent — '
                            'forward window still open.</div>',
                            unsafe_allow_html=True)
            g = st.selectbox(
                "Your grade (direction is not the whole story)",
                ["ungraded", "right, right reason",
                 "right, WRONG reason", "wrong"],
                index=["ungraded", "right, right reason",
                       "right, WRONG reason",
                       "wrong"].index(e.get("grade", "ungraded")),
                key=f"grade_{e['date']}_{id(e)}")
            if g != e.get("grade", "ungraded"):
                e["grade"] = g
                save(entries)
                st.success("Grade saved.")
    theme.note("The machine grades DIRECTION; only you can grade "
               "REASONING — and 'right for the wrong reason' is the "
               "grade that matters most, because it's the one that "
               "quietly builds bad habits. Post-mortems are Book III's "
               "whole thesis: the notebook is a feedback loop, not a "
               "diary.")

if entries:
    st.subheader(f"Entries ({len(entries)})")
    for e in entries:
        with st.expander(f"📅 {e['date']} — {e['decision'][:60] or 'entry'}"):
            for field in ("evidence", "interpretation", "risks",
                          "falsification", "decision"):
                if e.get(field):
                    st.markdown(f"**{field.title()}**")
                    st.markdown(e[field])
else:
    st.info("No entries yet. The first divergence you spot goes here.")
