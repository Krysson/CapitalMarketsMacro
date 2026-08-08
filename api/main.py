"""Capital Markets Desk — Phase 0 API stub.

One job: answer the go/no-go question from Render's actual IP.
Yahoo blocks some endpoints from some datacenter ranges (GitHub
runners lose quote/fundamentals/options but keep chart — verified
22-Jul-26); whether Render's ranges are blocked decides the v5
quote architecture. GET /probe runs the full test battery and
returns a verdict. Every check fails soft with a named error —
house rules apply from line one.

alpha.2: keyed provider chain wired in (providers.py). The Yahoo
chart endpoint stays the primary tape source; on a miss, quotes
degrade to Alpaca IEX -> Finnhub -> Twelve Data with source and
tier tags carried through, and every miss stays named. Adds
/api/tape (batched, 60s cache) and /api/shares/{ticker}.
"""
import datetime as dt
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from providers import get_quote, get_shares_outstanding, provider_status

app = FastAPI(title="Capital Markets Desk API", version="5.0.0-alpha.2")

# open CORS for Phase 0 so the lovable preview / Vercel page can
# call it; Phase 4 locks this to the real origins.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET"], allow_headers=["*"])


def _attempt(fn, tries: int = 3):
    """Run one probe leg with backoff; never raise.
    -> {ok, attempts, detail | error}. v2: a shared-IP rate limit
    (Render free egresses through a pool Yahoo throttles) can pass
    on a later try — one attempt can't tell PARTIAL from NO-GO."""
    last = None
    for i in range(tries):
        try:
            return {"ok": True, "attempts": i + 1, "detail": fn()}
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:160]}"
            if i < tries - 1:
                time.sleep(3 * (i + 1))
    return {"ok": False, "attempts": tries, "error": last}


def _session():
    """Browser-impersonated HTTP session (curl_cffi). The Streamlit
    app's fetches succeed partly on the strength of this; give the
    probe the same footing. Falls back to yfinance's default."""
    try:
        from curl_cffi import requests as _cf
        return _cf.Session(impersonate="chrome")
    except Exception:
        return None


# ------------------------------------------------------------- tape core ----

# The tape is Yahoo-chart-first (the endpoint that answers from this
# host — Phase 0 verdict), keyed chain second. Per-batch cache, 60s,
# successes only, same pattern as providers.py's per-symbol cache.
_TAPE_TTL = 60
_tape_cache: dict[str, tuple[float, dict]] = {}


def _yahoo_batch_closes(symbols: list[str]) -> dict[str, dict]:
    """One batched chart-endpoint pull for the whole tape. Returns
    {symbol: row} for every symbol that answered; missing symbols
    simply aren't in the dict — the caller sends those to the keyed
    chain. Raises only if the entire batch fails."""
    import pandas as pd
    import yfinance as yf

    df = yf.download(symbols, period="2d", auto_adjust=True,
                     progress=False, threads=True)
    if df is None or df.empty:
        raise ValueError("chart endpoint returned no rows for batch")

    closes = df["Close"]
    if isinstance(closes, pd.Series):          # single-symbol shape
        closes = closes.to_frame(name=symbols[0])

    out: dict[str, dict] = {}
    for sym in symbols:
        if sym not in closes.columns:
            continue
        col = closes[sym].dropna()
        if col.empty:
            continue
        last = float(col.iloc[-1])
        prev = float(col.iloc[-2]) if len(col) > 1 else None
        out[sym] = {
            "symbol": sym,
            "price": round(last, 4),
            "change_pct": (round((last / prev - 1) * 100, 3)
                           if prev else None),
            "asof": str(col.index[-1])[:10],
            "source": "yahoo-chart",
            "tier": "[T2]",
            "degraded": [],
        }
    return out


def _tape_rows(symbols: list[str]) -> dict:
    """Assemble the tape: Yahoo batch first, keyed chain for the
    stragglers, named miss for anything neither could serve.
    Empties must explain themselves."""
    rows: dict[str, dict] = {}
    batch_error = None
    try:
        rows = _yahoo_batch_closes(symbols)
    except Exception as e:
        batch_error = f"{type(e).__name__}: {str(e)[:160]}"

    for sym in symbols:
        if sym in rows:
            continue
        misses = ([{"source": "yahoo-chart", "reason": batch_error}]
                  if batch_error else
                  [{"source": "yahoo-chart",
                    "reason": f"no rows for {sym} in batch"}])
        keyed = get_quote(sym)
        if keyed.ok:
            d = keyed.data
            rows[sym] = {
                "symbol": sym,
                "price": round(float(d["last"]), 4),
                "change_pct": d.get("change_pct"),
                "asof": str(d.get("asof")),
                "source": keyed.source,
                "tier": keyed.tier,
                "degraded": misses + [
                    {"source": m.source, "reason": m.reason}
                    for m in keyed.degraded],
            }
        else:
            rows[sym] = {
                "symbol": sym,
                "price": None,
                "error": "all sources degraded",
                "degraded": misses + [
                    {"source": m.source, "reason": m.reason}
                    for m in keyed.degraded],
            }
    return rows


# ---------------------------------------------------------------- routes ----

@app.get("/")
def root():
    return {"service": "capital-markets-desk-api",
            "phase": 0,
            "utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "next": "GET /probe for the Yahoo go/no-go battery"}


@app.get("/api/health")
def health():
    return {"status": "up"}


@app.get("/api/providers")
def providers_health():
    return provider_status()


@app.get("/api/tape")
def tape(symbols: str = "SPY,QQQ,IWM,DIA,TLT,GLD,USO,UUP"):
    """Batched tape for the scaffold header. ?symbols=SPY,QQQ,...
    (comma-separated, up to 25). 60s in-process cache per distinct
    batch; Yahoo chart primary, keyed chain fallback per symbol."""
    syms = sorted({s.strip().upper() for s in symbols.split(",")
                   if s.strip()})[:25]
    if not syms:
        return {"error": "no symbols given", "rows": {}}

    key = ",".join(syms)
    now = time.monotonic()
    hit = _tape_cache.get(key)
    if hit and now - hit[0] < _TAPE_TTL:
        return hit[1]

    rows = _tape_rows(syms)
    payload = {
        "utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "cache_ttl_s": _TAPE_TTL,
        "rows": rows,
    }
    if all(r.get("price") is not None for r in rows.values()):
        _tape_cache[key] = (now, payload)   # cache full successes only
    return payload


@app.get("/api/quote/{ticker}")
def quote(ticker: str):
    """Single quote: Yahoo chart endpoint first (the one that always
    answered from bot IPs), keyed chain on a miss. The response
    names every source that failed before one answered."""
    import yfinance as yf

    sym = ticker.upper()

    def _leg():
        h = yf.Ticker(sym).history(period="2d", auto_adjust=True)
        if h.empty:
            raise ValueError("chart endpoint returned no rows")
        last = h["Close"].dropna()
        return {"ticker": sym,
                "price": round(float(last.iloc[-1]), 4),
                "asof": str(last.index[-1])[:10],
                "source": "yahoo-chart",
                "tier": "[T2]",
                "degraded": []}
    out = _attempt(_leg)
    if out["ok"]:
        return out["detail"]

    misses = [{"source": "yahoo-chart", "reason": out["error"]}]
    keyed = get_quote(sym)
    if keyed.ok:
        d = keyed.data
        return {"ticker": sym,
                "price": round(float(d["last"]), 4),
                "asof": str(d.get("asof")),
                "source": keyed.source,
                "tier": keyed.tier,
                "degraded": misses + [
                    {"source": m.source, "reason": m.reason}
                    for m in keyed.degraded]}
    return {"ticker": sym,
            "price": None,
            "error": "all sources degraded",
            "degraded": misses + [{"source": m.source, "reason": m.reason}
                                  for m in keyed.degraded]}


@app.get("/api/shares/{ticker}")
def shares(ticker: str):
    """Shares outstanding via the keyed ladder (Finnhub profile2 ->
    Alpha Vantage OVERVIEW when configured). During the parallel run
    the accrual on the Streamlit Cloud IP stays rung 1; this is the
    Render-side ladder. Finnhub's profile2 is thin for ETFs — an
    empty here is expected for SPY-type tickers and says so."""
    return {"ticker": ticker.upper(),
            **get_shares_outstanding(ticker.upper()).to_payload()}


@app.get("/probe")
def probe():
    """The go/no-go battery. Four legs against SPY from THIS host's
    IP, plus a verdict block that maps straight onto the migration
    spec's decision:
      quotes_direct   — fast_info answers: live quotes can be direct
      chart_ok        — history answers: fallback pipe exists
      options_direct  — chains answer WITH nonzero OI: walls/flows
                        machinery can run on the backend
      shares_updating — get_shares_full answers AND varies: the
                        v4.9.2 flow fix will hold here too
    """
    import pandas as pd
    import yfinance as yf

    sess = _session()
    tk = yf.Ticker("SPY", session=sess) if sess else yf.Ticker("SPY")
    legs = {"impersonated_session": bool(sess)}

    def chart():
        h = tk.history(period="5d", auto_adjust=True)
        if h.empty:
            raise ValueError("no rows")
        return {"last_close": round(float(h['Close'].dropna().iloc[-1]), 2),
                "rows": int(len(h))}
    legs["chart"] = _attempt(chart)

    def fast():
        fi = tk.fast_info
        px = fi.get("last_price")
        if not px:
            raise ValueError("last_price empty/None")
        return {"last_price": round(float(px), 2)}
    legs["fast_info"] = _attempt(fast)

    def chains():
        exps = tk.options
        if not exps:
            raise ValueError("no expiries listed")
        ch = tk.option_chain(exps[0])
        oi = int(pd.to_numeric(ch.calls["openInterest"],
                               errors="coerce").fillna(0).sum()
                 + pd.to_numeric(ch.puts["openInterest"],
                                 errors="coerce").fillna(0).sum())
        return {"front_expiry": exps[0], "rows":
                int(len(ch.calls) + len(ch.puts)),
                "total_oi": oi,
                "oi_zeroed": oi == 0}
    legs["option_chain"] = _attempt(chains)

    def shares_leg():
        s = tk.get_shares_full(
            start=pd.Timestamp.now() - pd.Timedelta(days=30))
        if s is None or not len(s):
            raise ValueError("empty series")
        tail = s.dropna().tail(5)
        return {"latest": int(tail.iloc[-1]),
                "distinct_last5": int(tail.nunique()),
                "static": bool(tail.nunique() <= 1)}
    legs["shares_full"] = _attempt(shares_leg)

    ch_ok = legs["chart"]["ok"]
    q_ok = legs["fast_info"]["ok"]
    o_ok = (legs["option_chain"]["ok"]
            and not legs["option_chain"]["detail"]["oi_zeroed"])
    s_ok = (legs["shares_full"]["ok"]
            and not legs["shares_full"]["detail"]["static"])
    return {
        "host": "render",
        "utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "legs": legs,
        "verdict": {
            "chart_ok": ch_ok,
            "quotes_direct": q_ok,
            "options_direct": o_ok,
            "shares_updating": s_ok,
            "go_no_go": (
                "GO — direct quotes and chains from this host; v5 "
                "serves live" if (q_ok and o_ok) else
                "PARTIAL — chart pipe works; quotes/chains route "
                "through the accrual+cache pattern" if ch_ok else
                "NO-GO/THROTTLED — nothing answered even with "
                "retries + impersonation; if errors say RateLimit "
                "it's the shared-IP pool, not a block — re-probe at "
                "a different hour before treating this as final; "
                "either way v5 serves from the record first"),
        },
    }
