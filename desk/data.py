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
@st.cache_resource
def _lastgood() -> dict:
    """Cross-rerun store of last successful pulls from flaky endpoints."""
    return {}


def _resilient(key: str, fetcher, ttl: int = 900, retry_gap: int = 120,
               _now=None):
    """Fetch with success-TTL, failure cool-down, and stale fallback.

    Returns (value, fetched_ts, stale). Raises only if there has never
    been a successful pull AND the fetch fails.
    """
    import time as _time
    store = _lastgood()
    now = _now if _now is not None else _time.time()
    if key in store:
        val, ts = store[key]
        if now - ts < ttl:
            return val, ts, False
    if store.get(key + "._fail", 0) > now - retry_gap:
        if key in store:
            val, ts = store[key]
            return val, ts, True
        raise RuntimeError("endpoint cooling down; no cached value yet")
    try:
        val = fetcher()
        store[key] = (val, now)
        store.pop(key + "._fail", None)
        return val, now, False
    except Exception:
        store[key + "._fail"] = now
        if key in store:
            val, ts = store[key]
            return val, ts, True
        raise


def _fetch_skew(target_dte: int) -> tuple[pd.DataFrame, str]:
    """Raw chain pull; retries once with a pause before giving up."""
    import time as _time

    import yfinance as yf

    last_err = None
    for attempt in range(2):
        try:
            tk = yf.Ticker("SPY")
            spot = tk.fast_info["last_price"]
            today = dt.date.today()
            expiries = [(e, abs((dt.date.fromisoformat(e) - today).days
                                - target_dte)) for e in tk.options]
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
            if out.empty:
                raise ValueError("empty chain")
            return out, expiry
        except Exception as ex:
            last_err = ex
            _time.sleep(1.5)
    raise last_err


def spy_skew_curve(target_dte: int = 45) -> tuple[pd.DataFrame, str,
                                                  float | None]:
    """(frame, expiry, stale_ts). stale_ts is the epoch of the last good
    pull when Yahoo is throttling and we're serving it; None when fresh.
    Empty frame only if there has never been a successful pull."""
    try:
        (df, expiry), ts, stale = _resilient(
            "skew", lambda: _fetch_skew(target_dte))
        return df, expiry, (ts if stale else None)
    except Exception:
        return pd.DataFrame(), "", None


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


# Command-bar shorthand for common series — type the alias, get the chart.
FRED_ALIASES = {
    "CPI": "CPIAUCSL", "COREPCE": "PCEPILFE", "PCE": "PCEPILFE",
    "NFP": "PAYEMS", "PAYROLLS": "PAYEMS", "CLAIMS": "ICSA",
    "UNRATE": "UNRATE", "U3": "UNRATE", "GDP": "GDPC1",
    "FEDFUNDS": "DFEDTARU", "EFFR": "EFFR", "SOFR": "SOFR",
    "10Y": "DGS10", "2Y": "DGS2", "CURVE": "T10Y2Y",
    "BREAKEVEN": "T5YIE", "NFCI": "NFCI", "WALCL": "WALCL",
    "TGA": "WTREGEN", "RRP": "RRPONTSYD",
}


# --------------------------------------------------------------- Cboe ----
# The index owner's own daily-history CSVs — keyless, updated daily.
# Exists because Yahoo quietly dropped most Cboe proprietary indices
# (licensing), which is why ^SKEW never rendered. [T1]
CBOE_ALIASES = {"SKEW": "SKEW", "VVIX": "VVIX"}


@st.cache_data(ttl=3600, show_spinner=False)
def cboe_series(symbol: str) -> pd.Series:
    """Daily close for a Cboe index from cdn.cboe.com. Empty on any
    failure. NOTE: Cboe announced (2025 consultation) a coming SKEW
    methodology revision — when it lands, old and new levels won't be
    comparable; the chart note says so."""
    try:
        r = requests.get(
            "https://cdn.cboe.com/api/global/us_indices/daily_prices/"
            f"{symbol}_History.csv", timeout=20)
        r.raise_for_status()
        import io as _io
        df = pd.read_csv(_io.StringIO(r.text))
        cols = {c.strip().upper(): c for c in df.columns}
        dcol, ccol = cols.get("DATE"), cols.get("CLOSE")
        if not dcol or not ccol:
            return pd.Series(dtype=float, name=symbol)
        s = pd.Series(pd.to_numeric(df[ccol], errors="coerce").values,
                      index=pd.to_datetime(df[dcol], errors="coerce"),
                      name=symbol)
        return s[s.index.notna()].dropna().sort_index()
    except Exception:
        return pd.Series(dtype=float, name=symbol)


@st.cache_data(ttl=3600, show_spinner=False)
def stooq_series(symbol: str) -> pd.Series:
    """Quiet computable fallback (stooq.com free CSV) for plain US
    tickers Yahoo fumbles. [T2] Empty on failure."""
    try:
        sym = symbol.lower()
        if sym.isalpha():
            sym += ".us"
        r = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d",
                         timeout=15)
        if not r.ok or "Close" not in r.text[:100]:
            return pd.Series(dtype=float, name=symbol)
        import io as _io
        df = pd.read_csv(_io.StringIO(r.text))
        s = pd.Series(pd.to_numeric(df["Close"], errors="coerce").values,
                      index=pd.to_datetime(df["Date"], errors="coerce"),
                      name=symbol)
        return s[s.index.notna()].dropna().sort_index()
    except Exception:
        return pd.Series(dtype=float, name=symbol)


# ---------------------------------------------------------------- EIA ----
# The official energy layer. What this is NOT: the API (American
# Petroleum Institute) Tuesday-evening inventory number — that is a
# PAID private survey with no free feed; it reaches this desk only as a
# Tier 5 headline on the Wire. What the EIA publishes Wednesday 10:30
# ET is the number of record the API print front-runs — and it's free.
EIA_API = "https://api.eia.gov/v2/seriesid/"

# alias -> (APIv1 series id — the v2 /seriesid route translates these,
#           display name). Weekly WPSR series unless noted.
EIA_ALIASES = {
    "CUSHING": ("PET.W_EPC0_SAX_YCUOK_MBBL.W",
                "Cushing, OK Crude Stocks ex-SPR (kbbl)"),
    "CRUDE": ("PET.WCESTUS1.W",
              "US Commercial Crude Stocks ex-SPR (kbbl)"),
    "GASOLINE": ("PET.WGTSTUS1.W", "US Total Gasoline Stocks (kbbl)"),
    "DISTILLATE": ("PET.WDISTUS1.W", "US Distillate Stocks (kbbl)"),
    "REFINERY": ("PET.WPULEUS3.W", "US Refinery Utilization (%)"),
    "UTIL": ("PET.WPULEUS3.W", "US Refinery Utilization (%)"),
    "CRUDEPROD": ("PET.WCRFPUS2.W", "US Crude Production (kb/d)"),
    "WTISPOT": ("PET.RWTC.D", "WTI Spot, Cushing FOB ($/bbl, daily)"),
    "NATGAS": ("NG.NW2_EPG0_SWO_R48_BCF.W",
               "Lower-48 Working Nat Gas Storage (Bcf)"),
    "GASSTORAGE": ("NG.NW2_EPG0_SWO_R48_BCF.W",
                   "Lower-48 Working Nat Gas Storage (Bcf)"),
}


def _eia_key() -> str | None:
    try:
        if "EIA_API_KEY" in st.secrets:
            return st.secrets["EIA_API_KEY"]
    except Exception:
        pass
    return os.environ.get("EIA_API_KEY")


@st.cache_data(ttl=3600, show_spinner=False)
def eia_series(series_id: str) -> pd.Series:
    """One EIA series via the v2 /seriesid translation route. Empty on
    failure or without an EIA_API_KEY (the EIA API has no keyless
    fallback, unlike FRED). GOTCHA (documented API change v2.1.6): data
    values return as JSON *strings* — always coerce numeric. We request
    newest-first with the 5,000-row cap (long dailies exceed it) and
    re-sort ascending."""
    key = _eia_key()
    if not key:
        return pd.Series(dtype=float, name=series_id)
    try:
        r = requests.get(
            EIA_API + series_id,
            params={"api_key": key, "length": 5000,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc"},
            timeout=30)
        r.raise_for_status()
        rows = r.json().get("response", {}).get("data", [])
        if not rows:
            return pd.Series(dtype=float, name=series_id)
        idx, vals = [], []
        for o in rows:
            p = str(o.get("period", ""))
            if len(p) == 7:            # monthly "YYYY-MM"
                p += "-01"
            idx.append(p)
            vals.append(o.get("value"))
        s = pd.Series(pd.to_numeric(pd.Series(vals), errors="coerce").values,
                      index=pd.to_datetime(idx, errors="coerce"),
                      name=series_id)
        return s[s.index.notna()].dropna().sort_index()
    except Exception:
        return pd.Series(dtype=float, name=series_id)


@st.cache_data(ttl=900, show_spinner=False)
def ticker_snapshot(t: str) -> dict:
    """Quote-page basics for one ticker. {} on failure; the profile
    fields degrade independently (Yahoo's .info is flakier than prices)."""
    import yfinance as yf

    out = {}
    try:
        tk = yf.Ticker(t)
        fi = tk.fast_info
        out = {"price": fi["last_price"],
               "prev_close": fi["previous_close"],
               "year_high": fi["year_high"], "year_low": fi["year_low"],
               "market_cap": fi.get("market_cap"),
               "currency": fi.get("currency", "USD")}
    except Exception:
        return {}
    try:
        info = tk.info
        for k_src, k_dst in (("longName", "name"), ("sector", "sector"),
                             ("industry", "industry"),
                             ("trailingPE", "pe"), ("forwardPE", "fwd_pe"),
                             ("dividendYield", "div_yield"),
                             ("beta", "beta"),
                             ("longBusinessSummary", "summary")):
            if info.get(k_src) is not None:
                out[k_dst] = info[k_src]
    except Exception:
        pass
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def ticker_financials(t: str) -> pd.DataFrame:
    """Annual income-statement highlights, columns = fiscal years.
    Empty frame on failure (Yahoo rate-limits this endpoint)."""
    import yfinance as yf

    try:
        df = yf.Ticker(t).income_stmt
        rows = [r for r in ("Total Revenue", "Gross Profit",
                            "Operating Income", "Net Income")
                if r in df.index]
        if not rows:
            return pd.DataFrame()
        out = df.loc[rows].iloc[:, :4]
        out.columns = [c.strftime("%Y") if hasattr(c, "strftime")
                       else str(c) for c in out.columns]
        return out
    except Exception:
        return pd.DataFrame()


TREASURY_TENORS = [
    ("1M", "DGS1MO"), ("3M", "DGS3MO"), ("6M", "DGS6MO"),
    ("1Y", "DGS1"), ("2Y", "DGS2"), ("3Y", "DGS3"), ("5Y", "DGS5"),
    ("7Y", "DGS7"), ("10Y", "DGS10"), ("20Y", "DGS20"), ("30Y", "DGS30"),
]


@st.cache_data(ttl=3600, show_spinner=False)
def treasury_curve(start: str = "2015-01-01") -> pd.DataFrame:
    """Constant-maturity par yields, columns = tenors. All FRED, Tier 1."""
    cols = {}
    for label, sid in TREASURY_TENORS:
        s = fred_series(sid, start=start)
        if not s.empty:
            cols[label] = s
    return pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()


def shape_surface(raw: pd.DataFrame, spot: float) -> pd.DataFrame:
    """Pure transform: raw option rows -> OTM surface points.

    Expects columns strike / impliedVolatility / type / dte / expiry.
    Keeps 70-125%% moneyness, drops junk IVs, and uses the standard
    OTM construction: puts below spot, calls above.
    """
    if raw.empty or not spot:
        return pd.DataFrame()
    out = raw.copy()
    out["moneyness"] = out["strike"] / spot * 100
    out = out[(out.moneyness > 70) & (out.moneyness < 125)
              & (out.impliedVolatility > 0.01)
              & (out.impliedVolatility < 3.0)]
    out = out[((out.type == "put") & (out.moneyness <= 100.5))
              | ((out.type == "call") & (out.moneyness > 100.5))]
    return out


def _fetch_surface(target_dtes: tuple) -> tuple[pd.DataFrame, float]:
    import time as _time

    import yfinance as yf

    if True:
        tk = yf.Ticker("SPY")
        spot = tk.fast_info["last_price"]
        today = dt.date.today()
        avail = [(e, (dt.date.fromisoformat(e) - today).days)
                 for e in tk.options]
        avail = [x for x in avail if x[1] > 0]
        chosen = []
        for tgt in target_dtes:
            if not avail:
                break
            pick = min(avail, key=lambda x: abs(x[1] - tgt))
            if pick not in chosen:
                chosen.append(pick)
        frames = []
        for i, (expiry, dte) in enumerate(chosen):
            try:
                if i:
                    _time.sleep(0.8)      # pace the rate-limited endpoint
                ch = tk.option_chain(expiry)
                for typ, df in (("put", ch.puts), ("call", ch.calls)):
                    part = df[["strike", "impliedVolatility"]].copy()
                    part["type"], part["dte"], part["expiry"] = typ, dte, expiry
                    frames.append(part)
            except Exception:
                continue
        if not frames:
            raise ValueError("no chains resolved")
        return shape_surface(pd.concat(frames), spot), spot


def spy_iv_surface(target_dtes: tuple = (15, 30, 60, 90)) -> tuple[
        pd.DataFrame, float | None, float | None]:
    """(surface, spot, stale_ts) — stale_ts set when serving the last
    good pull during a Yahoo throttle; empty only if never succeeded."""
    try:
        (df, spot), ts, stale = _resilient(
            "surface", lambda: _fetch_surface(target_dtes), ttl=1800)
        return df, spot, (ts if stale else None)
    except Exception:
        return pd.DataFrame(), None, None


@st.cache_data(ttl=86400, show_spinner=False)
def fred_meta(series_id: str) -> dict:
    """Series metadata (title, units, frequency…). {} without an API key
    or on failure — the Quote page degrades to showing the raw ID."""
    key = _fred_key()
    if not key:
        return {}
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series",
            params={"series_id": series_id, "api_key": key,
                    "file_type": "json"},
            timeout=15)
        r.raise_for_status()
        s = r.json()["seriess"][0]
        return {"title": s.get("title", ""),
                "units": s.get("units_short", s.get("units", "")),
                "freq": s.get("frequency_short", ""),
                "sa": s.get("seasonal_adjustment_short", ""),
                "updated": s.get("last_updated", "")[:10]}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fred_search(text: str, limit: int = 15) -> list[dict]:
    """Search FRED's catalog, popularity-ranked. [] without a key."""
    key = _fred_key()
    if not key or not text.strip():
        return []
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/search",
            params={"search_text": text, "api_key": key,
                    "file_type": "json", "limit": limit,
                    "order_by": "popularity", "sort_order": "desc"},
            timeout=15)
        r.raise_for_status()
        return [{"id": s["id"], "title": s.get("title", ""),
                 "freq": s.get("frequency_short", ""),
                 "units": s.get("units_short", ""),
                 "pop": s.get("popularity", 0)}
                for s in r.json().get("seriess", [])]
    except Exception:
        return []


def series_hist_points(s: pd.Series) -> list[tuple[str, str]]:
    """Compact historics for the Quote page: latest and lookbacks.
    Change shown in native units (safe for both levels and rates)."""
    s = s.dropna()
    if s.empty:
        return []
    last_dt = s.index[-1]
    latest = float(s.iloc[-1])
    out = [("LATEST", f"{latest:,.2f}")]
    for label, off in (("1M AGO", pd.DateOffset(months=1)),
                       ("6M AGO", pd.DateOffset(months=6)),
                       ("1Y AGO", pd.DateOffset(years=1))):
        v = s.asof(last_dt - off)
        if pd.notna(v):
            out.append((label, f"{float(v):,.2f}"))
    y = s.asof(last_dt - pd.DateOffset(years=1))
    if pd.notna(y):
        out.append(("1Y \u0394", f"{latest - float(y):+,.2f}"))
    return out


# ------------------------------------------------------------ FUTURES ----

FUTURES_COMPLEXES = {
    "ENERGY": [("CL=F", "WTI Crude"), ("BZ=F", "Brent"),
               ("NG=F", "Nat Gas"), ("RB=F", "RBOB Gasoline")],
    "METALS": [("GC=F", "Gold"), ("SI=F", "Silver"),
               ("HG=F", "Copper"), ("PL=F", "Platinum")],
    "GRAINS": [("ZC=F", "Corn"), ("ZS=F", "Soybeans"),
               ("ZW=F", "Wheat"), ("ZL=F", "Soybean Oil")],
    "SOFTS": [("KC=F", "Coffee"), ("SB=F", "Sugar"),
              ("CC=F", "Cocoa"), ("CT=F", "Cotton")],
    "LIVESTOCK": [("LE=F", "Live Cattle"), ("HE=F", "Lean Hogs")],
}

_MONTH_CODES = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
                7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}

# Contract-month cycles and Yahoo exchange suffixes for curve building.
FUT_SPECS = {
    "CL": (".NYM", set(range(1, 13))),            # WTI: every month
    "NG": (".NYM", set(range(1, 13))),
    "GC": (".CMX", {2, 4, 6, 8, 10, 12}),
    "SI": (".CMX", {3, 5, 7, 9, 12}),
    "HG": (".CMX", {3, 5, 7, 9, 12}),
    "ZC": (".CBT", {3, 5, 7, 9, 12}),
    "ZS": (".CBT", {1, 3, 5, 7, 8, 9, 11}),
    "ZW": (".CBT", {3, 5, 7, 9, 12}),
}


def next_contracts(root: str, n: int = 6,
                   today: dt.date | None = None) -> list[tuple[str, str]]:
    """Next n listed contract months for a root -> [(yahoo_symbol,
    'Mon-YY' label)]. Pure; starts NEXT calendar month so a front
    contract mid-expiry never sneaks in."""
    if root not in FUT_SPECS:
        return []
    suffix, cycle = FUT_SPECS[root]
    today = today or dt.date.today()
    y, m = today.year, today.month
    out = []
    while len(out) < n:
        m += 1
        if m > 12:
            m, y = 1, y + 1
        if m in cycle:
            sym = f"{root}{_MONTH_CODES[m]}{str(y)[2:]}{suffix}"
            out.append((sym, dt.date(y, m, 1).strftime("%b-%y")))
    return out


@st.cache_data(ttl=900, show_spinner=False)
def futures_board(period: str = "1y") -> pd.DataFrame:
    """Front-month closes for every board contract. Columns = tickers."""
    import yfinance as yf

    tickers = [t for grp in FUTURES_COMPLEXES.values() for t, _ in grp]
    try:
        raw = yf.download(tickers, period=period, interval="1d",
                          auto_adjust=True, progress=False,
                          group_by="column")
        closes = raw["Close"] if "Close" in raw else raw
        return closes.dropna(how="all")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def futures_curve(root: str, n: int = 6) -> pd.DataFrame:
    """Term structure: one quote per listed month (n calls against
    Yahoo). Each contract fails independently; rows = whatever resolved."""
    import yfinance as yf

    rows = []
    for sym, label in next_contracts(root, n):
        try:
            px = yf.Ticker(sym).fast_info["last_price"]
            if px and px > 0:
                rows.append({"contract": label, "symbol": sym,
                             "price": float(px)})
        except Exception:
            continue
    return pd.DataFrame(rows)


# ------------------------------------------------------ COT / GLOBAL ----

# CFTC COT lives in TWO datasets: physical commodities in the
# "disaggregated" report (speculators = managed money), financial
# futures in the TFF report (speculators = leveraged funds). Same API,
# different dataset IDs and column prefixes.
# GOTCHA (verified against live API responses): the two datasets use
# DIFFERENT column conventions — disaggregated has an "_all" suffix on
# position columns, TFF does not. Asking Socrata for the wrong name
# returns an error, not empty data.
_COT_DATASETS = {
    "disagg": ("72hh-3qpy", "m_money_positions_long_all",
               "m_money_positions_short_all", "MANAGED MONEY"),
    "tff": ("gpe5-46if", "lev_money_positions_long",
            "lev_money_positions_short", "LEVERAGED FUNDS"),
}

# (cftc_code, display_name, dataset_kind)
COT_CODES = {
    "ES": ("13874A", "S&P 500 E-mini", "tff"),
    "NQ": ("209742", "Nasdaq 100 E-mini", "tff"),
    "ZN": ("043602", "10Y T-Note", "tff"),
    "ZT": ("042601", "2Y T-Note", "tff"),
    "ZB": ("020601", "30Y T-Bond", "tff"),
    "DX": ("098662", "US Dollar Index", "tff"),
    "VX": ("1170E1", "VIX Futures", "tff"),
    "CL": ("067651", "WTI Crude", "disagg"),
    "NG": ("023651", "Nat Gas", "disagg"),
    "GC": ("088691", "Gold", "disagg"),
    "SI": ("084691", "Silver", "disagg"),
    "HG": ("085692", "Copper", "disagg"),
    "ZC": ("002602", "Corn", "disagg"),
    "ZS": ("005602", "Soybeans", "disagg"),
    "ZW": ("001602", "Wheat (SRW)", "disagg"),
}


def cot_transform(rows: list[dict],
                  lcol: str = "m_money_positions_long_all",
                  scol: str = "m_money_positions_short_all"
                  ) -> pd.DataFrame:
    """Pure: raw CFTC records -> weekly net-speculator DataFrame.
    Column names differ per dataset — pass them explicitly."""
    df = pd.DataFrame(rows)
    need = {"report_date_as_yyyy_mm_dd", lcol, scol}
    if df.empty or not need.issubset(df.columns):
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    for c in (lcol, scol, "open_interest_all"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["net_mm"] = df[lcol] - df[scol]
    keep = ["net_mm"] + (["open_interest_all"]
                         if "open_interest_all" in df else [])
    return df.set_index("date")[keep].dropna(subset=["net_mm"]).sort_index()


@st.cache_data(ttl=21600, show_spinner=False)
def cot_series(code: str, kind: str = "disagg") -> pd.DataFrame:
    """~10y of weekly COT for one contract from the CFTC's public API
    (official filings — reported, not estimated). kind selects the
    dataset: 'disagg' for commodities, 'tff' for financials."""
    dataset, lcol, scol, _ = _COT_DATASETS[kind]
    try:
        r = requests.get(
            f"https://publicreporting.cftc.gov/resource/{dataset}.json",
            params={"cftc_contract_market_code": code,
                    "$select": (f"report_date_as_yyyy_mm_dd,{lcol},"
                                f"{scol},open_interest_all"),
                    # DESC: Socrata applies $limit AFTER ordering — asc
                    # returns the OLDEST 600 weeks (ends ~2017)
                    "$order": "report_date_as_yyyy_mm_dd DESC",
                    "$limit": 600},
            timeout=15)
        r.raise_for_status()
        return cot_transform(r.json(), lcol, scol)
    except Exception:
        return pd.DataFrame()


GLOBAL_INDICES = {
    "AMERICAS": [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"),
                 ("^GSPTSE", "TSX"), ("^BVSP", "Bovespa"),
                 ("^MXX", "Mexico IPC")],
    "EMEA": [("^FTSE", "FTSE 100"), ("^GDAXI", "DAX"),
             ("^FCHI", "CAC 40"), ("^STOXX50E", "Euro Stoxx 50"),
             ("^SSMI", "Swiss SMI")],
    "APAC": [("^N225", "Nikkei 225"), ("^HSI", "Hang Seng"),
             ("000001.SS", "Shanghai Comp"), ("^KS11", "KOSPI"),
             ("^AXJO", "ASX 200"), ("^BSESN", "Sensex")],
}


@st.cache_data(ttl=900, show_spinner=False)
def global_board(period: str = "1y") -> pd.DataFrame:
    import yfinance as yf

    tickers = [t for grp in GLOBAL_INDICES.values() for t, _ in grp]
    tickers.append("DX-Y.NYB")
    try:
        raw = yf.download(tickers, period=period, interval="1d",
                          auto_adjust=True, progress=False,
                          group_by="column")
        closes = raw["Close"] if "Close" in raw else raw
        return closes.dropna(how="all")
    except Exception:
        return pd.DataFrame()


# Yahoo pairs: value = units of QUOTE per 1 BASE.
FX_PAIRS = {"EUR": ("EURUSD=X", True), "GBP": ("GBPUSD=X", True),
            "AUD": ("AUDUSD=X", True), "JPY": ("JPY=X", False),
            "CHF": ("CHF=X", False), "CAD": ("CAD=X", False),
            "CNY": ("CNY=X", False)}


def fx_cross(usd_per: dict[str, float]) -> pd.DataFrame:
    """Pure triangulation: {ccy: USD value of 1 unit} -> cross matrix
    where cell[base][quote] = units of quote per 1 base."""
    ccys = list(usd_per)
    return pd.DataFrame(
        {q: [usd_per[b] / usd_per[q] for b in ccys] for q in ccys},
        index=ccys)


@st.cache_data(ttl=900, show_spinner=False)
def fx_matrix() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(cross matrix today, 1d %-change matrix). Empty frames on failure."""
    import yfinance as yf

    try:
        raw = yf.download([p for p, _ in FX_PAIRS.values()], period="5d",
                          interval="1d", progress=False,
                          group_by="column")
        closes = (raw["Close"] if "Close" in raw else raw).dropna(how="all")
        if len(closes) < 2:
            return pd.DataFrame(), pd.DataFrame()

        def usd_per(row) -> dict[str, float]:
            out = {"USD": 1.0}
            for ccy, (pair, direct) in FX_PAIRS.items():
                px = row.get(pair)
                if pd.notna(px) and px > 0:
                    out[ccy] = float(px) if direct else 1.0 / float(px)
            return out

        today = fx_cross(usd_per(closes.iloc[-1]))
        prior = fx_cross(usd_per(closes.iloc[-2]))
        chg = (today / prior - 1) * 100
        return today, chg
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=21600, show_spinner=False)
def treasury_auctions() -> pd.DataFrame:
    """Upcoming auctions from TreasuryDirect's public API (no key)."""
    try:
        r = requests.get("https://www.treasurydirect.gov/TA_WS/"
                         "securities/upcoming?format=json", timeout=15)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if df.empty:
            return df
        keep = [c for c in ("auctionDate", "securityType", "securityTerm",
                            "offeringAmount") if c in df.columns]
        df = df[keep].copy()
        if "offeringAmount" in df:
            df["offeringAmount"] = (
                pd.to_numeric(df["offeringAmount"], errors="coerce") / 1e9)
        if "auctionDate" in df:
            df["auctionDate"] = pd.to_datetime(
                df["auctionDate"]).dt.strftime("%a %d-%b")
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def px_history(ticker: str, start: str = "2006-01-01") -> pd.Series:
    """Long daily close history for one ticker (time machine, grading)."""
    import yfinance as yf

    try:
        raw = yf.download(ticker, start=start, interval="1d",
                          auto_adjust=True, progress=False)
        s = raw["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s.dropna()
    except Exception:
        return pd.Series(dtype=float)


def fwd_from_series(s: pd.Series, entry: pd.Timestamp,
                    horizons: tuple = (5, 21, 63)) -> dict[int, float]:
    """Pure: forward %-returns from the first session on/after entry."""
    s = s.dropna()
    out = {}
    idx = s.index.searchsorted(pd.Timestamp(entry))
    if idx >= len(s):
        return out
    base = float(s.iloc[idx])
    for h in horizons:
        j = idx + h
        if j < len(s):
            out[h] = (float(s.iloc[j]) / base - 1) * 100
    return out


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fred_series_asof(series_id: str, asof: str,
                     start: str = "2000-01-01") -> pd.Series:
    """ALFRED vintage: the series as it was KNOWN on `asof` — revisions
    that came later do not exist. Needs FRED_API_KEY; empty without."""
    key = _fred_key()
    if not key:
        return pd.Series(dtype=float)
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": key,
                    "file_type": "json", "observation_start": start,
                    "observation_end": asof, "realtime_start": asof,
                    "realtime_end": asof},
            timeout=20)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        s = pd.Series(
            {pd.Timestamp(o["date"]): float(o["value"])
             for o in obs if o.get("value") not in (".", None)})
        return s.sort_index()
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def vintage_bundle(asof: str) -> dict[str, pd.Series]:
    """The full macro bundle as known on `asof` (one ALFRED call per
    series; cached a week per date)."""
    out = {}
    for panel in MACRO_SERIES.values():
        for sid, _, _ in panel:
            out[sid] = fred_series_asof(sid, asof)
    return out
