"""Capital Markets Desk — entry point and navigation.

st.navigation replaces filename-order sidebar chaos with intent: the
working surfaces first, markets grouped together, the analyst's tools
as their own section, and the reference material (Time Machine, Help)
where reference material belongs — at the bottom. Page files keep
their paths, so every _ROUTES command and switch_page call still works.
"""
import streamlit as st

st.set_page_config(page_title="Capital Markets Desk", page_icon="📟",
                   layout="wide")

pg = st.navigation({
    "The Desk": [
        st.Page("pages/0_Summary.py", title="Summary", icon="📟",
                default=True),
        st.Page("pages/00_Launchpad.py", title="Launchpad", icon="🟧"),
        st.Page("pages/0_Daily_Circuit.py", title="Daily Circuit",
                icon="🔁"),
    ],
    "Markets": [
        st.Page("pages/1_Macro.py", title="Macro", icon="🌡️"),
        st.Page("pages/2_Market.py", title="Market", icon="📈"),
        st.Page("pages/3_Volatility.py", title="Volatility", icon="🌀"),
        st.Page("pages/7_Rates.py", title="Rates", icon="📉"),
        st.Page("pages/8_Futures.py", title="Futures & COT", icon="🛢️"),
        st.Page("pages/9_Global.py", title="Global & FX", icon="🌍"),
        st.Page("pages/17_Flow.py", title="Flow", icon="🌊"),
    ],
    "Research": [
        st.Page("pages/6_Quote.py", title="Quote", icon="🔎"),
        st.Page("pages/5_Wire.py", title="Wire", icon="🗞️"),
        st.Page("pages/13_Calendar.py", title="Calendar", icon="🗓️"),
        st.Page("pages/10_Fed.py", title="Fed", icon="🏛️"),
    ],
    "The Analyst": [
        st.Page("pages/4_Notebook.py", title="Notebook", icon="📓"),
        st.Page("pages/15_Ideas.py", title="Idea Desk", icon="⚡"),
        st.Page("pages/12_Desk_Analyst.py", title="Desk Analyst",
                icon="🤖"),
        st.Page("pages/14_History.py", title="Regime History",
                icon="📼"),
    ],
    "Reference": [
        st.Page("pages/11_Time_Machine.py", title="Time Machine",
                icon="⏪"),
        st.Page("pages/16_Help.py", title="Help", icon="❓"),
    ],
})
pg.run()
