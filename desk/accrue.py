"""App-side accrual (v4.4.1) — Plan B, now the plan.

The verdict from two nights of runner logs: Yahoo hard-blocks the
quote/fundamentals/options endpoints from GitHub's IP ranges even
with browser impersonation, while the chart endpoint passes. So the
bot keeps the signals row (chart endpoint) and the app — whose IPs
fetch everything fine, proven daily by the rotation monitor and the
skew curve — accrues the flow and OI records itself, committing to
the data branch through the Notebook's GH_TOKEN machinery.

Runs opportunistically on Summary-page load: if the last business
day's rows are missing and publishing is configured, fetch, append,
commit. Morning accrual is BETTER for OI: chains report refreshed
open interest overnight. If nobody opens the app for a day, the gap
is honest — and closes at the next open, since flows use shares ×
that day's close from history, not the live tape.
"""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import streamlit as st

from desk import flow as _flow
from desk import instflow as _inst
from desk import publish as _pub


def _last_bday(today: dt.date | None = None) -> str:
    d = today or dt.date.today()
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def _get_csv(path: str) -> pd.DataFrame:
    try:
        import requests
        from desk.history import OWNER, REPO
        r = requests.get(f"https://raw.githubusercontent.com/{OWNER}/"
                         f"{REPO}/data/{path}", timeout=15)
        if r.ok and r.text.strip():
            return pd.read_csv(io.StringIO(r.text))
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=4 * 3600, show_spinner=False)
def run() -> str:
    """One attempt per 4h per session-cache. Returns a status line
    for the bot strip. Never raises."""
    if not _pub.enabled():
        return ""
    target = _last_bday()
    msgs = []
    # ---- flows ----
    try:
        cur = _get_csv("history/flows.csv")
        have = set(cur["date"].astype(str)) if not cur.empty else set()
        if target not in have:
            rows = _flow.snapshot_rows(target)
            if rows:
                new = pd.concat([cur, pd.DataFrame(rows)],
                                ignore_index=True)
                csv = new.to_csv(index=False)
                sha = _pub._get_sha("history/flows.csv")
                ok, _ = _pub._put("history/flows.csv", csv,
                                  f"app accrual: flows {target}", sha)
                msgs.append(f"flows {target}: "
                            f"{'logged ' + str(len(rows)) if ok else 'commit failed'}")
                if ok:
                    _flow.load.clear()
            else:
                try:
                    import yfinance as _yf
                    _fi = _yf.Ticker("SPY").fast_info
                    probe = f"probe shares={_fi.get('shares')!r}"
                except Exception as _e:
                    probe = f"probe {type(_e).__name__}: {_e}"[:100]
                msgs.append(f"flows {target}: no rows ({probe})")
    except Exception as e:
        msgs.append(f"flows: skipped ({type(e).__name__})")
    # ---- short-volume ratios (v4.9.1) ----
    # Accrue-your-own, same as flows/signals: FINRA's daily file is
    # keyless but has no history endpoint, so the percentile view on
    # the Flow page needs a record — this builds it one session at a
    # time. The fetch reuses flow.finra_short()'s cache.
    try:
        from desk import flow as _flow
        sv_today, sv_date = _flow.finra_short()
        if not sv_today.empty:
            sv_iso = dt.datetime.strptime(
                sv_date, "%d-%b-%Y").date().isoformat()
            rec = _get_csv("history/shortvol.csv")
            have = (set(rec["date"].astype(str)) if not rec.empty
                    and "date" in rec else set())
            if sv_iso not in have:
                add = sv_today[["Symbol", "short_ratio"]].copy()
                add.insert(0, "date", sv_iso)
                add.columns = ["date", "symbol", "short_ratio"]
                allr = pd.concat([rec, add], ignore_index=True)
                sha = _pub._get_sha("history/shortvol.csv")
                ok, _ = _pub._put("history/shortvol.csv",
                                  allr.to_csv(index=False),
                                  f"app accrual: shortvol {sv_iso}",
                                  sha)
                if ok:
                    _flow.shortvol_history.clear()
                msgs.append(f"shortvol {sv_iso}: "
                            + ("stored" if ok else "commit failed"))
    except Exception as e:
        msgs.append(f"shortvol: skipped ({type(e).__name__})")
    # ---- OI ----
    try:
        latest = _get_csv("history/oi_latest.csv")
        snap_date = (str(latest["date"].iloc[0])
                     if not latest.empty and "date" in latest
                     else None)
        today = dt.date.today().isoformat()
        # v4.9.2: a record stored degraded at 7am (zero-OI feed) can
        # heal later the same day — OI often populates mid-morning.
        # Retry while the stored record is degraded; the zero-OI
        # guard below still refuses to replace healthy with zeros.
        latest_deg = (not latest.empty and "oi" in latest and float(
            pd.to_numeric(latest["oi"], errors="coerce")
            .fillna(0).sum()) <= 0)
        if snap_date != today or latest_deg:
            snap = _inst.oi_snapshot(today)
            if snap is not None and not snap.empty and float(
                    pd.to_numeric(snap["oi"], errors="coerce")
                    .fillna(0).sum()) <= 0:
                # v4.9.0: Yahoo intermittently returns chains with
                # openInterest zeroed while volume populates (first
                # seen 06-Aug-26). A zero-OI snapshot is a degraded
                # feed, not data — never overwrite a good record
                # with one. Volume-only rows ride oi_footprints'
                # next healthy diff instead.
                msgs.append("OI: source zeroed openInterest — kept "
                            f"record of {snap_date or 'n/a'}")
                snap = None
            if snap is not None and not snap.empty:
                fps = pd.DataFrame()
                # v4.9.2: never diff against a degraded (zero-OI)
                # prior record — oi_prev=0 would mint the entire OI
                # as a fake overnight footprint.
                if not latest.empty and not latest_deg:
                    fps = _inst.footprints(latest, snap)
                sha = _pub._get_sha("history/oi_latest.csv")
                ok, _ = _pub._put("history/oi_latest.csv",
                                  snap.to_csv(index=False),
                                  f"app accrual: OI {today}", sha)
                if ok and fps is not None and not fps.empty:
                    old = _get_csv("history/oi_footprints.csv")
                    allf = pd.concat([old, fps], ignore_index=True)
                    sha2 = _pub._get_sha("history/oi_footprints.csv")
                    _pub._put("history/oi_footprints.csv",
                              allf.to_csv(index=False),
                              f"app accrual: footprints {today}", sha2)
                    _inst.load_footprints.clear()
                msgs.append(f"OI {today}: "
                            + (f"stored ({len(fps)} footprints)"
                               if ok and fps is not None
                               else "stored" if ok else "commit failed"))
            else:
                try:
                    import yfinance as _yf
                    probe = (f"probe exps="
                             f"{len(_yf.Ticker('SPY').options)}")
                except Exception as _e:
                    probe = f"probe {type(_e).__name__}: {_e}"[:100]
                msgs.append(f"OI: no chain data ({probe})")
    except Exception as e:
        msgs.append(f"OI: skipped ({type(e).__name__})")
    return " · ".join(msgs)
