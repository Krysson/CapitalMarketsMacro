"""Nightly signal snapshot — one row of the desk's live track record.

Runs headless in GitHub Actions after the US close, computes today's
dial scores and market readings from the SAME desk modules the app
uses (no parallel logic to drift), and appends one row to
history/signals.csv. The workflow then commits that CSV to the `data`
branch — never main, because a push to main redeploys Streamlit Cloud
and a redeploy wipes the Notebook's JSON storage.

The record is append-only and live-accrued: nothing is backfilled,
every row is a timestamped git commit. A reconstructed record is a
claim; this one is evidence.

Note: desk modules import streamlit, so the cache decorators emit
"No runtime found" warnings when run headless. Harmless — verified.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

# Run from anywhere; the repo root is one level up from scripts/.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desk import data, signals  # noqa: E402  (path bootstrap above)

CSV_PATH = ROOT / "history" / "signals.csv"

COLUMNS = [
    "date",
    "growth_score", "growth_label",
    "inflation_score", "inflation_label",
    "policy_score", "policy_label",
    "liquidity_score", "liquidity_label",
    "spx", "vix", "vix_vix3m", "rsp_spy", "hyg_lqd",
    "t10y2y", "hy_oas", "net_liq_tn", "dxy",
]


def _last(s: pd.Series | None, nd: int) -> str:
    """Last value of a series, rounded — '' if unavailable (fail-soft:
    a blank cell is honest; a fabricated number is not)."""
    if s is None:
        return ""
    s = s.dropna()
    return "" if s.empty else f"{float(s.iloc[-1]):.{nd}f}"


def _ratio(hist: pd.DataFrame, num: str, den: str, nd: int = 4) -> str:
    """Last value of num/den on days where BOTH printed."""
    if num not in hist.columns or den not in hist.columns:
        return ""
    pair = hist[[num, den]].dropna()
    if pair.empty:
        return ""
    return f"{float(pair[num].iloc[-1] / pair[den].iloc[-1]):.{nd}f}"


def build_row(today: str, bundle: dict, hist: pd.DataFrame,
              hy_oas: pd.Series, net_liq: pd.Series) -> dict:
    """Pure assembly of one CSV row from already-fetched inputs."""
    row = {"date": today}
    for sig in signals.compute_signals(bundle):
        key = sig.category.lower()
        if sig.loading:  # a check's data was unavailable — say so
            row[f"{key}_score"] = ""
            row[f"{key}_label"] = "Incomplete"
        else:
            row[f"{key}_score"] = sig.score
            row[f"{key}_label"] = sig.label

    get = lambda t: hist[t] if t in hist.columns else None
    row["spx"] = _last(get("^GSPC"), 2)
    row["vix"] = _last(get("^VIX"), 2)
    row["vix_vix3m"] = _ratio(hist, "^VIX", "^VIX3M")
    row["rsp_spy"] = _ratio(hist, "RSP", "SPY")
    row["hyg_lqd"] = _ratio(hist, "HYG", "LQD")
    row["t10y2y"] = _last(bundle.get("T10Y2Y"), 2)
    row["hy_oas"] = _last(hy_oas, 2)
    nl = net_liq.dropna()
    row["net_liq_tn"] = ("" if nl.empty
                         else f"{float(nl.iloc[-1]) / 1e6:.3f}")  # $mm -> $tn
    row["dxy"] = _last(get("DX-Y.NYB"), 2)
    return row


def main() -> int:
    today = pd.Timestamp.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    # Skip if today's row already exists (rerun-safe, manual-dispatch-safe).
    existing = None
    if CSV_PATH.exists():
        existing = pd.read_csv(CSV_PATH, dtype={"date": str})
        if today in set(existing["date"]):
            print(f"row for {today} already recorded — nothing to do")
            return 0

    print("fetching FRED bundle…")
    bundle = data.macro_bundle()
    if all(s.dropna().empty for s in bundle.values()):
        # FRED completely down: better a red run and no row than a junk row.
        print("ERROR: no FRED data at all — refusing to write a row",
              file=sys.stderr)
        return 1

    print("fetching market history…")
    hist = data.market_history(period="6mo")

    # US market holiday guard: on a weekday holiday Yahoo's latest SPX bar
    # is a prior session. Recording it under today's date would stamp
    # stale prices with a fresh timestamp — skip instead. SNAPSHOT_FORCE=1
    # overrides (useful for a first manual run or catch-up).
    if not os.environ.get("SNAPSHOT_FORCE"):
        spx = hist["^GSPC"].dropna() if "^GSPC" in hist.columns else pd.Series(dtype=float)
        if not spx.empty and spx.index[-1].strftime("%Y-%m-%d") != today:
            print(f"latest SPX bar is {spx.index[-1]:%Y-%m-%d}, not {today} "
                  "— market closed today; skipping (set SNAPSHOT_FORCE=1 "
                  "to record anyway)")
            return 0

    hy_oas = data.fred_series("BAMLH0A0HYM2", start="2024-01-01")
    net_liq = data.net_liquidity(bundle)

    row = build_row(today, bundle, hist, hy_oas, net_liq)

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row], columns=COLUMNS)
    if existing is not None:
        frame = pd.concat(
            [existing.reindex(columns=COLUMNS), frame], ignore_index=True)
    frame.to_csv(CSV_PATH, index=False)

    dials = " · ".join(
        f"{k.split('_')[0].upper()} {row[k]}={row[k.replace('score', 'label')]}"
        for k in ("growth_score", "inflation_score",
                  "policy_score", "liquidity_score"))
    print(f"recorded {today}: {dials} | SPX {row['spx'] or 'n/a'} "
          f"VIX {row['vix'] or 'n/a'} NetLiq {row['net_liq_tn'] or 'n/a'}tn")

    # ---- alerts: crossings vs the prior recorded session -> GitHub issue.
    # Fail-soft by design: an alert hiccup must never fail the snapshot.
    try:
        from desk import alerts
        num = frame.copy()
        for c in num.columns:
            if not c.endswith("_label") and c != "date":
                num[c] = pd.to_numeric(num[c], errors="coerce")
        tripped = alerts.evaluate(num)
        if tripped:
            print(f"ALERTS TRIPPED ({len(tripped)}):")
            for a in tripped:
                print(f"  - {a}")
            token = os.environ.get("GITHUB_TOKEN")
            repo = os.environ.get("GITHUB_REPOSITORY")
            if token and repo:
                import requests as _rq
                title, body = alerts.issue_payload(tripped, today)
                resp = _rq.post(
                    f"https://api.github.com/repos/{repo}/issues",
                    json={"title": title, "body": body,
                          "labels": ["desk-alert"]},
                    headers={"Authorization": f"Bearer {token}",
                             "Accept": "application/vnd.github+json"},
                    timeout=20)
                print("alert issue:",
                      resp.json().get("html_url", resp.status_code)
                      if resp.ok else f"failed ({resp.status_code})")
            else:
                print("no GITHUB_TOKEN/GITHUB_REPOSITORY — alerts "
                      "logged only")
        else:
            print("no alerts tripped")
    except Exception as ex:
        print(f"alert evaluation skipped ({type(ex).__name__}) — "
              f"snapshot unaffected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
