"""API receipts (v4.7) — every Claude call writes one line: when,
which surface, tokens in/out. Local CSV like the book; the desk pays
only when a button is pressed, and now it keeps the receipt."""
import csv
import datetime as dt
from pathlib import Path

STORE = Path("api_usage.csv")


def log(surface: str, tokens_in: int, tokens_out: int) -> None:
    try:
        new = not STORE.exists()
        with STORE.open("a", newline="") as f:
            wr = csv.writer(f)
            if new:
                wr.writerow(["ts", "surface", "in", "out"])
            wr.writerow([dt.datetime.now().isoformat(timespec="seconds"),
                         surface, tokens_in, tokens_out])
    except Exception:
        pass


def totals() -> tuple[int, int, int]:
    """(calls, tokens_in, tokens_out) lifetime, local file."""
    try:
        rows = list(csv.DictReader(STORE.open()))
        return (len(rows), sum(int(r["in"]) for r in rows),
                sum(int(r["out"]) for r in rows))
    except Exception:
        return 0, 0, 0
