"""Institutional flow — where big players can't hide.

The chapter's standard, encoded: observable residue only. Institutions
must leave records at specific chokepoints — option open interest
(cleared positions, per strike, daily), Treasury auction results
(demand by bidder class, official), and the NY Fed's primary dealer
statistics (actual dealer positions, weekly, the most institutional
public dataset that exists). This module reads those three. Everything
else — sweep detection, trade-side classification, GEX — is inference,
which is what the paid products sell and what this desk declines to
treat as primary.

The OI layer uses the accrual trick a third time: the nightly bot
stores today's chain (a working snapshot, overwritten) and appends
detected FOOTPRINTS — strikes where open interest jumped — to an
append-only log on the data branch. OI tells you THAT size arrived at
a strike, never which side initiated; the page says so every time.

All keyless. All fail-soft.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from desk.history import OWNER, REPO

OPTION_UNDERLYINGS = ("SPY", "QQQ")
_LOCAL_FP = Path(__file__).resolve().parents[1] / "history" / "oi_footprints.csv"
FP_RAW_URL = (f"https://raw.githubusercontent.com/{OWNER}/{REPO}"
              "/data/history/oi_footprints.csv")

OI_COLS = ["date", "und", "expiry", "strike", "type",
           "oi", "volume", "spot"]
FP_COLS = ["date", "und", "expiry", "strike", "type",
           "oi_prev", "oi_now", "d_oi", "prev_volume", "spot"]


# --------------------------------------------- nightly OI snapshot ----

def oi_snapshot(today: str, max_expiries: int = 5,
                strike_band: float = 0.10,
                min_size: int = 500) -> pd.DataFrame:
    """Today's chain for the underlyings: near expiries (≤45d), strikes
    within ±band of spot, rows with OI or volume ≥ min_size. Headless;
    a failed expiry or underlying is skipped — gaps stay honest."""
    import time

    import yfinance as yf

    rows = []
    for und in OPTION_UNDERLYINGS:
        try:
            tk = yf.Ticker(und)
            spot = float(tk.fast_info.get("last_price") or 0)
            if spot <= 0:
                continue
            exps = [e for e in tk.options
                    if 0 <= (pd.Timestamp(e)
                             - pd.Timestamp(today)).days <= 45]
            for exp in exps[:max_expiries]:
                time.sleep(0.35)                 # pace Yahoo
                try:
                    ch = tk.option_chain(exp)
                except Exception:
                    continue
                for typ, frame in (("C", ch.calls), ("P", ch.puts)):
                    f = frame[["strike", "openInterest", "volume"]].copy()
                    f["openInterest"] = pd.to_numeric(
                        f["openInterest"], errors="coerce").fillna(0)
                    f["volume"] = pd.to_numeric(
                        f["volume"], errors="coerce").fillna(0)
                    f = f[(f["strike"] >= spot * (1 - strike_band))
                          & (f["strike"] <= spot * (1 + strike_band))
                          & ((f["openInterest"] >= min_size)
                             | (f["volume"] >= min_size))]
                    for _, r in f.iterrows():
                        rows.append({
                            "date": today, "und": und, "expiry": exp,
                            "strike": float(r["strike"]), "type": typ,
                            "oi": int(r["openInterest"]),
                            "volume": int(r["volume"]),
                            "spot": round(spot, 2)})
        except Exception:
            continue
    return pd.DataFrame(rows, columns=OI_COLS)


def footprints(prev: pd.DataFrame, curr: pd.DataFrame,
               min_jump: int = 5000,
               min_ratio: float = 0.5) -> pd.DataFrame:
    """OI deltas T-1 → T that qualify as footprints: jump ≥ min_jump
    contracts AND (fresh strike, or ≥ min_ratio of prior OI). Carries
    the PRIOR day's volume — the session the trades actually happened.
    Pure."""
    if prev is None or prev.empty or curr is None or curr.empty:
        return pd.DataFrame(columns=FP_COLS)
    key = ["und", "expiry", "strike", "type"]
    m = curr.merge(prev[key + ["oi", "volume"]], on=key, how="left",
                   suffixes=("", "_prev"))
    m["oi_prev"] = m["oi_prev"].fillna(0)
    m["prev_volume"] = m["volume_prev"].fillna(0)
    m["d_oi"] = m["oi"] - m["oi_prev"]
    hit = m[(m["d_oi"] >= min_jump)
            & ((m["oi_prev"] == 0)
               | (m["d_oi"] >= min_ratio * m["oi_prev"]))]
    out = hit.rename(columns={"oi": "oi_now"})[
        ["date", "und", "expiry", "strike", "type",
         "oi_prev", "oi_now", "d_oi", "prev_volume", "spot"]].copy()
    for c in ("oi_prev", "oi_now", "d_oi", "prev_volume"):
        out[c] = out[c].astype(int)
    return out.sort_values("d_oi", ascending=False)


@st.cache_data(ttl=3600, show_spinner=False)
def load_footprints() -> pd.DataFrame:
    """The append-only footprint log. Empty before two bot runs."""
    if OWNER != "OWNER":
        try:
            r = requests.get(FP_RAW_URL, timeout=15)
            if r.ok and r.text.strip():
                df = pd.read_csv(io.StringIO(r.text))
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                return df.dropna(subset=["date"])
        except Exception:
            pass
    try:
        if _LOCAL_FP.exists():
            df = pd.read_csv(_LOCAL_FP)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df.dropna(subset=["date"])
    except Exception:
        pass
    return pd.DataFrame()


def evaluate_oi_alerts(fp: pd.DataFrame,
                       min_alert: int | None = None) -> list[str]:
    """Alert lines for today's very large footprints. Pure."""
    if fp is None or fp.empty:
        return []
    if min_alert is None:
        from desk.alerts import THRESHOLDS as _T
        min_alert = int(_T["oi_footprint_alert"])
    out = []
    for _, r in fp[fp["d_oi"] >= min_alert].iterrows():
        kind = "calls" if r["type"] == "C" else "puts"
        out.append(
            f"OI FOOTPRINT: {r['und']} {r['expiry']} {r['strike']:g} "
            f"{kind} +{r['d_oi']:,} contracts overnight "
            f"({r['oi_prev']:,} → {r['oi_now']:,}; prior-day volume "
            f"{r['prev_volume']:,}). Size arrived at that strike — "
            f"which side initiated is NOT observable.")
    return out


# ------------------------------------------------- auction results ----

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def auction_results(days: int = 60) -> pd.DataFrame:
    """Recent auction RESULTS from TreasuryDirect (keyless): bid-to-
    cover and bidder-class shares. Field names are taken tolerantly —
    absent fields become NaN, never a crash. Coupon auctions only
    (bills roll constantly and rarely matter)."""
    try:
        r = requests.get("https://www.treasurydirect.gov/TA_WS/"
                         f"securities/auctioned?days={days}&format=json",
                         timeout=20)
        r.raise_for_status()
        raw = pd.DataFrame(r.json())
    except Exception:
        return pd.DataFrame()
    if raw.empty:
        return pd.DataFrame()

    def num(col):
        return (pd.to_numeric(raw[col], errors="coerce")
                if col in raw.columns else pd.Series(float("nan"),
                                                     index=raw.index))

    out = pd.DataFrame({
        "date": pd.to_datetime(raw.get("auctionDate"), errors="coerce"),
        "type": raw.get("securityType", ""),
        "term": raw.get("securityTerm", ""),
        "btc": num("bidToCoverRatio"),
        "high_yield": num("highYield"),
        "indirect": num("indirectBidderAccepted"),
        "direct": num("directBidderAccepted"),
        "dealer": num("primaryDealerAccepted"),
    })
    comp = out[["indirect", "direct", "dealer"]].sum(axis=1)
    out["indirect_pct"] = (out["indirect"] / comp * 100).where(comp > 0)
    out["dealer_pct"] = (out["dealer"] / comp * 100).where(comp > 0)
    out = out[out["type"].isin(["Note", "Bond", "TIPS", "FRN"])]
    return (out.dropna(subset=["date"])
               .sort_values("date", ascending=False))


# -------------------------------------------- primary dealer stats ----

PD_SERIES = {
    "PDPOSGST-TOT": "UST net position (ex-TIPS)",
    "PDPOSCS-TOT": "Corporate securities net position",
}


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def dealer_positions() -> dict[str, pd.Series]:
    """Weekly primary dealer NET positions from the NY Fed Markets
    Data API (keyless). Endpoint shape is tried in two documented
    variants and parsed tolerantly; {} on failure. [T1 — the most
    institutional public dataset that exists.] Values are $ millions."""
    out = {}
    for key, name in PD_SERIES.items():
        for url in (
            f"https://markets.newyorkfed.org/api/pd/get/SBN2024/"
            f"timeseries/{key}.json",
            f"https://markets.newyorkfed.org/api/pd/get/all/"
            f"timeseries/{key}.json",
        ):
            try:
                r = requests.get(url, timeout=20)
                if not r.ok:
                    continue
                rows = (r.json().get("pd", {}) or {}).get("timeseries", [])
                if not rows:
                    continue
                idx, vals = [], []
                for o in rows:
                    d = o.get("asofdate") or o.get("asOfDate")
                    v = o.get("value")
                    if d is None or v in (None, "", "*"):
                        continue
                    idx.append(d)
                    vals.append(v)
                s = pd.Series(
                    pd.to_numeric(pd.Series(vals), errors="coerce").values,
                    index=pd.to_datetime(idx, errors="coerce"), name=name)
                s = s[s.index.notna()].dropna().sort_index()
                if not s.empty:
                    out[name] = s
                    break
            except Exception:
                continue
    return out
