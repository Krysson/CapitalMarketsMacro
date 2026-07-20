"""News Wire — free RSS feeds rendered as a terminal tape.

Two tapes, deliberately separated to teach the Data Reliability Tiers:
PRIMARY   — the agencies themselves (Fed, BLS, BEA). These are the
            releases, not coverage of them.
NARRATIVE — financial media. Useful for knowing what the crowd is being
            told; never evidence on its own.
All feeds fail soft; a dead feed drops out with a notice, the tape rolls on.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st

from desk import theme

st.set_page_config(page_title="Wire — Desk", page_icon="🗞️", layout="wide")
theme.header(
    "BOOK III · THE WIRE",
    "News Wire",
    "Two tapes. The primary tape is the source; the narrative tape is the "
    "story being told about the source. Never confuse the two.")

ET = ZoneInfo("America/New_York")

# BLS has no all-releases feed — bls.gov/feed lists per-release feeds
# (and bls_latest.rss is a single-item digest, useless on a tape), so we
# pull the four majors individually. They merge under one BLS source tag.
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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_tape(feeds: list[tuple[str, str]]) -> tuple[list[dict], list[str]]:
    """Pull and merge feeds, newest first. Returns (items, dead_sources)."""
    import urllib.parse

    import feedparser
    import requests

    # Several agencies 403 non-browser requests, and feedparser has no
    # timeout — so fetch ourselves, then parse. BLS specifically sits
    # behind Akamai, which can block datacenter IPs (like Streamlit
    # Cloud's) outright — the feed works from a home browser and fails
    # from the server. For that case we retry once through a public
    # read-only mirror (allorigins). Deliberate, narrow exception to the
    # no-third-party rule: fallback only, public data only.
    headers = {
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept": ("application/atom+xml, application/rss+xml, "
                   "application/xml;q=0.9, */*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def _get(u: str, timeout: int = 10) -> bytes:
        r = requests.get(u, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.content

    def _reason(ex: Exception) -> str:
        if isinstance(ex, requests.HTTPError) and ex.response is not None:
            return f"HTTP {ex.response.status_code}"
        if isinstance(ex, requests.Timeout):
            return "timeout"
        return type(ex).__name__

    items, dead = [], {}
    for src, url in feeds:
        try:
            try:
                content = _get(url)
            except Exception as first:
                mirror = ("https://api.allorigins.win/raw?url="
                          + urllib.parse.quote(url, safe=""))
                try:
                    content = _get(mirror, timeout=15)
                except Exception:
                    raise first
            parsed = feedparser.parse(content)
            if parsed.bozo and not parsed.entries:
                raise ValueError("unparseable feed")
            for e in parsed.entries[:25]:
                ts = e.get("published_parsed") or e.get("updated_parsed")
                when = (dt.datetime(*ts[:6], tzinfo=dt.timezone.utc)
                        .astimezone(ET)) if ts else None
                title = (e.get("title") or "").strip()
                if title:
                    items.append({"src": src, "when": when, "title": title,
                                  "link": e.get("link", "")})
        except Exception as ex:
            dead.setdefault(src, _reason(ex))
    items.sort(key=lambda x: x["when"] or dt.datetime.min.replace(
        tzinfo=ET), reverse=True)
    return items[:40], [f"{s} ({r})" for s, r in dead.items()]


def tape(label: str, tier: str, feeds: list[tuple[str, str]],
         src_color: str) -> None:
    st.subheader(label)
    st.markdown(f'<div class="desk-eyebrow" style="color:{theme.MUTED}">'
                f'{tier}</div>', unsafe_allow_html=True)
    with st.spinner("Pulling the tape…"):
        items, dead = fetch_tape(feeds)
    if dead:
        st.markdown(f'<div class="desk-note" style="color:{theme.RED}">'
                    f'FEED DOWN: {", ".join(dead)} — tape continues '
                    f'without it.</div>', unsafe_allow_html=True)
    if not items:
        st.warning("No items — all feeds unreachable. Try again shortly.")
        return
    lines = []
    for it in items:
        stamp = (it["when"].strftime("%d-%b %H:%M") if it["when"]
                 else "        --:--")
        title = it["title"].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div style="padding:3px 0;border-bottom:1px solid '
            f'rgba(232,230,225,0.06)">'
            f'<span style="color:{theme.MUTED}">{stamp} ET</span>'
            f'<span style="color:{src_color};margin:0 10px">'
            f'{it["src"]:>4}</span>'
            f'<a href="{it["link"]}" target="_blank" style="color:'
            f'{theme.TEXT};text-decoration:none">{title}</a></div>')
    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.82rem;background:{theme.PANEL};padding:10px 14px;'
        f'border-left:3px solid {src_color};border-radius:2px">'
        + "".join(lines) + "</div>",
        unsafe_allow_html=True)


tape("Primary tape", "TIER 1–2 · OFFICIAL RELEASES · THE SOURCE ITSELF",
     PRIMARY_FEEDS, theme.AMBER)
theme.note("Press releases from the Fed, BLS, and BEA — the actual "
           "documents markets reprice on, before anyone paraphrases them. "
           "When a headline here conflicts with a headline below, this "
           "one wins by definition.")

st.divider()

tape("Narrative tape", "TIER 5 · MEDIA · THE STORY ABOUT THE SOURCE",
     NARRATIVE_FEEDS, theme.PURPLE)
theme.note("Financial media. This tape tells you what the crowd is being "
           "told — which is worth knowing — but narrative is Tier 5 data: "
           "it can lag, lead, or invert the truth. Evidence for a "
           "Notebook entry comes from the tape above, never this one.")

st.page_link("pages/4_Notebook.py",
             label="Something on the tape worth logging? → Notebook",
             icon="📓")
