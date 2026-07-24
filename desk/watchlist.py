"""The Watchlist — the funnel's parking lot. Ch. 15: 'a candidate
passes all five gates or goes to the watchlist.' Now it has somewhere
to go. Symbol + REASON + generator + price-when-added; the '% since
added' column quietly scores your watching. Local JSON like the
Notebook. No automated alerts on watch levels — the bot can't see
your local file, and promising surveillance that doesn't happen would
be a lie; the morning read is when you check it."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from desk import paper

STORE = Path("watchlist.json")


def load() -> list[dict]:
    if STORE.exists():
        try:
            w = json.loads(STORE.read_text())
            if isinstance(w, list):
                return w
        except Exception:
            pass
    return []


def save(items: list[dict]) -> None:
    STORE.write_text(json.dumps(items, indent=2))


def add(items, symbol, reason, generator="", trigger="") -> tuple[bool, str]:
    symbol = symbol.upper().strip()
    if not symbol:
        return False, "No symbol."
    if any(i["symbol"] == symbol for i in items):
        return False, f"{symbol} already on the list."
    if len(reason.strip()) < 8:
        return False, ("A watchlist entry without a reason is a "
                       "ticker collection. Why are you watching?")
    px = paper.mark(symbol)
    items.insert(0, {"symbol": symbol, "reason": reason.strip(),
                     "generator": generator, "trigger": trigger.strip(),
                     "added": dt.date.today().isoformat(),
                     "px_added": px})
    return True, f"{symbol} parked ({'@ ' + format(px, ',.2f') if px else 'no mark yet'})."


def table(items) -> pd.DataFrame:
    rows = []
    for i in items:
        m = paper.mark(i["symbol"])
        p0 = i.get("px_added")
        rows.append({"Symbol": i["symbol"], "Added": i["added"],
                     "@ Add": p0, "Last": m,
                     "Since %": ((m / p0 - 1) * 100
                                 if (m and p0) else None),
                     "Gen": (i.get("generator") or "").split(" ")[0],
                     "Trigger": i.get("trigger", "")[:40],
                     "Reason": i["reason"][:60]})
    return pd.DataFrame(rows)
