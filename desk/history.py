"""Reader for the desk's live-accrued signal history.

The nightly GitHub Action (scripts/snapshot.py) appends one row per US
trading day to history/signals.csv on the repo's `data` branch — never
main, so the app never redeploys (a redeploy wipes Notebook storage).
The app reads that CSV over raw.githubusercontent, cached an hour.

Fail-soft everywhere: before the workflow's first run the branch does
not exist and this module simply returns an empty frame — the History
page shows its honest empty state instead of an error.

ONE-TIME SETUP: set OWNER below to your GitHub username (or add a
HISTORY_CSV_URL secret, which overrides the constant). A local
history/signals.csv — present when the snapshot script has run on this
machine — is used as a fallback for development.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
import streamlit as st

OWNER = "OWNER"  # <-- your GitHub username, one-time edit
REPO = "CapitalMarketsMacro"
RAW_URL = (f"https://raw.githubusercontent.com/{OWNER}/{REPO}"
           "/data/history/signals.csv")

_LOCAL = Path(__file__).resolve().parents[1] / "history" / "signals.csv"

DIALS = ["growth", "inflation", "policy", "liquidity"]


def _url() -> str:
    try:
        if "HISTORY_CSV_URL" in st.secrets:
            return st.secrets["HISTORY_CSV_URL"]
    except Exception:
        pass
    return RAW_URL


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates, coerce numerics, de-dupe, sort. Pure."""
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = (df.dropna(subset=["date"])
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
            .set_index("date"))
    for c in df.columns:
        if not c.endswith("_label"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load() -> pd.DataFrame:
    """The full history, indexed by date. Empty frame if the record
    hasn't started yet (data branch missing, URL unset, network down)."""
    if OWNER != "OWNER":  # constant configured — try the raw URL
        try:
            r = requests.get(_url(), timeout=15)
            if r.ok and r.text.strip():
                import io
                return _clean(pd.read_csv(io.StringIO(r.text),
                                          dtype={"date": str}))
        except Exception:
            pass
    else:
        # Constant unconfigured — a secrets override may still be set.
        try:
            if "HISTORY_CSV_URL" in st.secrets:
                r = requests.get(st.secrets["HISTORY_CSV_URL"], timeout=15)
                if r.ok and r.text.strip():
                    import io
                    return _clean(pd.read_csv(io.StringIO(r.text),
                                              dtype={"date": str}))
        except Exception:
            pass
    try:  # local fallback: dev machine after a manual script run
        if _LOCAL.exists():
            return _clean(pd.read_csv(_LOCAL, dtype={"date": str}))
    except Exception:
        pass
    return pd.DataFrame()


def category(score) -> int | None:
    """Score -> color band: 0 red (0-1), 1 yellow (2), 2 green (3-4).
    None when the score is missing (an 'Incomplete' row)."""
    if pd.isna(score):
        return None
    s = int(score)
    return 2 if s >= 3 else (0 if s <= 1 else 1)


def streaks(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Per dial: (current color band, sessions it has held). Skips
    dials whose latest score is missing."""
    out = {}
    for d in DIALS:
        col = f"{d}_score"
        if col not in df.columns:
            continue
        cats = [category(v) for v in df[col]]
        if not cats or cats[-1] is None:
            continue
        cur, n = cats[-1], 0
        for c in reversed(cats):
            if c != cur:
                break
            n += 1
        out[d] = (cur, n)
    return out


def red_flips(df: pd.DataFrame, dial: str,
              fwd_days: int = 21) -> pd.DataFrame:
    """Every session a dial FLIPPED into red, with SPX's forward return
    over the next `fwd_days` recorded sessions (NaN until enough rows
    have accrued to grade it). Record-internal — graded against the
    same CSV, no outside data."""
    col = f"{dial}_score"
    if col not in df.columns or "spx" not in df.columns:
        return pd.DataFrame()
    cats = df[col].map(category)
    prev = cats.shift(1)
    flip = (cats == 0) & (prev != 0) & prev.notna()
    rows = []
    idx = list(df.index)
    for i, ts in enumerate(idx):
        if not flip.iloc[i]:
            continue
        spx0 = df["spx"].iloc[i]
        fwd = None
        if i + fwd_days < len(idx):
            spx1 = df["spx"].iloc[i + fwd_days]
            if pd.notna(spx0) and pd.notna(spx1) and spx0:
                fwd = (spx1 / spx0 - 1) * 100
        rows.append({"date": ts, "spx_at_flip": spx0, "fwd_1m_pct": fwd})
    return pd.DataFrame(rows)
