"""Analyst's Notebook — Evidence → Interpretation → Risks → Falsification."""
import datetime as dt
import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Notebook — Desk", page_icon="📓", layout="wide")
st.title("Analyst's Notebook")
st.caption("Evidence → Interpretation → Risks → Falsification → Decision. "
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
    "app redeploys or restarts. **Download your notebook regularly** (button "
    "below) and re-upload to restore.", icon="💾")

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
    if st.form_submit_button("Save entry"):
        entries.insert(0, {
            "date": str(date), "evidence": evidence,
            "interpretation": interpretation, "risks": risks,
            "falsification": falsification, "decision": decision,
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
    st.download_button("⬇️ Download notebook (markdown)",
                       "\n".join(md_lines),
                       file_name="analysts_notebook.md")

uploaded = st.file_uploader("Restore from a previous JSON backup", type="json")
if uploaded is not None:
    try:
        restored = json.loads(uploaded.read())
        save(restored)
        st.success(f"Restored {len(restored)} entries — refresh the page.")
    except Exception:
        st.error("Could not parse that file.")

if entries:
    st.download_button("⬇️ Download backup (JSON)",
                       json.dumps(entries, indent=2),
                       file_name="notebook_backup.json")
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
