"""Flow layer — the Sector Flow Tracker's automatable half, in-app.

Fund-level ETF flows have no free historical feed — so the desk
accrues its own, the same way it accrues the signal record: the
nightly bot logs shares outstanding × close for a fixed ETF set to
history/flows.csv on the `data` branch, and flow = Δshares × price
(creations and redemptions) computes from day one forward. Nothing
backfilled; thin at first; live-accrued and tamper-evident. [T2 —
Yahoo's shares figure can lag a day, which matters less than it
sounds: per Ch. 15, the flow scan speaks only in STREAKS and
divergences, and streaks survive a day of lag.]

The daily short-volume layer is FINRA's public Reg SHO files —
keyless, same-day, one row per symbol at a predictable CDN URL. [T1 —
official filings; note it covers OFF-EXCHANGE (TRF/ADF/ORF) volume
only, so the ratio is a positioning tell, not total market shorting.]

What stays in the workbook, honestly: the BlockLog (real-time block
prints aren't free) and the FINRA ATS dark-venue paste (free but
login-gated and 2-4 weeks delayed by rule).
"""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from desk.history import OWNER, REPO

# ticker -> (name, group). Groups drive the rotation-signature read:
# equity complex vs fixed income vs commodity is the July 15 lesson.
FLOW_ETFS = {
    "XLK": ("Technology", "Sector"), "XLF": ("Financials", "Sector"),
    "XLE": ("Energy", "Sector"), "XLV": ("Health Care", "Sector"),
    "XLI": ("Industrials", "Sector"),
    "XLY": ("Cons. Discretionary", "Sector"),
    "XLP": ("Cons. Staples", "Sector"), "XLU": ("Utilities", "Sector"),
    "XLB": ("Materials", "Sector"), "XLRE": ("Real Estate", "Sector"),
    "XLC": ("Comm. Services", "Sector"),
    "SOXX": ("Semiconductors", "Sector"),
    "SPY": ("S&P 500 (SPY)", "Broad"), "VOO": ("S&P 500 (VOO)", "Broad"),
    "QQQ": ("Nasdaq 100", "Broad"), "IWM": ("Russell 2000", "Broad"),
    "RSP": ("S&P Equal Weight", "Broad"),
    "TLT": ("20Y+ Treasuries", "Fixed Income"),
    "HYG": ("High Yield", "Fixed Income"),
    "LQD": ("Inv. Grade", "Fixed Income"),
    "GLD": ("Gold", "Commodity"), "SLV": ("Silver", "Commodity"),
    "USO": ("WTI Crude", "Commodity"),
}

_LOCAL = Path(__file__).resolve().parents[1] / "history" / "flows.csv"
RAW_URL = (f"https://raw.githubusercontent.com/{OWNER}/{REPO}"
           "/data/history/flows.csv")
FINRA_CDN = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d}.txt"


# ------------------------------------------------- nightly accrual ----

def snapshot_rows(today: str) -> list[dict]:
    """One row per ETF: date, ticker, shares outstanding, close.
    Headless-safe; a ticker that fails is skipped (its flow shows as a
    gap, never a fabricated number)."""
    import time

    import yfinance as yf

    rows = []
    for i, t in enumerate(FLOW_ETFS):
        try:
            if i:
                time.sleep(0.25)          # pace Yahoo
            fi = yf.Ticker(t).fast_info
            sh, px = fi.get("shares"), fi.get("last_price")
            if sh and px and sh > 0 and px > 0:
                rows.append({"date": today, "ticker": t,
                             "shares": int(sh), "close": round(float(px), 4)})
        except Exception:
            continue
    return rows


# ---------------------------------------------------------- loading ----

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ("shares", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return (df.dropna(subset=["date", "ticker", "shares", "close"])
              .drop_duplicates(subset=["date", "ticker"], keep="last")
              .sort_values(["ticker", "date"]))


@st.cache_data(ttl=3600, show_spinner=False)
def load() -> pd.DataFrame:
    """The accrued shares log. Empty before the first bot run."""
    if OWNER != "OWNER":
        try:
            r = requests.get(RAW_URL, timeout=15)
            if r.ok and r.text.strip():
                return _clean(pd.read_csv(io.StringIO(r.text)))
        except Exception:
            pass
    try:
        if _LOCAL.exists():
            return _clean(pd.read_csv(_LOCAL))
    except Exception:
        pass
    return pd.DataFrame()


# -------------------------------------------------------- flow math ----

def compute_flows(log: pd.DataFrame) -> pd.DataFrame:
    """Long log -> daily flows: date, ticker, flow_mm ($ millions),
    group. flow = Δshares × close (creations/redemptions). Pure."""
    if log.empty:
        return pd.DataFrame()
    out = []
    for t, g in log.groupby("ticker"):
        if t not in FLOW_ETFS:
            continue
        g = g.sort_values("date")
        dshares = g["shares"].diff()
        flow = dshares * g["close"] / 1e6
        for d, f in zip(g["date"].iloc[1:], flow.iloc[1:]):
            if pd.notna(f):
                out.append({"date": d, "ticker": t,
                            "flow_mm": round(float(f), 1),
                            "group": FLOW_ETFS[t][1]})
    return (pd.DataFrame(out).sort_values(["date", "ticker"])
            if out else pd.DataFrame())


def streaks(flows: pd.DataFrame, min_days: int = 3,
            min_total_mm: float = 250.0) -> pd.DataFrame:
    """Per ticker: current one-sided run (consecutive same-sign flow
    days ending at the latest date), kept when it's at least min_days
    AND at least min_total_mm cumulative. Ch. 15: the scan only speaks
    in streaks; single days are plumbing. Pure."""
    if flows.empty:
        return pd.DataFrame()
    rows = []
    last_date = flows["date"].max()
    for t, g in flows.groupby("ticker"):
        g = g.sort_values("date")
        if g["date"].iloc[-1] != last_date:
            continue                      # stale ticker — no live streak
        vals = g["flow_mm"].tolist()
        sign = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
        if sign == 0:
            continue
        n, total = 0, 0.0
        for v in reversed(vals):
            if v * sign <= 0:
                break
            n += 1
            total += v
        if n >= min_days and abs(total) >= min_total_mm:
            rows.append({"ticker": t, "name": FLOW_ETFS[t][0],
                         "group": FLOW_ETFS[t][1], "days": n,
                         "total_mm": round(total, 0)})
    return (pd.DataFrame(rows)
            .sort_values("total_mm", key=lambda s: s.abs(),
                         ascending=False)
            if rows else pd.DataFrame())


def group_day(flows: pd.DataFrame) -> pd.DataFrame:
    """Latest day's net flow by group — the rotation-signature table."""
    if flows.empty:
        return pd.DataFrame()
    last = flows[flows["date"] == flows["date"].max()]
    return (last.groupby("group")["flow_mm"].sum()
            .reindex(["Sector", "Broad", "Fixed Income", "Commodity"])
            .dropna().to_frame("net_mm"))


# ------------------------------------------------ FINRA short volume ----

def parse_finra(text: str) -> pd.DataFrame:
    """Pipe-delimited Reg SHO daily file -> rows for the desk's ETF
    set with short_ratio = ShortVolume / TotalVolume. Pure."""
    try:
        df = pd.read_csv(io.StringIO(text), sep="|")
    except Exception:
        return pd.DataFrame()
    need = {"Symbol", "ShortVolume", "TotalVolume"}
    if not need.issubset(df.columns):
        return pd.DataFrame()
    df = df[df["Symbol"].isin(FLOW_ETFS)].copy()
    for c in ("ShortVolume", "TotalVolume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["ShortVolume", "TotalVolume"])
    df = df[df["TotalVolume"] > 0]
    df["short_ratio"] = df["ShortVolume"] / df["TotalVolume"]
    return df[["Symbol", "ShortVolume", "TotalVolume", "short_ratio"]]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def finra_short(lookback_days: int = 7) -> tuple[pd.DataFrame, str]:
    """(latest available day's table, its date-string). Walks back from
    today until a file exists (weekends/holidays have none). Keyless.
    Empty frame if nothing reachable."""
    d = dt.date.today()
    for _ in range(lookback_days):
        stamp = d.strftime("%Y%m%d")
        try:
            r = requests.get(FINRA_CDN.format(d=stamp), timeout=15)
            if r.ok and "Symbol" in r.text[:200]:
                out = parse_finra(r.text)
                if not out.empty:
                    return out, d.strftime("%d-%b-%Y")
        except Exception:
            pass
        d -= dt.timedelta(days=1)
    return pd.DataFrame(), ""


# ------------------------------------------------------ flow alerts ----

def evaluate_flow_alerts(flows: pd.DataFrame) -> list[str]:
    """Alert lines for the nightly issue: big one-sided streaks and the
    equity-out/fixed-income-in rotation signature. Pure; [] when quiet."""
    out = []
    stk = streaks(flows, min_days=4, min_total_mm=1000.0)
    for _, r in stk.iterrows():
        side = "IN" if r["total_mm"] > 0 else "OUT"
        out.append(
            f"FLOW STREAK: {r['name']} ({r['ticker']}) — "
            f"${abs(r['total_mm']):,.0f}mm {side} over {r['days']} "
            f"consecutive sessions. Ch. 15's G6 speaks in streaks; "
            f"this is one.")
    gd = group_day(flows)
    if not gd.empty:
        eq = float(gd.reindex(["Sector", "Broad"])["net_mm"].sum())
        fi = float(gd.loc["Fixed Income", "net_mm"]) \
            if "Fixed Income" in gd.index else 0.0
        if eq <= -1500 and fi >= 500:
            out.append(
                f"ROTATION SIGNATURE: equity complex "
                f"${eq:,.0f}mm out while fixed income "
                f"${fi:+,.0f}mm in on the same session — the "
                f"July 15 pattern. Rotation or distribution? is the "
                f"question; write the falsifier for each answer.")
    return out
