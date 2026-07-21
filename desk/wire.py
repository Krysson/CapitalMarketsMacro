"""Wire data layer — free RSS/Atom feeds, fetched concurrently.

Feeds are fetched in parallel with short timeouts, so one slow or
blocked agency can never hang the page (the failed serial+mirror
approach taught us that; total wall time is now ~one timeout, not the
sum of them). No third-party mirrors: a feed either answers us directly
or it reports down with a reason.

Known limitation: BLS sits behind Akamai, which blocks many datacenter
IPs. The BLS lane may show down on Streamlit Cloud while working fine
when the desk runs locally. The FEED DOWN reason (e.g. HTTP 403) tells
you which case you're in.
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import streamlit as st

ET = ZoneInfo("America/New_York")

# BLS has no all-releases feed (and bls_latest.rss is a one-item digest),
# so the four majors are pulled individually under one BLS source tag.
PRIMARY_FEEDS = [
    ("FED", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("BLS", "https://www.bls.gov/feed/cpi.rss"),
    ("BLS", "https://www.bls.gov/feed/empsit.rss"),
    ("BLS", "https://www.bls.gov/feed/ppi.rss"),
    ("BLS", "https://www.bls.gov/feed/jolts.rss"),
    ("BEA", "https://apps.bea.gov/rss/rss.xml"),
]
def google_url(query: str) -> str:
    """Google News RSS for a search query — free, keyless, durable."""
    from urllib.parse import quote_plus
    return (f"https://news.google.com/rss/search?q={quote_plus(query)}"
            f"&hl=en-US&gl=US&ceid=US:en")


# Aggregator lanes (Tier 5 — but fast). The release-chaser queries also
# serve as the CPI/NFP fast path on Streamlit Cloud, where Akamai blocks
# the direct BLS feeds.
GOOGLE_FEEDS = [
    ("G-FED", google_url("federal reserve FOMC when:2d")),
    ("G-CPI", google_url("CPI inflation report when:2d")),
    ("G-JOBS", google_url("jobs report nonfarm payrolls when:2d")),
    ("G-RATES", google_url("treasury yields auction when:2d")),
    ("G-OIL", google_url("oil prices OPEC supply when:2d")),
    ("G-MKT", google_url("stock market when:1d")),
]

# The release-chaser subset: aggregator lanes that track BLS releases,
# used as the visible backup when Akamai blocks the direct BLS feeds.
BLS_BACKUP_FEEDS = [f for f in GOOGLE_FEEDS if f[0] in ("G-CPI", "G-JOBS")]
GOOGLE_NARRATIVE_FEEDS = [f for f in GOOGLE_FEEDS
                          if f[0] not in ("G-CPI", "G-JOBS")]

NARRATIVE_FEEDS = [
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml"
             "?partnerId=wrss01&id=20910258"),
    ("MW", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": ("application/atom+xml, application/rss+xml, "
               "application/xml;q=0.9, */*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
}


def _reason(ex: Exception) -> str:
    import requests
    if isinstance(ex, requests.HTTPError) and ex.response is not None:
        return f"HTTP {ex.response.status_code}"
    if isinstance(ex, requests.Timeout):
        return "timeout"
    return type(ex).__name__


def _fetch_one(src: str, url: str) -> tuple[list[dict], str | None]:
    """One feed → (items, error_reason_or_None). Never raises."""
    import feedparser
    import requests

    try:
        r = requests.get(url, headers=_HEADERS, timeout=6)
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError("unparseable feed")
        items = []
        for e in parsed.entries[:25]:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            when = (dt.datetime(*ts[:6], tzinfo=dt.timezone.utc)
                    .astimezone(ET)) if ts else None
            title = (e.get("title") or "").strip()
            if title:
                items.append({"src": src, "when": when, "title": title,
                              "link": e.get("link", "")})
        return items, None
    except Exception as ex:
        return [], _reason(ex)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_tape(feeds: list[tuple[str, str]]) -> tuple[list[dict],
                                                      list[str]]:
    """Pull feeds in parallel, merge newest-first. (items, dead_sources)."""
    with ThreadPoolExecutor(max_workers=len(feeds)) as pool:
        results = list(pool.map(lambda f: _fetch_one(*f), feeds))
    items, dead = [], {}
    for (src, _), (got, err) in zip(feeds, results):
        items.extend(got)
        if err is not None:
            dead.setdefault(src, err)
    items.sort(key=lambda x: x["when"] or dt.datetime.min.replace(
        tzinfo=ET), reverse=True)
    return items[:40], [f"{s} ({r})" for s, r in dead.items()]


# ------------------------------------------------- the news ticker ----

def in_release_window(now: dt.datetime | None = None) -> bool:
    """True inside the fast-refresh windows around scheduled releases:
    8:25-9:00 ET on CPI/NFP days, 1:55-2:30 pm ET on FOMC days."""
    from desk import events

    now = now or dt.datetime.now(ET)
    d, t = now.date(), now.time()
    if d in events.CPI_RELEASES or d in events.NFP_RELEASES:
        if dt.time(8, 25) <= t <= dt.time(9, 0):
            return True
    if d in events.FOMC_STATEMENTS or d in events.FOMC_PAST_STATEMENTS:
        if dt.time(13, 55) <= t <= dt.time(14, 30):
            return True
    return False


def merge_ticker(primary_items: list[dict], other_items: list[dict],
                 n_primary: int = 5, total: int = 14) -> list[dict]:
    """Pure: reserved-slot merge with dedupe. Tier 1 agencies always
    lead; the aggregator/media lanes fill the rest by recency."""
    seen: set[str] = set()

    def keep(item: dict) -> bool:
        key = item["title"].lower()[:60]
        if key in seen or not item["title"]:
            return False
        seen.add(key)
        return True

    far_past = dt.datetime(1970, 1, 1, tzinfo=ET)
    prim = sorted((i for i in primary_items if keep(i)),
                  key=lambda i: i["when"] or far_past, reverse=True)
    rest = sorted((i for i in other_items if keep(i)),
                  key=lambda i: i["when"] or far_past, reverse=True)
    out = [dict(i, primary=True) for i in prim[:n_primary]]
    out += [dict(i, primary=False) for i in rest[:total - len(out)]]
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _ticker_cached(ttl: int, bucket: int) -> list[dict]:
    prim, _ = fetch_tape(PRIMARY_FEEDS)
    other, _ = fetch_tape(NARRATIVE_FEEDS + GOOGLE_FEEDS)
    return merge_ticker(prim, other)


def ticker_items() -> list[dict]:
    """Headlines for the scrolling ticker. Refreshes every 5 minutes
    normally, every 60 seconds inside a scheduled-release window."""
    import time
    ttl = 60 if in_release_window() else 300
    try:
        return _ticker_cached(ttl, int(time.time() // ttl))
    except Exception:
        return []
