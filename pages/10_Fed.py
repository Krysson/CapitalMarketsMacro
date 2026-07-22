"""Fed Statement Diff — every changed word was argued about. DIFF <GO>.

The FOMC edits its statement as little as possible, on purpose. That
discipline makes the redline the highest-signal document in macro:
professionals read the CHANGES, not the statement.
"""
import datetime as dt

import streamlit as st

from desk import events, fed, theme

st.set_page_config(page_title="Fed Diff — Desk", page_icon="▪",
                   layout="wide")
theme.header(
    "BOOK II · CH. 4 COMPANION",
    "Fed Statement Diff",
    "The statement redlined against the prior one. Green = added, "
    "red struck = removed. The Committee changes as few words as it can "
    "— so every change is a decision.")

dates = events.past_statements()
if len(dates) < 2:
    st.error("Not enough statement dates on file — update desk/events.py.")
    st.stop()

c1, c2 = st.columns(2)
new_d = c1.selectbox("Statement", dates, index=0,
                     format_func=lambda d: f"{d:%d %b %Y}")
older = [d for d in dates if d < new_d]
old_d = c2.selectbox("Compared against", older, index=0,
                     format_func=lambda d: f"{d:%d %b %Y}")

with st.spinner("Pulling both statements…"):
    new_txt, old_txt = fed.get_statement(new_d), fed.get_statement(old_d)

for d, txt in ((new_d, new_txt), (old_d, old_txt)):
    if not txt:
        st.error(f"Couldn't fetch the {d:%d %b %Y} statement "
                 f"(federalreserve.gov unreachable, or an off-pattern "
                 f"URL). Try again shortly.")
        st.stop()

ops = fed.word_diff(old_txt, new_txt)
add, rem = fed.diff_stats(ops)
n_equal = sum(len(t.split()) for op, t in ops if op == "equal")
churn = (add + rem) / max(1, n_equal + rem) * 100
theme.readout(
    theme.AMBER if churn > 8 else theme.GREEN,
    f"{add} words added · {rem} removed vs {old_d:%d %b} — "
    f"{churn:.0f}% of the statement changed. "
    + ("Heavy edit — something moved." if churn > 8
       else "Light touch — continuity is the message."))

spans = []
for op, text in ops:
    if op == "equal":
        spans.append(f'<span style="color:{theme.MUTED}">{text}</span>')
    elif op == "insert":
        spans.append(f'<span style="color:#7EE0A3;background:'
                     f'rgba(0,176,97,0.12);padding:0 2px">{text}</span>')
    else:
        spans.append(f'<span style="color:{theme.RED};text-decoration:'
                     f'line-through;opacity:0.85;padding:0 2px">{text}'
                     f'</span>')
st.markdown(
    f'<div style="background:{theme.PANEL};padding:16px 20px;'
    f'border-radius:2px;border-left:3px solid {theme.AMBER};'
    f'font-family:\'IBM Plex Sans\',sans-serif;font-size:0.95rem;'
    f'line-height:1.75">{" ".join(spans)}</div>',
    unsafe_allow_html=True)
theme.note("How to read it: changes to the FIRST paragraph are the "
           "economy read; changes near 'the Committee' verbs (decided / "
           "judges / anticipates) are the policy signal; a new name in "
           "the vote is a dissent — count them. Unchanged text is "
           "deliberately unchanged: continuity is itself a message. "
           "Statements land 2:00 p.m. ET on decision day — this page "
           "has the redline minutes later.")

with st.expander("Full text — current statement"):
    st.markdown(new_txt)
with st.expander("Full text — prior statement"):
    st.markdown(old_txt)
