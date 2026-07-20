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


@st.cache_data(ttl=900, show_spinner=False)
def spy_iv_surface(target_dtes: tuple = (15, 30, 60, 90)) -> tuple[
        pd.DataFrame, float | None]:
    """SPY IV across ~4 expiries. (surface_points, spot); empty on failure.

    One chain call per expiry against Yahoo's rate-limited endpoint —
    each expiry fails independently.
    """
    import yfinance as yf

    try:
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
        for expiry, dte in chosen:
            try:
                ch = tk.option_chain(expiry)
                for typ, df in (("put", ch.puts), ("call", ch.calls)):
                    part = df[["strike", "impliedVolatility"]].copy()
                    part["type"], part["dte"], part["expiry"] = typ, dte, expiry
                    frames.append(part)
            except Exception:
                continue
        if not frames:
            return pd.DataFrame(), spot
        return shape_surface(pd.concat(frames), spot), spot
    except Exception:
        return pd.DataFrame(), None


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
