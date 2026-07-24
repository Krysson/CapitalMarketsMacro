"""Breadth internals — computed from S&P 500 members, because no free
feed publishes the aggregates. The nightly bot batch-downloads member
prices via the CHART endpoint (the one Yahoo doesn't block from
runners — 22-Jul log), computes the internals for the full trailing
year, and writes history/breadth.csv to the data branch: the first
run backfills a year of history instantly.

S&P-500-scoped, not NYSE-wide — arguably better: the A/D line matches
the index you chart it against. Current-constituent backfill carries
mild survivorship tint; live rows don't. [T2]
"""
from __future__ import annotations

import io

import pandas as pd
import requests
import streamlit as st

from desk.history import OWNER, REPO

WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def constituents() -> list[str]:
    """Tickers from Wikipedia's table (the standard free source)."""
    r = requests.get(WIKI, timeout=30,
                     headers={"User-Agent": "Mozilla/5.0 desk"})
    tables = pd.read_html(io.StringIO(r.text))
    col = tables[0]["Symbol"]
    return [s.replace(".", "-") for s in col.astype(str).tolist()]


def compute(closes: pd.DataFrame) -> pd.DataFrame:
    """Members' daily closes -> internals frame."""
    closes = closes.dropna(axis=1, how="all")
    ma200 = closes.rolling(200, min_periods=120).mean()
    ma50 = closes.rolling(50, min_periods=30).mean()
    valid = closes.notna()
    out = pd.DataFrame(index=closes.index)
    out["pct_above_200d"] = ((closes > ma200) & valid).sum(1) \
        / valid.sum(1) * 100
    out["pct_above_50d"] = ((closes > ma50) & valid).sum(1) \
        / valid.sum(1) * 100
    chg = closes.diff()
    out["advancers"] = (chg > 0).sum(1)
    out["decliners"] = (chg < 0).sum(1)
    out["ad_line"] = (out["advancers"] - out["decliners"]).cumsum()
    hi52 = closes.rolling(252, min_periods=200).max()
    lo52 = closes.rolling(252, min_periods=200).min()
    out["new_highs"] = (closes >= hi52).sum(1)
    out["new_lows"] = (closes <= lo52).sum(1)
    out["nh_nl"] = out["new_highs"] - out["new_lows"]
    return out.dropna(subset=["pct_above_200d"]).round(2)


@st.cache_data(ttl=1800, show_spinner=False)
def load() -> pd.DataFrame:
    """breadth.csv from the data branch."""
    try:
        url = (f"https://raw.githubusercontent.com/{OWNER}/{REPO}"
               f"/data/history/breadth.csv")
        r = requests.get(url, timeout=15)
        if r.ok and r.text.strip():
            df = pd.read_csv(io.StringIO(r.text))
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date").sort_index()
    except Exception:
        pass
    return pd.DataFrame()
