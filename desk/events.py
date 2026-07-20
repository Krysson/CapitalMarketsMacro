"""Scheduled macro events — published calendars, hardcoded on purpose.

Both agencies publish these dates up to a year ahead, so a static list is
the reliable free-data approach (no API, nothing to rate-limit, nothing
to fail). The cost: someone has to refresh the lists when new calendars
drop. The Summary strip shows a maintenance nudge when a list runs dry.

CPI       — BLS release dates, 8:30 a.m. ET.
            Source: bls.gov/schedule/news_release/cpi.htm
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
