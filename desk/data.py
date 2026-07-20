"""Data layer for the Capital Markets Desk.

FRED: uses an API key from Streamlit secrets or env if present, otherwise
falls back to the public fredgraph.csv endpoint (no key required).
Market data: Yahoo Finance via yfinance.
All fetchers fail soft — they return empty frames rather than raising, and
pages are expected to show a warning when data is missing.
"""
from __future__ import annotations

import datetime as dt
import io
import os

import pandas as pd
import requests
import streamlit as st

FRED_API = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# ---------------------------------------------------------------- FRED ----

def _fred_key() -> str | None:
    try:
        if "FRED_API_KEY" in st.secrets:
            return st.secrets["FRED_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FRED_API_KEY")


@st.cache_data(ttl=3600, show_spinner=False)
def fred_series(series_id: str, start: str = "2000-01-01") -> pd.Series:
    """Return a FRED series as a float Series indexed by date. Empty on failure."""
    key = _fred_key()
    try:
        if key:
            r = requests.get(
                FRED_API,
                params={
                    "series_id": series_id,
                    "api_key": key,
                    "file_type": "json",
                    "observation_start": start,
                },
                timeout=30,
            )
            r.raise_for_status()
            obs = r.json()["observations"]
            s = pd.Series(
                [o["value"] for o in obs],
                index=pd.to_datetime([o["date"] for o in obs]),
                name=series_id,
            )
        else:
            r = requests.get(FRED_CSV, params={"id": series_id}, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", series_id]
            s = pd.Series(
                df[series_id].values,
                index=pd.to_datetime(df["date"]),
                name=series_id,
            )
            s = s[s.index >= start]
        s = pd.to_numeric(s, errors="coerce").dropna()
        return s
    except Exception:
        return pd.Series(dtype=float, name=series_id)


MACRO_SERIES = {
    "GROWTH": [
        ("PAYEMS", "Nonfarm Payrolls", "thousands"),
        ("INDPRO", "Industrial Production", "index"),
        ("RSAFS", "Retail Sales", "$mm"),
        ("ICSA", "Initial Jobless Claims", "claims"),
    ],
    "INFLATION": [
        ("CPIAUCSL", "CPI (Headline)", "index"),
        ("PCEPILFE", "Core PCE Price Index", "index"),
        ("T5YIE", "5Y Breakeven", "%"),
        ("T10YIE", "10Y Breakeven", "%"),
    ],
    "POLICY": [
        ("DFEDTARU", "Fed Funds Target (Upper)", "%"),
        ("SOFR", "SOFR (overnight)", "%"),
        ("T10Y2Y", "10Y − 2Y Spread", "pp"),
    ],
    "LIQUIDITY": [
        ("WALCL", "Fed Balance Sheet", "$mm"),
        ("RRPONTSYD", "ON RRP", "$bn"),
        ("WTREGEN", "Treasury General Account", "$mm"),
        ("NFCI", "Chicago Fed NFCI", "index"),
    ],
}


@st.cache_data(ttl=3600, show_spinner=False)
def macro_bundle() -> dict[str, pd.Series]:
    """Fetch every macro series once; keyed by FRED id."""
    out = {}
    for panel in MACRO_SERIES.values():
        for sid, *_ in panel:
            out[sid] = fred_series(sid)
    return out


def net_liquidity(bundle: dict[str, pd.Series]) -> pd.Series:
    """WALCL − TGA − RRP, in $ millions, aligned weekly."""
    w, t, r = bundle.get("WALCL"), bundle.get("WTREGEN"), bundle.get("RRPONTSYD")
    if w is None or w.empty:
        return pd.Series(dtype=float)
    df = pd.DataFrame({"walcl": w})
    if t is not None and not t.empty:
        df["tga"] = t
    if r is not None and not r.empty:
        df["rrp_bn"] = r
    df = df.sort_index().ffill().dropna()
    if df.empty:
        return pd.Series(dtype=float)
    nl = df["walcl"] - df.get("tga", 0) - df.get("rrp_bn", 0) * 1000
    nl.name = "Net Liquidity ($mm)"
    return nl


# -------------------------------------------------------------- MARKET ----

MARKET_TICKERS = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "IWM": "Russell 2000 (IWM)",
    "RSP": "S&P Equal Weight (RSP)",
    "SPY": "SPY",
    "HYG": "High Yield (HYG)",
    "LQD": "Inv. Grade (LQD)",
    "GC=F": "Gold",
    "CL=F": "WTI Crude",
    "HG=F": "Copper",
    "DX-Y.NYB": "Dollar Index",
    "BTC-USD": "Bitcoin",
    "^VIX": "VIX",
    "^VIX3M": "VIX 3M",
    "^VVIX": "VVIX",
    "^SKEW": "SKEW",
    "^MOVE": "MOVE",
}


@st.cache_data(ttl=900, show_spinner=False)
def market_history(period: str = "2y") -> pd.DataFrame:
    """Daily closes for the full ticker set. Columns = tickers."""
    import yfinance as yf

    try:
        data = yf.download(
            list(MARKET_TICKERS), period=period, interval="1d",
            auto_adjust=True, progress=False, group_by="column",
        )
        closes = data["Close"] if "Close" in data else data
        return closes.dropna(how="all")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def spy_skew_curve(target_dte: int = 45) -> tuple[pd.DataFrame, str]:
    """IV-by-strike for the SPY expiration nearest target_dte.

    Returns (frame with strike/moneyness/iv/type, expiration label).
    """
    import yfinance as yf

    try:
        tk = yf.Ticker("SPY")
        spot = tk.fast_info["last_price"]
        today = dt.date.today()
        expiries = [(e, abs((dt.date.fromisoformat(e) - today).days - target_dte))
                    for e in tk.options]
        expiry = min(expiries, key=lambda x: x[1])[0]
        chain = tk.option_chain(expiry)
        frames = []
        for typ, df in (("put", chain.puts), ("call", chain.calls)):
            d = df[["strike", "impliedVolatility"]].copy()
            d["type"] = typ
            frames.append(d)
        out = pd.concat(frames)
        out["moneyness"] = out["strike"] / spot * 100
        out = out[(out.moneyness > 60) & (out.moneyness < 130)
                  & (out.impliedVolatility > 0.01)]
        return out, expiry
    except Exception:
        return pd.DataFrame(), ""


def pct_chg(s: pd.Series, days: int = 1) -> float | None:
    s = s.dropna()
    if len(s) <= days:
        return None
    return (s.iloc[-1] / s.iloc[-1 - days] - 1) * 100


@st.cache_data(ttl=900, show_spinner=False)
def ohlc(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Daily OHLC for one ticker (for candlestick charts). Empty on failure."""
    import yfinance as yf

    try:
        df = yf.download(ticker, period=period, interval="1d",
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        keep = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
        return df[keep].dropna()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def usrec() -> pd.Series:
    """NBER recession indicator (monthly 0/1). Cached a full day."""
    return fred_series("USREC", start="1990-01-01")


def tail_years(s: pd.Series, n: int | float) -> pd.Series:
    """Last n years by date cutoff (pandas-2-safe; Series.last() is gone)."""
    if s.empty:
        return s
    cutoff = s.index.max() - pd.Timedelta(days=int(n * 365.25))
    return s[s.index >= cutoff]


def yoy_pct(s: pd.Series) -> pd.Series:
    """Frequency-safe YoY %: resample to month-start, then shift(12)."""
    if s is None or s.empty:
        return pd.Series(dtype=float)
    m = s.resample("MS").last()
    return ((m / m.shift(12) - 1) * 100).dropna()


def latest_prints(bundle: dict[str, pd.Series]) -> dict:
    """Latest headline numbers for the event anchors.

    All FRED (Tier 1); the three extra series ride the existing
    fred_series cache. Each value is (number, date) or None.
    """
    def last(s: pd.Series):
        s = s.dropna()
        return (float(s.iloc[-1]), s.index[-1]) if not s.empty else None

    empty = pd.Series(dtype=float)
    pay = bundle.get("PAYEMS", empty).dropna()
    nfp = (pay.resample("MS").last().diff().dropna()
           if not pay.empty else empty)
    return {
        "cpi_yoy": last(yoy_pct(bundle.get("CPIAUCSL", empty))),
        "nfp_chg": last(nfp),                       # thousands, 1m change
        "unrate": last(fred_series("UNRATE", start="2024-01-01")),
        "tgt_lower": last(fred_series("DFEDTARL", start="2024-01-01")),
        "tgt_upper": last(bundle.get("DFEDTARU", empty)),
        "effr": last(fred_series("EFFR", start="2024-01-01")),
    }


def print_lines(p: dict) -> dict[str, str]:
    """Render latest_prints into one display line per anchor ('' if n/a)."""
    out = {"CPI": "", "NFP": "", "FOMC": ""}
    if p.get("cpi_yoy"):
        v, dt_ = p["cpi_yoy"]
        out["CPI"] = f"last {v:+.1f}% YoY ({dt_:%b})"
    if p.get("nfp_chg"):
        v, dt_ = p["nfp_chg"]
        line = f"last {v:+,.0f}K"
        if p.get("unrate"):
            line += f" · U-3 {p['unrate'][0]:.1f}%"
        out["NFP"] = line + f" ({dt_:%b})"
    if p.get("tgt_upper"):
        hi = p["tgt_upper"][0]
        line = (f"target {p['tgt_lower'][0]:.2f}\u2013{hi:.2f}%"
                if p.get("tgt_lower") else f"target \u2264{hi:.2f}%")
        if p.get("effr"):
            ev, ed = p["effr"]
            line += f" · EFFR {ev:.2f}% ({ed:%d-%b})"
        out["FOMC"] = line
    return out
