# providers.py — keyed market-data providers with fallback chain
# Capital Markets Desk / v5 Render stub
#
# Sources (all keyed; auth by key, not IP — immune to the Yahoo IP blocks):
#   Finnhub       FINNHUB_API_KEY            quotes, shares outstanding   [T2]
#   Alpaca (IEX)  ALPACA_API_KEY_ID +        quotes/trades                [T2]
#                 ALPACA_API_SECRET_KEY
#   Twelve Data   TWELVEDATA_API_KEY         quote fallback (optional)    [T2]
#   Alpha Vantage ALPHAVANTAGE_API_KEY       shares snapshot, nightly     [T3]
#
# Conventions honored:
#   - fail-soft with named errors: every miss returns a DegradedState with a
#     reason string; nothing is swallowed silently
#   - tier tags travel with the data
#   - in-process TTL cache, same pattern as /api/tape (60s default)

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import requests

# ---------------------------------------------------------------- config ----

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
ALPACA_KEY_ID = os.environ.get("ALPACA_API_KEY_ID", "")
ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET_KEY", "")
TWELVEDATA_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
ALPHAVANTAGE_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")

HTTP_TIMEOUT = 6  # seconds; the desk would rather degrade than hang

_session = requests.Session()
_session.headers.update({"User-Agent": "CapitalMarketsDesk/5.0"})

# ------------------------------------------------------------- ttl cache ----

_cache: dict[str, tuple[float, Any]] = {}


def ttl_cached(ttl: float) -> Callable:
    """Tiny in-process TTL cache, same spirit as the /api/tape cache."""

    def deco(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            key = f"{fn.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.monotonic()
            hit = _cache.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
            val = fn(*args, **kwargs)
            # only cache successes — a degraded miss should retry next call
            if isinstance(val, ProviderResult) and val.ok:
                _cache[key] = (now, val)
            return val

        return wrapper

    return deco


# ---------------------------------------------------------------- shapes ----

@dataclass
class DegradedState:
    """A named miss. Empties must explain themselves."""
    source: str
    reason: str


@dataclass
class ProviderResult:
    ok: bool
    data: Optional[dict] = None
    source: str = ""
    tier: str = ""          # "[T1]".."[T5]"
    degraded: list[DegradedState] = field(default_factory=list)

    def to_payload(self) -> dict:
        """JSON-ready; DegradedState becomes first-class UI material."""
        return {
            "ok": self.ok,
            "data": self.data,
            "source": self.source,
            "tier": self.tier,
            "degraded": [
                {"source": d.source, "reason": d.reason} for d in self.degraded
            ],
        }


# ----------------------------------------------------- individual pulls ----
# Each returns (dict | None, DegradedState | None). Never raises outward.

def _finnhub_quote(symbol: str):
    if not FINNHUB_KEY:
        return None, DegradedState("finnhub", "FINNHUB_API_KEY not set")
    try:
        r = _session.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code == 429:
            return None, DegradedState("finnhub", "rate limited (60/min)")
        if r.status_code != 200:
            return None, DegradedState("finnhub", f"HTTP {r.status_code}")
        j = r.json()
        # Finnhub returns zeros for unknown symbols rather than an error
        if not j.get("c"):
            return None, DegradedState("finnhub", f"no quote for {symbol}")
        return {
            "symbol": symbol,
            "last": j["c"],
            "change": j.get("d"),
            "change_pct": j.get("dp"),
            "high": j.get("h"),
            "low": j.get("l"),
            "open": j.get("o"),
            "prev_close": j.get("pc"),
            "asof": j.get("t"),
        }, None
    except requests.RequestException as e:
        return None, DegradedState("finnhub", f"network: {type(e).__name__}")


def _alpaca_quote(symbol: str):
    if not (ALPACA_KEY_ID and ALPACA_SECRET):
        return None, DegradedState("alpaca", "ALPACA key pair not set")
    try:
        r = _session.get(
            f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
            params={"feed": "iex"},
            headers={
                "APCA-API-KEY-ID": ALPACA_KEY_ID,
                "APCA-API-SECRET-KEY": ALPACA_SECRET,
            },
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code == 429:
            return None, DegradedState("alpaca", "rate limited (200/min)")
        if r.status_code != 200:
            return None, DegradedState("alpaca", f"HTTP {r.status_code}")
        t = r.json().get("trade") or {}
        if "p" not in t:
            return None, DegradedState("alpaca", f"no trade for {symbol}")
        return {
            "symbol": symbol,
            "last": t["p"],
            "size": t.get("s"),
            "asof": t.get("t"),
            "feed": "iex",
        }, None
    except requests.RequestException as e:
        return None, DegradedState("alpaca", f"network: {type(e).__name__}")


def _twelvedata_quote(symbol: str):
    if not TWELVEDATA_KEY:
        return None, DegradedState("twelvedata", "TWELVEDATA_API_KEY not set")
    try:
        r = _session.get(
            "https://api.twelvedata.com/quote",
            params={"symbol": symbol, "apikey": TWELVEDATA_KEY},
            timeout=HTTP_TIMEOUT,
        )
        j = r.json()
        if j.get("status") == "error" or "close" not in j:
            return None, DegradedState(
                "twelvedata", j.get("message", "no quote payload")[:120]
            )
        return {
            "symbol": symbol,
            "last": float(j["close"]),
            "change": float(j.get("change", 0) or 0),
            "change_pct": float(j.get("percent_change", 0) or 0),
            "prev_close": float(j.get("previous_close", 0) or 0),
            "asof": j.get("timestamp"),
        }, None
    except (requests.RequestException, ValueError) as e:
        return None, DegradedState("twelvedata", f"network/parse: {type(e).__name__}")


def _finnhub_shares(symbol: str):
    if not FINNHUB_KEY:
        return None, DegradedState("finnhub", "FINNHUB_API_KEY not set")
    try:
        r = _session.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code == 429:
            return None, DegradedState("finnhub", "rate limited (60/min)")
        if r.status_code != 200:
            return None, DegradedState("finnhub", f"HTTP {r.status_code}")
        j = r.json()
        so = j.get("shareOutstanding")
        if not so:
            return None, DegradedState(
                "finnhub", f"profile2 empty for {symbol} (ETF/index?)"
            )
        # Finnhub reports in millions
        return {"symbol": symbol, "shares_outstanding": float(so) * 1_000_000}, None
    except requests.RequestException as e:
        return None, DegradedState("finnhub", f"network: {type(e).__name__}")


def _alphavantage_shares(symbol: str):
    """Nightly-snapshot use only: free tier is ~25 requests/DAY."""
    if not ALPHAVANTAGE_KEY:
        return None, DegradedState("alphavantage", "ALPHAVANTAGE_API_KEY not set")
    try:
        r = _session.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": ALPHAVANTAGE_KEY,
            },
            timeout=HTTP_TIMEOUT,
        )
        j = r.json()
        if "Note" in j or "Information" in j:
            return None, DegradedState("alphavantage", "daily quota exhausted (25/day)")
        so = j.get("SharesOutstanding")
        if not so or so in ("None", "-"):
            return None, DegradedState("alphavantage", f"no SharesOutstanding for {symbol}")
        return {"symbol": symbol, "shares_outstanding": float(so)}, None
    except (requests.RequestException, ValueError) as e:
        return None, DegradedState("alphavantage", f"network/parse: {type(e).__name__}")


# --------------------------------------------------------- public chains ----

@ttl_cached(60)
def get_quote(symbol: str) -> ProviderResult:
    """Keyed-quote fallback chain: Alpaca IEX -> Finnhub -> Twelve Data.

    NOTE: the Yahoo chart endpoint (direct from Render, already in the stub)
    remains the primary tape source. Call this when that path degrades, or
    wire it as the stub's fallback inside /api/tape.
    """
    misses: list[DegradedState] = []
    for fn, source, tier in (
        (_alpaca_quote, "alpaca-iex", "[T2]"),
        (_finnhub_quote, "finnhub", "[T2]"),
        (_twelvedata_quote, "twelvedata", "[T2]"),
    ):
        data, miss = fn(symbol)
        if data:
            return ProviderResult(True, data, source, tier, misses)
        misses.append(miss)
    return ProviderResult(False, None, "", "", misses)


@ttl_cached(6 * 3600)
def get_shares_outstanding(symbol: str) -> ProviderResult:
    """Shares ladder (v5): Finnhub profile2 -> Alpha Vantage OVERVIEW.

    During the parallel run, get_shares_full on the Streamlit Cloud IP stays
    rung 1 of the ladder; this chain is rungs 2-3 and the whole ladder once
    the accrual moves to Render. 6h cache: shares don't move intraday, and it
    protects the Alpha Vantage 25/day budget.
    """
    misses: list[DegradedState] = []
    for fn, source, tier in (
        (_finnhub_shares, "finnhub-profile2", "[T2]"),
        (_alphavantage_shares, "alphavantage-overview", "[T3]"),
    ):
        data, miss = fn(symbol)
        if data:
            return ProviderResult(True, data, source, tier, misses)
        misses.append(miss)
    return ProviderResult(False, None, "", "", misses)


# ------------------------------------------------------------ diagnostics ---

def provider_status() -> dict:
    """For a /api/providers health endpoint: which keys are present (never the
    values), plus a live one-symbol probe per configured source."""
    configured = {
        "finnhub": bool(FINNHUB_KEY),
        "alpaca": bool(ALPACA_KEY_ID and ALPACA_SECRET),
        "twelvedata": bool(TWELVEDATA_KEY),
        "alphavantage": bool(ALPHAVANTAGE_KEY),
    }
    probes = {}
    if configured["finnhub"]:
        d, m = _finnhub_quote("SPY")
        probes["finnhub"] = "ok" if d else m.reason
    if configured["alpaca"]:
        d, m = _alpaca_quote("SPY")
        probes["alpaca"] = "ok" if d else m.reason
    if configured["twelvedata"]:
        d, m = _twelvedata_quote("SPY")
        probes["twelvedata"] = "ok" if d else m.reason
    # Alpha Vantage deliberately not probed: 25/day is too scarce to spend here
    return {"configured": configured, "probe": probes}
