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


# ------------------------------------------------- v4.9.0: fiscal ----
# fiscaldata.treasury.gov — official, free, keyless. House rule: the
# daily official series is primary; FRED's weekly WTREGEN is the
# fallback (wired in data.net_liquidity). Every function fails soft
# with a named reason and returns an empty frame/series — callers
# render explained empties, never tracebacks.
_FISCAL_API = ("https://api.fiscaldata.treasury.gov/services/api/"
               "fiscal_service")


def _fiscal_get(path: str, params: str) -> list[dict]:
    r = requests.get(f"{_FISCAL_API}{path}?{params}",
                     headers=_HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("data", [])


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def tga_daily() -> "pd.Series":
    """TGA closing balance from the Daily Treasury Statement, $mm,
    daily. Account naming changed across DTS vintages, so rows are
    matched by substring, and the balance column is whichever of the
    known candidates the vintage carries."""
    import pandas as pd
    try:
        rows = _fiscal_get(
            "/v1/accounting/dts/operating_cash_balance",
            "sort=-record_date&page[size]=900")
        df = pd.DataFrame(rows)
        if df.empty or "account_type" not in df:
            return pd.Series(dtype=float)
        m = df["account_type"].str.contains(
            "Treasury General Account|Federal Reserve Account",
            case=False, na=False)
        df = df[m]
        col = next((c for c in ("close_today_bal", "closing_balance",
                                "open_today_bal") if c in df), None)
        if col is None or df.empty:
            return pd.Series(dtype=float)
        s = pd.Series(
            pd.to_numeric(df[col], errors="coerce").values,
            index=pd.to_datetime(df["record_date"]).values,
            name="TGA ($mm, DTS daily)").dropna().sort_index()
        return s[~s.index.duplicated(keep="last")]
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def debt_to_penny() -> tuple[float, str] | None:
    """Latest total public debt outstanding ($) and its date."""
    try:
        rows = _fiscal_get(
            "/v2/accounting/od/debt_to_penny",
            "fields=record_date,tot_pub_debt_out_amt"
            "&sort=-record_date&page[size]=1")
        if rows:
            return (float(rows[0]["tot_pub_debt_out_amt"]),
                    rows[0]["record_date"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def interest_expense_fytd() -> tuple[float, str] | None:
    """Fiscal-year-to-date interest expense on the public debt ($).
    Field names vary by vintage; matched from known candidates."""
    try:
        rows = _fiscal_get(
            "/v2/accounting/od/interest_expense",
            "sort=-record_date&page[size]=60")
        for row in rows:
            for k in ("fytd_expense_amt", "fytd_intexp_amt",
                      "intexp_fytd_amt"):
                if row.get(k) not in (None, "", "null"):
                    return (float(row[k]), row.get("record_date", "?"))
    except Exception:
        pass
    return None
