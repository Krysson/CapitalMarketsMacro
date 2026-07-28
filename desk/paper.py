"""Paper engine v4.2 — reconciliation, brackets, spreads, options,
the blotter's math, and a configurable book.

The engine only exists while someone looks at it (Streamlit has no
background process), so resting orders are evaluated ON EVERY LOOK:
a stop is an intention, not a guarantee — if price gapped past your
level since the desk last looked, you fill near the gap, because
that's what real stops do. Options are LONG single-leg SPY/QQQ only,
marked at mid, charged the spread at entry and exit (the honest cost)
and settled at intrinsic on expiry. Spreads are ONE position with two
legs and ONE kill switch — a spread is a single thesis about a
relationship. No manual marks, ever: self-reported marks are where
paper books go to lie to their owners.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

import pandas as pd

from desk import data

STORE = Path("paper_book.json")
DEFAULT_CASH = 1_000_000.0

GENERATORS = [
    "G1 Divergence", "G2 Crowding", "G3 Catalyst", "G4 Constraint map",
    "G5 Regime transition", "G6 Flow anomaly", "G7 Relative value",
    "G8 Narrative gap", "COINCIDENCE (two+ named in thesis)",
]
GATES = ["Edge source named", "Why-now dated", "Kill switch written",
         "Expression honest", "Size survivable"]

FUTURES = {
    "ES=F": ("S&P 500 E-mini", 50.0, 0.25),
    "NQ=F": ("Nasdaq 100 E-mini", 20.0, 0.25),
    "RTY=F": ("Russell 2000 E-mini", 50.0, 0.10),
    "ZN=F": ("10Y Note", 1000.0, 0.015625),
    "ZB=F": ("30Y Bond", 1000.0, 0.03125),
    "CL=F": ("WTI Crude", 1000.0, 0.01),
    "NG=F": ("Nat Gas", 10000.0, 0.001),
    "GC=F": ("Gold", 100.0, 0.10),
    "SI=F": ("Silver", 5000.0, 0.005),
    "HG=F": ("Copper", 25000.0, 0.0005),
    "ZC=F": ("Corn", 50.0, 0.25),
    "ZS=F": ("Soybeans", 50.0, 0.25),
    "DX=F": ("Dollar Index", 1000.0, 0.005),
    "6E=F": ("Euro FX", 125000.0, 0.00005),
}
SLIPPAGE_BPS = {"EQUITY": 5.0, "FX": 2.0, "CRYPTO": 10.0}
OPTION_UNDERLYINGS = ("SPY", "QQQ")

_FUT_EXCH = (".NYM", ".CME", ".CBT", ".CMX", ".NYB")
_MONTHS = "FGHJKMNQUVXZ"


def _fut_root(s: str) -> str | None:
    for suf in _FUT_EXCH:
        if s.endswith(suf):
            body = s[: -len(suf)]
            core = body.rstrip("0123456789")
            if (len(core) >= 2 and core[-1] in _MONTHS
                    and len(body) > len(core)):
                return core[:-1]
    return None


def asset_class(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.endswith("=F") or _fut_root(s):
        return "FUTURE"
    if s.endswith("=X"):
        return "FX"
    if s.endswith("-USD") or s.endswith("-USDT"):
        return "CRYPTO"
    return "EQUITY"


def spec(symbol: str):
    s = symbol.upper().strip()
    if s in FUTURES:
        return FUTURES[s]
    root = _fut_root(s)
    if root:
        cont = FUTURES.get(root + "=F")
        if cont:
            return (f"{cont[0]} ({s})", cont[1], cont[2])
        return None
    return s, 1.0, 0.0


def mark(symbol: str) -> float | None:
    try:
        snap = data.ticker_snapshot(symbol)
        px = snap.get("price")
        if px:
            return float(px)
    except Exception:
        pass
    try:
        o = data.ohlc(symbol, period="5d")
        if not o.empty:
            return float(o["Close"].dropna().iloc[-1])
    except Exception:
        pass
    return None


def prior_close(symbol: str) -> float | None:
    try:
        o = data.ohlc(symbol, period="5d")
        c = o["Close"].dropna()
        if len(c) >= 2:
            return float(c.iloc[-2])
    except Exception:
        pass
    return None


def fill_price(px: float, symbol: str, side: str):
    cls = asset_class(symbol)
    if cls == "FUTURE":
        sp = spec(symbol)
        slip = (sp[2] if sp else 0) or px * 0.0002
    else:
        slip = px * SLIPPAGE_BPS.get(cls, 5.0) / 10_000
    return (px + slip, slip) if side == "LONG" else (px - slip, slip)


# ---------------------------------------------------------- options ----

def parse_option(sym: str):
    """'SPY 2026-09-18 700 C' -> (und, expiry, strike, cp) or None."""
    try:
        parts = sym.upper().split()
        if len(parts) != 4:
            return None
        und, exp, k, cp = parts
        if und not in OPTION_UNDERLYINGS or cp not in ("C", "P"):
            return None
        dt.date.fromisoformat(exp)
        return und, exp, float(k), cp
    except Exception:
        return None


def option_quote(und: str, expiry: str, strike: float, cp: str):
    """(bid, ask, mid) from the live chain, or None. [T2, 15-min]."""
    try:
        import yfinance as yf
        ch = yf.Ticker(und).option_chain(expiry)
        tbl = ch.calls if cp == "C" else ch.puts
        row = tbl[abs(tbl["strike"] - strike) < 0.001]
        if row.empty:
            return None
        bid = float(row["bid"].iloc[0] or 0)
        ask = float(row["ask"].iloc[0] or 0)
        if ask <= 0:
            return None
        return bid, ask, (bid + ask) / 2
    except Exception:
        return None


# --------------------------------------------------------- the book ----

def _empty(cash: float = DEFAULT_CASH) -> dict:
    return {"cash": float(cash), "start_cash": float(cash),
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "positions": [], "log": []}


def _remote_book() -> dict | None:
    try:
        import requests

        from desk.history import OWNER, REPO
        r = requests.get(f"https://raw.githubusercontent.com/{OWNER}/"
                         f"{REPO}/data/state/paper_book.json",
                         timeout=10)
        if r.ok:
            v = json.loads(r.text)
            if isinstance(v, dict) and "positions" in v:
                return v
    except Exception:
        pass
    return None


def load_book() -> dict:
    if not STORE.exists():
        v = _remote_book()
        if v is not None:
            STORE.write_text(json.dumps(v, indent=2))
    if STORE.exists():
        try:
            b = json.loads(STORE.read_text())
            if isinstance(b, dict) and "positions" in b:
                b.setdefault("log", [])
                return b
        except Exception:
            pass
    return _empty()


def save_book(book: dict) -> None:
    STORE.write_text(json.dumps(book, indent=2))
    try:
        from desk import publish
        publish.publish_file("state/paper_book.json",
                             json.dumps(book, indent=2),
                             "paper book sync")
    except Exception:
        pass


def _log(book, msg):
    book.setdefault("log", []).insert(
        0, f"{dt.datetime.now():%d-%b %H:%M} · {msg}")
    book["log"] = book["log"][:200]


def _pos_value(p, m):
    sign = 1 if p["side"] == "LONG" else -1
    return (m - p["entry"]) * sign * p["qty"] * p["mult"]


def open_position(book: dict, *, symbol: str, side: str, qty: float,
                  generator: str, gates: list, kill_switch: str,
                  thesis: str = "", stop: float | None = None,
                  target: float | None = None) -> tuple[bool, str]:
    symbol = symbol.upper().strip()
    if not symbol:
        return False, "No symbol."
    if qty <= 0:
        return False, "Quantity must be positive."
    if generator not in GENERATORS:
        return False, ("Name the generator — 'it felt right' is not a "
                       "source (Ch. 15). Or park it on the Watchlist.")
    missing = [g for g in GATES if g not in gates]
    if missing:
        return False, (f"Unpassed gates: {', '.join(missing)}. "
                       f"That's a watchlist entry, not an order.")
    if len(kill_switch.strip()) < 15:
        return False, ("Write the kill switch as a real sentence: "
                       "'wrong if [observable] does [thing], known "
                       "within [timeframe]'. No switch, no order.")
    opt = parse_option(symbol)
    if opt:
        if side != "LONG":
            return False, ("Options are LONG-only in phase one — "
                           "naked short premium without margin "
                           "modeling is a fake free lunch.")
        und, exp, k, cp = opt
        q = option_quote(und, exp, k, cp)
        if not q:
            return False, (f"No live quote for {symbol} — check "
                           f"expiry/strike on the chain (Vol page).")
        bid, ask, mid = q
        fill = ask                      # crossing the spread IS the cost
        pos = {"id": uuid.uuid4().hex[:8],
               "opened": dt.datetime.now().isoformat(timespec="seconds"),
               "symbol": symbol, "name": f"{und} {exp} {k:g}{cp}",
               "class": "OPTION", "side": "LONG", "qty": float(qty),
               "mult": 100.0, "entry": round(fill, 4),
               "slippage": round((ask - mid) * qty * 100, 2),
               "generator": generator,
               "kill_switch": kill_switch.strip(),
               "thesis": thesis.strip(), "status": "open",
               "opt": {"und": und, "exp": exp, "k": k, "cp": cp},
               "stop": stop, "target": target}
        cost = fill * qty * 100
        if cost > book["cash"]:
            return False, f"Premium ${cost:,.0f} exceeds cash."
        book["cash"] -= cost
        book["positions"].insert(0, pos)
        _log(book, f"OPEN LONG {qty:g} {symbol} @ {fill:.2f} "
                   f"(mid {mid:.2f} — you paid the spread)")
        return True, (f"FILLED LONG {qty:g} {symbol} @ {fill:.2f} — "
                      f"mid was {mid:.2f}; the difference is the "
                      f"spread, charged honestly. Marks are 15-min "
                      f"delayed. Expires {exp}: settles at intrinsic "
                      f"if held.")
    sp = spec(symbol)
    if sp is None:
        return False, (f"{symbol}: futures month with no root spec — "
                       f"refusing a fake 1x fill. Use =F or ask for "
                       f"the spec.")
    px = mark(symbol)
    if px is None:
        return False, f"{symbol}: no mark available."
    fill, slip = fill_price(px, symbol, side)
    name, mult, _ = sp
    notional = fill * qty * mult
    if asset_class(symbol) != "FUTURE" and notional > book["cash"]:
        return False, (f"Notional ${notional:,.0f} exceeds cash "
                       f"${book['cash']:,.0f} — gate five, resize.")
    if stop is not None and stop > 0:
        bad = (side == "LONG" and stop >= fill) or \
              (side == "SHORT" and stop <= fill)
        if bad:
            return False, "Stop is on the wrong side of the fill."
    pos = {"id": uuid.uuid4().hex[:8],
           "opened": dt.datetime.now().isoformat(timespec="seconds"),
           "symbol": symbol, "name": name,
           "class": asset_class(symbol), "side": side,
           "qty": float(qty), "mult": mult, "entry": round(fill, 6),
           "slippage": round(slip * qty * mult, 2),
           "generator": generator, "kill_switch": kill_switch.strip(),
           "thesis": thesis.strip(), "status": "open",
           "stop": stop or None, "target": target or None}
    if pos["class"] != "FUTURE":
        book["cash"] -= notional
    book["positions"].insert(0, pos)
    br = ""
    if stop or target:
        br = (f" · bracket: stop {stop:g}" if stop else "") + \
             (f" target {target:g}" if target else "") + \
             " (evaluated when the desk looks — gaps fill at the gap)"
    _log(book, f"OPEN {side} {qty:g} {symbol} @ {fill:,.4f}{br}")
    return True, f"FILLED {side} {qty:g} {symbol} @ {fill:,.4f}.{br}"


def open_spread(book: dict, *, leg1: str, side1: str, leg2: str,
                side2: str, qty: float, generator: str, gates: list,
                kill_switch: str, thesis: str = "") -> tuple[bool, str]:
    """One position, two legs, one kill switch."""
    if generator not in GENERATORS:
        return False, "Name the generator."
    if [g for g in GATES if g not in gates]:
        return False, "All five gates or it's a watchlist entry."
    if len(kill_switch.strip()) < 15:
        return False, "Write the kill switch."
    if side1 == side2:
        return False, ("A spread has opposing legs — same-direction "
                       "is just two positions.")
    legs = []
    for sym, side in ((leg1, side1), (leg2, side2)):
        sym = sym.upper().strip()
        sp = spec(sym)
        if sp is None:
            return False, f"{sym}: no contract spec."
        px = mark(sym)
        if px is None:
            return False, f"{sym}: no mark."
        fill, slip = fill_price(px, sym, side)
        legs.append({"symbol": sym, "side": side, "entry": round(fill, 6),
                     "mult": sp[1], "slip": round(slip * qty * sp[1], 2)})
    if any(asset_class(l["symbol"]) != "FUTURE" for l in legs):
        return False, ("Spread tickets are futures-only for now — "
                       "equity pairs work as two positions.")
    pos = {"id": uuid.uuid4().hex[:8],
           "opened": dt.datetime.now().isoformat(timespec="seconds"),
           "symbol": f"{legs[0]['symbol']}/{legs[1]['symbol']}",
           "name": "SPREAD", "class": "SPREAD",
           "side": f"{side1[0]}/{side2[0]}", "qty": float(qty),
           "mult": 1.0, "entry": 0.0,
           "slippage": round(sum(l["slip"] for l in legs), 2),
           "generator": generator, "kill_switch": kill_switch.strip(),
           "thesis": thesis.strip(), "status": "open", "legs": legs,
           "stop": None, "target": None}
    book["positions"].insert(0, pos)
    _log(book, f"OPEN SPREAD {qty:g}x {pos['symbol']} "
               f"({side1[0]}/{side2[0]})")
    return True, (f"FILLED spread {qty:g}x {pos['symbol']} — one "
                  f"position, one thesis, one kill switch. Gross is "
                  f"large, net is the point.")


def _close(book, pos, px_map, reason, pm=""):
    if pos["class"] == "SPREAD":
        pnl = 0.0
        for l in pos["legs"]:
            m = px_map.get(l["symbol"])
            if m is None:
                return False, f"{l['symbol']}: no mark."
            exit_side = "SHORT" if l["side"] == "LONG" else "LONG"
            fill, slip = fill_price(m, l["symbol"], exit_side)
            sign = 1 if l["side"] == "LONG" else -1
            pnl += (fill - l["entry"]) * sign * pos["qty"] * l["mult"]
            l["exit"] = round(fill, 6)
            pos["slippage"] = round(pos["slippage"]
                                    + slip * pos["qty"] * l["mult"], 2)
        book["cash"] += pnl
    elif pos["class"] == "OPTION":
        o = pos["opt"]
        q = option_quote(o["und"], o["exp"], o["k"], o["cp"])
        if reason == "EXPIRY" or not q:
            u = mark(o["und"])
            if u is None:
                return False, "no underlying mark for settlement"
            intr = max(0.0, (u - o["k"]) if o["cp"] == "C"
                       else (o["k"] - u))
            fill = intr
        else:
            fill = q[0]                       # sell at bid: spread paid
            pos["slippage"] = round(pos["slippage"]
                                    + (q[2] - q[0]) * pos["qty"] * 100, 2)
        pnl = (fill - pos["entry"]) * pos["qty"] * 100
        book["cash"] += fill * pos["qty"] * 100
        pos["exit"] = round(fill, 4)
    else:
        m = px_map.get(pos["symbol"])
        if m is None:
            return False, f"{pos['symbol']}: no mark."
        exit_side = "SHORT" if pos["side"] == "LONG" else "LONG"
        fill, slip = fill_price(m, pos["symbol"], exit_side)
        sign = 1 if pos["side"] == "LONG" else -1
        pnl = (fill - pos["entry"]) * sign * pos["qty"] * pos["mult"]
        pos["slippage"] = round(pos["slippage"]
                                + slip * pos["qty"] * pos["mult"], 2)
        if pos["class"] != "FUTURE":
            book["cash"] += fill * pos["qty"] * pos["mult"]
        else:
            book["cash"] += pnl
        pos["exit"] = round(fill, 6)
    pos.update({"status": "closed", "realized": round(pnl, 2),
                "closed": dt.datetime.now().isoformat(timespec="seconds"),
                "close_reason": reason, "post_mortem": pm})
    _log(book, f"CLOSE ({reason}) {pos['symbol']} — {pnl:+,.2f}")
    return True, pnl


def close_position(book, pos_id, pm=""):
    for pos in book["positions"]:
        if pos["id"] == pos_id and pos["status"] == "open":
            syms = ([l["symbol"] for l in pos["legs"]]
                    if pos["class"] == "SPREAD" else [pos["symbol"]])
            px_map = {s: mark(s) for s in syms}
            ok, r = _close(book, pos, px_map, "MANUAL", pm)
            if not ok:
                return False, r
            return True, (f"CLOSED {pos['symbol']} — realized "
                          f"{r:+,.2f}. Grade it against the kill "
                          f"switch you wrote at entry.")
    return False, "Position not found or already closed."


def reconcile(book) -> list[str]:
    """The engine's heartbeat: run on every page load. Evaluates
    stops/targets at CURRENT marks (gap-honest) and settles expired
    options. Returns event strings."""
    events = []
    today = dt.date.today()
    for pos in list(book["positions"]):
        if pos["status"] != "open":
            continue
        if pos["class"] == "OPTION":
            if dt.date.fromisoformat(pos["opt"]["exp"]) < today:
                ok, r = _close(book, pos, {}, "EXPIRY",
                               "expired — settled at intrinsic")
                if ok:
                    events.append(f"{pos['symbol']} EXPIRED — settled "
                                  f"at intrinsic, {r:+,.2f}")
                continue
        stop, target = pos.get("stop"), pos.get("target")
        if not (stop or target) or pos["class"] in ("SPREAD",):
            continue
        m = mark(pos["symbol"])
        if m is None:
            continue
        long = pos["side"] == "LONG"
        hit_stop = stop and ((long and m <= stop)
                             or (not long and m >= stop))
        hit_tgt = target and ((long and m >= target)
                              or (not long and m <= target))
        if hit_stop or hit_tgt:
            reason = "STOP" if hit_stop else "TARGET"
            ok, r = _close(book, pos, {pos["symbol"]: m}, reason,
                           f"{reason.lower()} hit while the desk "
                           f"looked; fill at market, not the level")
            if ok:
                gap = ""
                lvl = stop if hit_stop else target
                if abs(m - lvl) / lvl > 0.001:
                    gap = (f" (level {lvl:g}, filled off {m:,.4f} — "
                           f"gap risk is real)")
                events.append(f"{pos['symbol']} {reason} — "
                              f"{r:+,.2f}{gap}")
    return events


# ---------------------------------------------------------- blotter ----

def blotter_stats(book, marks_map, prior_map):
    open_pos = [p for p in book["positions"] if p["status"] == "open"]
    closed = [p for p in book["positions"] if p["status"] == "closed"]
    gross = net = unreal = day = open_val = 0.0
    for p in open_pos:
        if p["class"] == "SPREAD":
            for l in p["legs"]:
                m = marks_map.get(l["symbol"])
                pc = prior_map.get(l["symbol"])
                if m is None:
                    continue
                sign = 1 if l["side"] == "LONG" else -1
                notion = m * p["qty"] * l["mult"]
                gross += notion
                net += sign * notion
                unreal += (m - l["entry"]) * sign * p["qty"] * l["mult"]
                if pc:
                    day += (m - pc) * sign * p["qty"] * l["mult"]
            continue
        m = marks_map.get(p["symbol"])
        if m is None:
            continue
        sign = 1 if p["side"] == "LONG" else -1
        notion = m * p["qty"] * p["mult"]
        gross += abs(notion)
        net += sign * notion
        unreal += _pos_value(p, m)
        if p["class"] != "OPTION":
            open_val += notion if p["class"] != "FUTURE" else 0
        else:
            open_val += notion
        pc = prior_map.get(p["symbol"])
        if pc:
            day += (m - pc) * sign * p["qty"] * p["mult"]
    realized = sum(p.get("realized", 0) for p in closed)
    fut_unreal = sum(
        _pos_value(p, marks_map[p["symbol"]])
        for p in open_pos
        if p["class"] == "FUTURE" and marks_map.get(p["symbol"]))
    spread_unreal = sum(
        (marks_map.get(l["symbol"], l["entry"]) - l["entry"])
        * (1 if l["side"] == "LONG" else -1) * p["qty"] * l["mult"]
        for p in open_pos if p["class"] == "SPREAD"
        for l in p["legs"] if marks_map.get(l["symbol"]))
    equity = book["cash"] + open_val + fut_unreal + spread_unreal
    return {"gross": gross, "net": net, "unrealized": unreal,
            "day": day, "realized": realized, "equity": equity,
            "total_pnl": equity - book["start_cash"],
            "n_open": len(open_pos), "n_closed": len(closed),
            "slippage_paid": sum(p.get("slippage", 0)
                                 for p in book["positions"])}


def mae_mfe(pos):
    """Max adverse / favorable excursion from daily bars between open
    and close. Honest: daily granularity, no page-visit dependence."""
    try:
        if pos["class"] in ("SPREAD", "OPTION"):
            return None, None
        o = data.ohlc(pos["symbol"], period="1y")
        d0 = pd.Timestamp(pos["opened"][:10])
        d1 = pd.Timestamp(pos.get("closed", "")[:10] or dt.date.today())
        w = o[(o.index >= d0) & (o.index <= d1)]
        if w.empty:
            return None, None
        sign = 1 if pos["side"] == "LONG" else -1
        lo, hi = float(w["Low"].min()), float(w["High"].max())
        mae = (lo - pos["entry"]) * sign if sign == 1 else \
              (hi - pos["entry"]) * sign
        mfe = (hi - pos["entry"]) * sign if sign == 1 else \
              (lo - pos["entry"]) * sign
        f = pos["qty"] * pos["mult"]
        return min(mae, 0) * f, max(mfe, 0) * f
    except Exception:
        return None, None


def gen_scorecard(closed):
    rows = {}
    for p in closed:
        g = p["generator"].split(" ")[0]
        r = rows.setdefault(g, [])
        r.append(p.get("realized", 0.0))
    out = []
    for g, pnls in rows.items():
        wins = [x for x in pnls if x > 0]
        losses = [x for x in pnls if x <= 0]
        pf = (sum(wins) / abs(sum(losses))
              if losses and sum(losses) != 0 else None)
        out.append({"Generator": g, "Trades": len(pnls),
                    "Win %": 100 * len(wins) / len(pnls),
                    "Avg win": (sum(wins) / len(wins)) if wins else 0,
                    "Avg loss": (sum(losses) / len(losses))
                    if losses else 0,
                    "Profit factor": pf,
                    "Expectancy": sum(pnls) / len(pnls),
                    "Total": sum(pnls)})
    return pd.DataFrame(out).sort_values("Total", ascending=False) \
        if out else pd.DataFrame()
