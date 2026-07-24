"""Capital Markets Desk — entry point and navigation.

st.navigation replaces filename-order sidebar chaos with intent: the
working surfaces first, markets grouped together, the analyst's tools
as their own section, and the reference material (Time Machine, Help)
where reference material belongs — at the bottom. Page files keep
their paths, so every _ROUTES command and switch_page call still works.
"""
import streamlit as st

st.set_page_config(page_title="Capital Markets Desk", page_icon="▪",
                   layout="wide")

pg = st.navigation({
    "The Desk": [
        st.Page("pages/0_Summary.py", title="Summary",
                default=True),
        st.Page("pages/00_Launchpad.py", title="Launchpad"),
        st.Page("pages/0_Daily_Circuit.py", title="Daily Circuit"),
    ],
    "Markets": [
        st.Page("pages/1_Macro.py", title="Macro"),
        st.Page("pages/2_Market.py", title="Market"),
        st.Page("pages/3_Volatility.py", title="Volatility"),
        st.Page("pages/7_Rates.py", title="Rates"),
        st.Page("pages/8_Futures.py", title="Futures & COT"),
        st.Page("pages/9_Global.py", title="Global & FX"),
        st.Page("pages/17_Flow.py", title="Flow"),
    ],
    "Research": [
        st.Page("pages/6_Quote.py", title="Quote"),
        st.Page("pages/5_Wire.py", title="Wire"),
        st.Page("pages/13_Calendar.py", title="Calendar"),
        st.Page("pages/10_Fed.py", title="Fed"),
    ],
    "The Analyst": [
        st.Page("pages/4_Notebook.py", title="Notebook"),
        st.Page("pages/15_Ideas.py", title="Idea Desk"),
        st.Page("pages/18_Paper.py", title="Paper Desk"),
        st.Page("pages/19_Watchlist.py", title="Watchlist"),
        st.Page("pages/12_Desk_Analyst.py", title="Desk Analyst"),
        st.Page("pages/14_History.py", title="Regime History"),
    ],
    "Reference": [
        st.Page("pages/11_Time_Machine.py", title="Time Machine"),
        st.Page("pages/16_Help.py", title="Help"),
    ],
})
pg.run()
