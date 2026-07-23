"""Paper engine — the desk's own simulator, every asset class it watches.

Why homegrown instead of a broker API: no free API covers the desk's
whole watchlist (Alpaca has no futures or FX; futures paper is
IBKR-or-nothing and IBKR can't run here), and — the deeper reason —
because we write the fill logic, the ticket can ENFORCE the
curriculum: no order exists without its generator, its gates, and its
kill-switch sentence. The last gate of Ch. 15's funnel is a form
that refuses to submit.

Honest simulator, stated assumptions: fills at the desk's latest mark
plus a per-asset-class slippage charge (always against you — fills
are never free, and that is itself curriculum); futures use real
contract multipliers (Book II content the reader should absorb);
marks are as fresh as the data layer (turn LIVE on while managing).
Not modeled, on purpose: queue position, margin calls, financing.
Options come in 4.1 — express tails via proxies until then.

The book lives like the Notebook: a local JSON file (wiped on
redeploy — export regularly) with the same schema-tolerant restore.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

import pandas as pd

from desk import data

STORE = Path("paper_book.json")
START_CASH = 100_000.0

GENERATORS = [
    "G1 Divergence", "G2 Crowding", "G3 Catalyst", "G4 Constraint map",
    "G5 Regime transition", "G6 Flow anomaly", "G7 Relative value",
    "G8 Narrative gap", "COINCIDENCE (two+ named in thesis)",
]

GATES = ["Edge source named", "Why-now dated", "Kill switch written",
         "Expression honest", "Size survivable"]

# Futures contract specs — multiplier per 1.0 of price, tick size.
# Real numbers; knowing them IS Book II content.
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

SLIPPAGE_BPS = {"EQUITY": 5.0, "FX": 2.0, "CRYPTO": 10.0}  # futures: 1 tick


_FUT_EXCH = (".NYM", ".CME", ".CBT", ".CMX", ".NYB")   # Yahoo month
_MONTHS = "FGHJKMNQUVXZ"                               # contract codes


def _fut_root(s: str) -> str | None:
    """CLV26.NYM -> CL · ESZ26.CME -> ES. None if not month-format."""
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


def spec(symbol: str) -> tuple[str, float, float] | None:
    """(name, multiplier, tick). Non-futures: (sym, 1, 0).
    Month contracts (CLV26.NYM) inherit their root's spec — a
    specific delivery month is the same contract as the continuous.
    Returns None for a futures symbol whose root we have no spec
    for: the ticket REFUSES rather than silently filling at 1x
    (that's how a $250 loss prints as -$0)."""
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
    """Latest price from the desk's own data layer. None if unknown."""
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


def fill_price(px: float, symbol: str, side: str) -> tuple[float, float]:
    """(fill, slippage_cost_per_unit_of_price). Slippage always against
    you: buys fill higher, sells lower. Futures pay one tick; the rest
    pay class bps."""
    cls = asset_class(symbol)
    if cls == "FUTURE":
        sp = spec(symbol)
        slip = (sp[2] if sp else 0) or px * 0.0002
    else:
        slip = px * SLIPPAGE_BPS.get(cls, 5.0) / 10_000
    return (px + slip, slip) if side == "LONG" else (px - slip, slip)


# ----------------------------------------------------------- the book --

def _empty() -> dict:
    return {"cash": START_CASH, "start_cash": START_CASH,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "positions": []}


def load_book() -> dict:
    if STORE.exists():
        try:
            b = json.loads(STORE.read_text())
            if isinstance(b, dict) and "positions" in b:
                return b
        except Exception:
            pass
    return _empty()


def save_book(book: dict) -> None:
    STORE.write_text(json.dumps(book, indent=2))


def open_position(book: dict, *, symbol: str, side: str, qty: float,
                  generator: str, gates: list[str], kill_switch: str,
                  thesis: str = "") -> tuple[bool, str]:
    """The enforced ticket. Returns (ok, message). Mutates book on ok."""
    symbol = symbol.upper().strip()
    if not symbol:
        return False, "No symbol."
    if qty <= 0:
        return False, "Quantity must be positive."
    if generator not in GENERATORS:
        return False, ("Name the generator. Ideas come from the scans — "
                       "'it felt right' is not a source (Ch. 15).")
    missing = [g for g in GATES if g not in gates]
    if missing:
        return False, (f"Unpassed gates: {', '.join(missing)}. A "
                       f"candidate passes ALL five or goes to the "
                       f"watchlist — the ticket is the fifth gate's "
                       f"enforcement, not a suggestion.")
    if len(kill_switch.strip()) < 15:
        return False, ("Write the kill switch as a real sentence: "
                       "'wrong if [observable] does [thing], known "
                       "within [timeframe]'. No switch, no order — "
                       "this refusal is the whole point of the desk.")
    px = mark(symbol)
    if px is None:
        return False, (f"{symbol}: no mark available (check the symbol "
                       f"on the Quote page first).")
    sp = spec(symbol)
    if sp is None:
        return False, (f"{symbol}: recognized as a futures month but "
                       f"no contract spec for its root — the desk "
                       f"refuses to fill at a fake 1x multiplier. Use "
                       f"the continuous (=F) or ask for the spec to "
                       f"be added.")
    fill, slip = fill_price(px, symbol, side)
    name, mult, _ = sp
    notional = fill * qty * mult
    if asset_class(symbol) != "FUTURE" and notional > book["cash"]:
        return False, (f"Notional ${notional:,.0f} exceeds cash "
                       f"${book['cash']:,.0f}. Survivable size is gate "
                       f"five — resize.")
    pos = {"id": uuid.uuid4().hex[:8],
           "opened": dt.datetime.now().isoformat(timespec="seconds"),
           "symbol": symbol, "name": name,
           "class": asset_class(symbol), "side": side,
           "qty": float(qty), "mult": mult, "entry": round(fill, 6),
           "slippage": round(slip * qty * mult, 2),
           "generator": generator, "kill_switch": kill_switch.strip(),
           "thesis": thesis.strip(), "status": "open"}
    if pos["class"] != "FUTURE":
        book["cash"] -= notional
    book["positions"].insert(0, pos)
    return True, (f"FILLED {side} {qty:g} {symbol} @ {fill:,.4f} "
                  f"(mark {px:,.4f} + slippage — fills are never free).")


def close_position(book: dict, pos_id: str,
                   pm: str = "") -> tuple[bool, str]:
    for pos in book["positions"]:
        if pos["id"] == pos_id and pos["status"] == "open":
            px = mark(pos["symbol"])
            if px is None:
                return False, f"{pos['symbol']}: no mark right now."
            exit_side = "SHORT" if pos["side"] == "LONG" else "LONG"
            fill, slip = fill_price(px, pos["symbol"], exit_side)
            sign = 1 if pos["side"] == "LONG" else -1
            pnl = (fill - pos["entry"]) * sign * pos["qty"] * pos["mult"]
            pos.update({"status": "closed", "exit": round(fill, 6),
                        "closed": dt.datetime.now().isoformat(
                            timespec="seconds"),
                        "realized": round(pnl, 2),
                        "slippage": round(pos["slippage"]
                                          + slip * pos["qty"]
                                          * pos["mult"], 2),
                        "post_mortem": pm})
            if pos["class"] != "FUTURE":
                book["cash"] += fill * pos["qty"] * pos["mult"]
            else:
                book["cash"] += pnl
            return True, (f"CLOSED {pos['symbol']} @ {fill:,.4f} — "
                          f"realized {pnl:+,.2f}. Now the honest part: "
                          f"grade it in the Notebook against the kill "
                          f"switch you wrote at entry.")
    return False, "Position not found or already closed."


def unrealized(pos: dict) -> tuple[float | None, float | None]:
    """(current mark, unrealized P&L $) for an open position."""
    px = mark(pos["symbol"])
    if px is None:
        return None, None
    sign = 1 if pos["side"] == "LONG" else -1
    return px, (px - pos["entry"]) * sign * pos["qty"] * pos["mult"]


def book_stats(book: dict, marks: dict[str, float | None]) -> dict:
    """Totals from cached marks (page computes marks once). Pure."""
    open_pos = [p for p in book["positions"] if p["status"] == "open"]
    closed = [p for p in book["positions"] if p["status"] == "closed"]
    unreal = 0.0
    open_notional = 0.0
    for p in open_pos:
        px = marks.get(p["symbol"])
        if px is None:
            continue
        sign = 1 if p["side"] == "LONG" else -1
        unreal += (px - p["entry"]) * sign * p["qty"] * p["mult"]
        if p["class"] != "FUTURE":
            open_notional += px * p["qty"] * p["mult"]
    realized = sum(p.get("realized", 0.0) for p in closed)
    equity = book["cash"] + open_notional + (
        unreal if any(p["class"] == "FUTURE" for p in open_pos) else 0.0)
    # futures P&L flows through cash at close; open futures P&L is the
    # unreal term above — add it for futures-only correctness:
    equity = book["cash"] + open_notional + sum(
        (marks.get(p["symbol"], p["entry"]) - p["entry"])
        * (1 if p["side"] == "LONG" else -1) * p["qty"] * p["mult"]
        for p in open_pos if p["class"] == "FUTURE"
        and marks.get(p["symbol"]) is not None)
    return {"n_open": len(open_pos), "n_closed": len(closed),
            "unrealized": unreal, "realized": realized,
            "equity": equity,
            "total_pnl": equity - book["start_cash"],
            "slippage_paid": sum(p.get("slippage", 0.0)
                                 for p in book["positions"])}
