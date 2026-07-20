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
