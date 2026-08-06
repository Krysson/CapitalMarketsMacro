"""Capital Markets Desk — Phase 0 API stub.

One job: answer the go/no-go question from Render's actual IP.
Yahoo blocks some endpoints from some datacenter ranges (GitHub
runners lose quote/fundamentals/options but keep chart — verified
22-Jul-26); whether Render's ranges are blocked decides the v5
quote architecture. GET /probe runs the full test battery and
returns a verdict. Every check fails soft with a named error —
house rules apply from line one.
"""
import datetime as dt

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Capital Markets Desk API", version="5.0.0-alpha.0")

# open CORS for Phase 0 so the lovable preview / Vercel page can
# call it; Phase 4 locks this to the real origins.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET"], allow_headers=["*"])


def _attempt(fn):
    """Run one probe leg; never raise. -> {ok, detail | error}."""
    try:
        return {"ok": True, "detail": fn()}
    except Exception as e:
        return {"ok": False,
                "error": f"{type(e).__name__}: {str(e)[:160]}"}


@app.get("/")
def root():
    return {"service": "capital-markets-desk-api",
            "phase": 0,
            "utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "next": "GET /probe for the Yahoo go/no-go battery"}


@app.get("/api/health")
def health():
    return {"status": "up"}


@app.get("/api/quote/{ticker}")
def quote(ticker: str):
    """Minimal quote via the chart endpoint (the one that always
    answered from bot IPs). Proves the basic pipe."""
    import yfinance as yf

    def _leg():
        h = yf.Ticker(ticker.upper()).history(period="2d",
                                              auto_adjust=True)
        if h.empty:
            raise ValueError("chart endpoint returned no rows")
        last = h["Close"].dropna()
        return {"ticker": ticker.upper(),
                "price": round(float(last.iloc[-1]), 4),
                "asof": str(last.index[-1])[:10],
                "source": "yahoo chart endpoint [T2]"}
    out = _attempt(_leg)
    return out["detail"] if out["ok"] else {"ticker": ticker.upper(),
                                            "error": out["error"]}


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

    tk = yf.Ticker("SPY")
    legs = {}

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

    def shares():
        s = tk.get_shares_full(
            start=pd.Timestamp.now() - pd.Timedelta(days=30))
        if s is None or not len(s):
            raise ValueError("empty series")
        tail = s.dropna().tail(5)
        return {"latest": int(tail.iloc[-1]),
                "distinct_last5": int(tail.nunique()),
                "static": bool(tail.nunique() <= 1)}
    legs["shares_full"] = _attempt(shares)

    ch_ok = legs["chart"]["ok"]
    q_ok = legs["fast_info"]["ok"]
    o_ok = (legs["option_chain"]["ok"]
            and not legs["option_chain"]["detail"]["oi_zeroed"])
    s_ok = (legs["shares_full"]["ok"]
            and not legs["shares_full"]["detail"]["static"])
    return {
        "host": "render" ,
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
                "NO-GO — Yahoo dark from this host; all market data "
                "rides the data branch / Supabase"),
        },
    }
