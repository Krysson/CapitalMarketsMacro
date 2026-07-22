"""Analyst's Notebook — Evidence → Interpretation → Risks → Falsification."""
import datetime as dt
import json
from pathlib import Path

import streamlit as st

import pandas as pd

from desk import data, publish, theme

st.set_page_config(page_title="Notebook — Desk", page_icon="📓", layout="wide")
theme.header("BOOK I · CH. 15", "Analyst's Notebook",
             "Evidence → Interpretation → Risks → Falsification → Decision. "
             "Tag evidence [F] fact, [E] estimate, [I] inference. The "
             "scratchpad is private; publishing an entry to the record is "
             "a deliberate act — like a real desk, the pitch goes on the "
             "tape, the working notes don't.")

STORE = Path("notebook_entries.json")
JOTS = Path("notebook_jots.json")


def load() -> list[dict]:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text())
        except Exception:
            return []
    return []


def save(entries: list[dict]) -> None:
    STORE.write_text(json.dumps(entries, indent=2))


def load_jots() -> list[dict]:
    if JOTS.exists():
        try:
            return json.loads(JOTS.read_text())
        except Exception:
            return []
    return []


def save_jots(jots: list[dict]) -> None:
    JOTS.write_text(json.dumps(jots, indent=2))


entries = load()
jots = load_jots()

st.warning(
    "Storage note: on Streamlit Community Cloud this scratchpad file resets "
    "whenever the app redeploys or restarts. **Download your notebook "
    "regularly** and re-upload to restore. Entries published to the record "
    "are immune — they live as git commits on the `data` branch.", icon="💾")

# --------------------------------------------------------- the blotter ----
theme.panel_bar("Blotter — quick notes",
                f"{len(jots)} jot{'s' if len(jots) != 1 else ''} · "
                "private, always")
with st.form("jot", clear_on_submit=True, border=False):
    jc1, jc2 = st.columns([8, 1])
    jot_text = jc1.text_input(
        "jot", label_visibility="collapsed",
        placeholder="10:14 — RSP/SPY green while SPX flat; watching…")
    if jc2.form_submit_button("JOT", use_container_width=True) \
            and jot_text.strip():
        jots.insert(0, {"ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "text": jot_text.strip()})
        save_jots(jots)
        st.rerun()
theme.note("The blotter is the desk's running tape of half-thoughts — "
           "timestamped, unstructured, never published. Promote a jot "
           "when it earns the full Evidence → Decision treatment; the "
           "structured entry is the pitch, this is the margin it came "
           "from.")

if jots:
    with st.expander(f"Open blotter ({len(jots)})",
                     expanded=len(jots) <= 5):
        kill = None
        for i, j in enumerate(jots):
            b1, b2, b3 = st.columns([8, 1.4, 0.6])
            b1.markdown(f'<div class="desk-note" style="font-size:0.85rem">'
                        f'<span style="color:{theme.AMBER}">{j["ts"]}</span> '
                        f'&nbsp;{j["text"]}</div>', unsafe_allow_html=True)
            if b2.button("→ entry", key=f"promote_{i}",
                         help="Prefill a structured entry's Evidence "
                              "with this jot"):
                st.session_state["prefill_evidence"] = \
                    f"[{j['ts']}] {j['text']}"
            if b3.button("✕", key=f"deljot_{i}"):
                kill = i
        if kill is not None:
            jots.pop(kill)
            save_jots(jots)
            st.rerun()

# Promote-prefill: seed the Evidence widget's state BEFORE the form
# renders. GOTCHA (learned the hard way): passing the jot as value= and
# popping it broke on the submit rerun — the reverted value changed the
# widget's auto-generated identity, so Streamlit returned a fresh empty
# widget and entries published blank. A stable key + pre-seeded state is
# the correct pattern; repeated promotes append instead of overwriting.
if "prefill_evidence" in st.session_state:
    _seed = st.session_state.pop("prefill_evidence")
    _cur = st.session_state.get("evidence_field", "")
    st.session_state["evidence_field"] = \
        f"{_cur}\n{_seed}".strip() if _cur else _seed

with st.form("entry", clear_on_submit=True):
    st.subheader("New entry")
    date = st.date_input("Date", dt.date.today())
    evidence = st.text_area(
        "Evidence", height=140, key="evidence_field",
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
    pub_on = publish.enabled()
    do_publish = st.checkbox(
        "Publish to the public record — commits this entry to the repo's "
        "`data` branch as a dated git commit, visible to anyone who can "
        "see the repo. Leave unchecked to keep it in the private "
        "scratchpad (the default, like a real desk).",
        value=False, disabled=not pub_on)
    if not pub_on:
        st.markdown('<div class="desk-note">Publishing is off — add a '
                    'GH_TOKEN to the app secrets and set OWNER in '
                    'desk/history.py to enable it (steps in the README). '
                    'The scratchpad works either way.</div>',
                    unsafe_allow_html=True)
    if st.form_submit_button("Save entry"):
        # Normalize the instrument so post-mortem grading can actually
        # fetch it: Yahoo index symbols need the caret (^DJI not dji).
        _ALIAS = {"DJI": "^DJI", "SPX": "^GSPC", "GSPC": "^GSPC",
                  "NDX": "^NDX", "VIX": "^VIX", "RUT": "^RUT"}
        inst = instrument.strip().upper() or "^GSPC"
        inst = _ALIAS.get(inst, inst)
        entry = {
            "date": str(date), "evidence": evidence,
            "interpretation": interpretation, "risks": risks,
            "falsification": falsification, "decision": decision,
            "call": call, "instrument": inst,
        }
        if do_publish and pub_on and not (evidence.strip()
                                          or decision.strip()):
            # A real desk doesn't publish an empty pitch — and the
            # record permanently displays whatever reaches it.
            do_publish = False
            st.error("Not published: an entry needs at least Evidence "
                     "or a Decision before it goes on the record. "
                     "Saved to the scratchpad instead.")
        if do_publish and pub_on:
            ok, path, detail = publish.publish_entry(entry)
            if ok:
                entry["published_path"] = path
                st.success(f"Saved and PUBLISHED — on the record at "
                           f"`{path}`. The commit timestamp is the "
                           f"receipt.")
            else:
                st.error(f"Saved locally, but publishing failed: {detail}")
        else:
            st.success("Saved to the scratchpad.")
        entries.insert(0, entry)
        save(entries)

st.divider()

if entries or jots:
    md_lines = []
    for e in entries:
        md_lines += [f"## {e['date']}", "",
                     f"**Evidence**\n\n{e['evidence']}", "",
                     f"**Interpretation**\n\n{e['interpretation']}", "",
                     f"**Risks**\n\n{e['risks']}", "",
                     f"**Falsification**\n\n{e['falsification']}", "",
                     f"**Decision** — {e['decision']}", "", "---", ""]
    if jots:
        md_lines += ["## Blotter", ""]
        md_lines += [f"- `{j['ts']}` {j['text']}" for j in jots] + [""]
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download notebook (markdown)",
                       "\n".join(md_lines),
                       file_name="analysts_notebook.md")
    c2.download_button("⬇️ Download backup (JSON)",
                       json.dumps({"entries": entries, "jots": jots},
                                  indent=2),
                       file_name="notebook_backup.json")

uploaded = st.file_uploader("Restore from a previous JSON backup", type="json")
if uploaded is not None:
    try:
        restored = json.loads(uploaded.read())
        if isinstance(restored, dict):          # current schema
            save(restored.get("entries", []))
            save_jots(restored.get("jots", []))
            n = len(restored.get("entries", [])) + len(restored.get("jots", []))
        else:                                    # legacy: bare entry list
            save(restored)
            n = len(restored)
        st.success(f"Restored {n} items — refresh the page.")
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
                if e.get("published_path") and publish.enabled():
                    ok, detail = publish.republish_entry(e)
                    if ok:
                        st.success("Grade saved — post-mortem mirrored to "
                                   "the public record. Once a call is on "
                                   "the tape, its reckoning belongs there "
                                   "too.")
                    else:
                        st.warning(f"Grade saved locally; record update "
                                   f"failed: {detail}")
                else:
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
        tag = " · 📡 ON THE RECORD" if e.get("published_path") else ""
        with st.expander(f"📅 {e['date']} — "
                         f"{e['decision'][:60] or 'entry'}{tag}"):
            for field in ("evidence", "interpretation", "risks",
                          "falsification", "decision"):
                if e.get(field):
                    st.markdown(f"**{field.title()}**")
                    st.markdown(e[field])
            if e.get("published_path"):
                st.markdown(f'<div class="desk-note">Published: '
                            f'{e["published_path"]} on the data branch — '
                            f'the git log is the audit trail.</div>',
                            unsafe_allow_html=True)
else:
    st.info("No entries yet. The first divergence you spot goes here.")

# ------------------------------------------------- the public record ----
record = publish.published_files()
if record:
    st.divider()
    theme.panel_bar("The public record",
                    f"{len(record)} published — data branch, append-only")
    for f in record[:25]:
        link = (f'<a href="{f["url"]}" target="_blank" '
                f'style="color:{theme.AMBER}">{f["name"]}</a>'
                if f.get("url") else f["name"])
        st.markdown(f'<div class="desk-note">📡 {link}</div>',
                    unsafe_allow_html=True)
    theme.note("Every file above is a dated commit made at save time — "
               "calls timestamped before outcomes, post-mortems appended "
               "in view of the same history. This is the Notebook held "
               "to the same standard as the signal record: receipts, "
               "not recollections.")
