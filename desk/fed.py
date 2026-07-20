"""Fed statement fetch, parse, and word-level diff. DIFF <GO>.

Statements live at a predictable URL per date. The diff is the product:
the FOMC changes as few words as possible on purpose, so every changed
word is a decision someone argued about in that room.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re

import requests
import streamlit as st

_HEADERS = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0 Safari/537.36")}


def statement_url(d: dt.date) -> str:
    return (f"https://www.federalreserve.gov/newsevents/pressreleases/"
            f"monetary{d:%Y%m%d}a.htm")


def html_to_text(html: str) -> str:
    """Pure: strip scripts/styles/tags, collapse whitespace."""
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&#8217;", "'").replace("&quot;", '"'))
    return re.sub(r"[ \t]+", " ", text)


def extract_statement(text: str) -> str:
    """Pure: trim page chrome to the statement body. Heuristic anchors —
    Fed statements have opened with the same handful of phrases for
    decades; the end is the vote or the implementation note."""
    starts = ["Recent indicators", "Information received",
              "Although the", "The Federal Open Market Committee",
              "Indicators of"]
    ends = ["Implementation Note", "For media inquiries",
            "Last Update:"]
    lo = min((i for p in starts if (i := text.find(p)) != -1),
             default=0)
    hi = min((i for p in ends if (i := text.find(p, lo + 50)) != -1),
             default=len(text))
    body = text[lo:hi].strip()
    return re.sub(r"\n{2,}", "\n\n", body)


@st.cache_data(ttl=86400, show_spinner=False)
def get_statement(d: dt.date) -> str:
    """Statement text for a date; '' on failure."""
    try:
        r = requests.get(statement_url(d), headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return extract_statement(html_to_text(r.text))
    except Exception:
        return ""


def word_diff(old: str, new: str) -> list[tuple[str, str]]:
    """Pure: token diff -> [(op, text)] with op in equal/insert/delete."""
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(("equal", " ".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(("delete", " ".join(a[i1:i2])))
            if j2 > j1:
                out.append(("insert", " ".join(b[j1:j2])))
    return out


def diff_stats(ops: list[tuple[str, str]]) -> tuple[int, int]:
    """(words_added, words_removed)."""
    add = sum(len(t.split()) for op, t in ops if op == "insert")
    rem = sum(len(t.split()) for op, t in ops if op == "delete")
    return add, rem
