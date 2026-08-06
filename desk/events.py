"""Scheduled macro events — published calendars, hardcoded on purpose.

Both agencies publish these dates up to a year ahead, so a static list is
the reliable free-data approach (no API, nothing to rate-limit, nothing
to fail). The cost: someone has to refresh the lists when new calendars
drop. The Summary strip shows a maintenance nudge when a list runs dry.

CPI       — BLS release dates, 8:30 a.m. ET.
            Source: bls.gov/schedule/news_release/cpi.htm
NFP       — BLS Employment Situation release dates, 8:30 a.m. ET.
            Source: bls.gov/schedule/news_release/empsit.htm
FOMC      — statement day (day 2 of each meeting), 2:00 p.m. ET.
            Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
            2027 dates are the Fed's *tentative* schedule (Sept 2025
            press release) — each is confirmed at the prior meeting.

Last verified: 2026-07-20.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

CPI_RELEASES = [
    dt.date(2026, 8, 12),   # Jul 2026 data
    dt.date(2026, 9, 11),   # Aug 2026 data
    dt.date(2026, 10, 14),  # Sep 2026 data
    dt.date(2026, 11, 10),  # Oct 2026 data
    dt.date(2026, 12, 10),  # Nov 2026 data
    # Dec 2026 data releases in Jan 2027 — add when BLS posts the
    # 2027 schedule (usually late summer / fall 2026).
]

NFP_RELEASES = [
    dt.date(2026, 8, 7),    # Jul 2026 data
    dt.date(2026, 9, 4),    # Aug 2026 data
    dt.date(2026, 10, 2),   # Sep 2026 data
    dt.date(2026, 11, 6),   # Oct 2026 data
    dt.date(2026, 12, 4),   # Nov 2026 data
    # Dec 2026 data releases in Jan 2027 — refresh with the 2027 schedule.
]

FOMC_STATEMENTS = [
    dt.date(2026, 7, 29),   # Jul 28–29
    dt.date(2026, 9, 16),   # Sep 15–16 (SEP / dot plot)
    dt.date(2026, 10, 28),  # Oct 27–28
    dt.date(2026, 12, 9),   # Dec 8–9  (SEP / dot plot)
    dt.date(2027, 1, 27),   # tentative from here down
    dt.date(2027, 3, 17),
    dt.date(2027, 4, 28),
    dt.date(2027, 6, 9),
    dt.date(2027, 7, 28),
    dt.date(2027, 9, 15),
    dt.date(2027, 10, 27),
    dt.date(2027, 12, 8),
]


@dataclass
class NextEvent:
    name: str
    date: dt.date | None
    time_note: str
    today: dt.date = None  # injectable for tests; defaults to real today

    def __post_init__(self):
        if self.today is None:
            self.today = dt.date.today()

    @property
    def days_until(self) -> int | None:
        if self.date is None:
            return None
        return (self.date - self.today).days

    @property
    def when(self) -> str:
        """'today · 2:00 p.m. ET' / 'tomorrow' / 'Wed Aug 12 · in 23d'."""
        d = self.days_until
        if d is None:
            return "schedule needs updating — see desk/events.py"
        if d == 0:
            return f"today · {self.time_note}"
        if d == 1:
            return f"tomorrow ({self.date:%a %b %-d})"
        return f"{self.date:%a %b %-d} · in {d}d"


def _next(dates: list[dt.date], today: dt.date) -> dt.date | None:
    future = [d for d in dates if d >= today]
    return min(future) if future else None


def next_cpi(today: dt.date | None = None) -> NextEvent:
    today = today or dt.date.today()
    return NextEvent("CPI", _next(CPI_RELEASES, today), "8:30 a.m. ET", today)


def next_fomc(today: dt.date | None = None) -> NextEvent:
    today = today or dt.date.today()
    return NextEvent("FOMC", _next(FOMC_STATEMENTS, today), "2:00 p.m. ET",
                     today)


def next_nfp(today: dt.date | None = None) -> NextEvent:
    today = today or dt.date.today()
    return NextEvent("NFP", _next(NFP_RELEASES, today), "8:30 a.m. ET",
                     today)


# Past FOMC statement days (for the statement-diff tool). Post-meeting
# dates from FOMC_STATEMENTS are appended automatically once they pass.
FOMC_PAST_STATEMENTS = [
    dt.date(2025, 1, 29), dt.date(2025, 3, 19), dt.date(2025, 5, 7),
    dt.date(2025, 6, 18), dt.date(2025, 7, 30), dt.date(2025, 9, 17),
    dt.date(2025, 10, 29), dt.date(2025, 12, 10),
    dt.date(2026, 1, 28), dt.date(2026, 3, 18), dt.date(2026, 4, 29),
    dt.date(2026, 6, 17),
]


def past_statements(today: dt.date | None = None) -> list[dt.date]:
    """All statement days that have occurred, newest first."""
    today = today or dt.date.today()
    all_ = FOMC_PAST_STATEMENTS + [d for d in FOMC_STATEMENTS if d <= today]
    return sorted(set(all_), reverse=True)


def opex_dates(months: int = 6,
               start: dt.date | None = None) -> list[dict]:
    """Monthly options expiration (third Friday) with the quarterly
    triple-witching flag. v4.9.0. Pure computation — the one calendar
    on the desk that needs no publisher, so it can never go stale and
    never shows FEED DOWN. (Exchange holiday shifts — a third Friday
    that is a market holiday settles Thursday — are rare enough that
    the chip says 'third Friday', not 'settlement day'.)"""
    start = start or dt.date.today()
    out, y, m = [], start.year, start.month
    for _ in range(months + 1):
        d = dt.date(y, m, 15)
        d += dt.timedelta((4 - d.weekday()) % 7)  # Fri on/after 15th
        out.append({"date": d, "witching": m in (3, 6, 9, 12)})
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return [o for o in out if o["date"] >= start][:months]
