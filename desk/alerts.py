"""Desk alerts — Ch. 15's tripwires, evaluated by the nightly bot.

Pure functions over the signal history CSV: the nightly snapshot job
runs evaluate() after writing its row, and if anything tripped it opens
a GitHub ISSUE on the repo. That's the delivery mechanism, chosen
deliberately: GitHub emails you on new issues (free, no new keys, no
SMTP), the alert is itself a timestamped artifact on the record, and
closing the issue is a natural "acknowledged" workflow.

Alerts fire on CHANGES and crossings, not levels — a level you already
know about is a condition; a crossing is news. Tune thresholds here;
the rules are deliberately few, because an alert channel that cries
weekly gets muted by Friday.
"""
from __future__ import annotations

import pandas as pd


def _cat(score) -> int | None:
    if pd.isna(score):
        return None
    s = int(score)
    return 2 if s >= 3 else (0 if s <= 1 else 1)


def _num(row, col):
    v = row.get(col)
    return None if v is None or pd.isna(v) else float(v)


def evaluate(df: pd.DataFrame) -> list[str]:
    """df = the full signals.csv as numerics, oldest first. Returns
    human-readable alert lines for TODAY's row; [] if nothing tripped
    or fewer than 2 rows exist (crossings need a yesterday)."""
    if df is None or len(df) < 2:
        return []
    today, prior = df.iloc[-1], df.iloc[-2]
    alerts: list[str] = []

    # 1) Vol regime: the book's tripwire — VIX/VIX3M crossing 1.0.
    r_now, r_prev = _num(today, "vix_vix3m"), _num(prior, "vix_vix3m")
    if r_now is not None and r_prev is not None:
        if r_now >= 1.0 and r_prev < 1.0:
            alerts.append(
                f"VOL REGIME: VIX/VIX3M crossed ABOVE 1.0 "
                f"({r_prev:.3f} → {r_now:.3f}) — backwardation, "
                f"front-end vol bid. The desk's primary stress tripwire.")
        elif r_now < 1.0 and r_prev >= 1.0:
            alerts.append(
                f"VOL REGIME: VIX/VIX3M back BELOW 1.0 "
                f"({r_prev:.3f} → {r_now:.3f}) — stress regime ending "
                f"is also a regime change.")

    # 2) Dial flips — any color change, red flips loudest.
    for d in ("growth", "inflation", "policy", "liquidity"):
        c_now = _cat(today.get(f"{d}_score"))
        c_prev = _cat(prior.get(f"{d}_score"))
        if None in (c_now, c_prev) or c_now == c_prev:
            continue
        name = {0: "RED", 1: "YELLOW", 2: "GREEN"}
        loud = " ← flip INTO red" if c_now == 0 else ""
        alerts.append(
            f"DIAL FLIP: {d.upper()} {name[c_prev]} → {name[c_now]} "
            f"({today.get(f'{d}_label')}){loud}. A fresh flip is when "
            f"a Notebook entry should exist.")

    # 3) Curve: 2s10s sign change.
    c_now, c_prev = _num(today, "t10y2y"), _num(prior, "t10y2y")
    if c_now is not None and c_prev is not None and \
            (c_now > 0) != (c_prev > 0):
        alerts.append(
            f"CURVE: 2s10s crossed zero ({c_prev:+.2f} → {c_now:+.2f}pp) "
            f"— inversion events are rates-regime news either direction.")

    # 4) Credit: HY OAS jump (w/w vs last recorded session) or stress level.
    h_now, h_prev = _num(today, "hy_oas"), _num(prior, "hy_oas")
    if h_now is not None and h_prev is not None:
        if h_now - h_prev >= 0.30:
            alerts.append(
                f"CREDIT: HY OAS widened {h_now - h_prev:+.2f} in a "
                f"session ({h_prev:.2f} → {h_now:.2f}) — spread "
                f"velocity, not level, is the tell.")
        elif h_now >= 5.0 > h_prev:
            alerts.append(
                f"CREDIT: HY OAS through 5.00 ({h_now:.2f}) — the "
                f"desk's stress line; credit demanding real "
                f"compensation.")

    # 5) Liquidity: a one-session net-liquidity drop >= $100bn.
    n_now, n_prev = _num(today, "net_liq_tn"), _num(prior, "net_liq_tn")
    if n_now is not None and n_prev is not None and \
            (n_prev - n_now) >= 0.10:
        alerts.append(
            f"LIQUIDITY: net liquidity fell "
            f"${(n_prev - n_now) * 1000:,.0f}bn in a session "
            f"({n_prev:.2f}tn → {n_now:.2f}tn) — check TGA/RRP for "
            f"the mechanical driver before interpreting.")

    # 6) Breadth: RSP/SPY down >=3% over ~1 recorded month.
    if len(df) >= 22:
        b_now = _num(today, "rsp_spy")
        b_m1 = _num(df.iloc[-22], "rsp_spy")
        if b_now is not None and b_m1 is not None and b_m1:
            chg = (b_now / b_m1 - 1) * 100
            if chg <= -3.0:
                alerts.append(
                    f"BREADTH: RSP/SPY {chg:+.1f}% over ~1 month — "
                    f"narrowing leadership; the first warning sign in "
                    f"the book's sequence.")
    return alerts


def issue_payload(alerts: list[str], date: str) -> tuple[str, str]:
    """(title, markdown body) for the GitHub issue. Pure."""
    title = (f"DESK ALERT — {date}: {len(alerts)} tripwire"
             f"{'' if len(alerts) == 1 else 's'}")
    body = (
        f"The nightly snapshot for **{date}** tripped "
        f"{len(alerts)} alert{'' if len(alerts) == 1 else 's'}:\n\n"
        + "\n".join(f"- {a}" for a in alerts)
        + "\n\n---\n*Generated by `scripts/snapshot.py` from "
          "`history/signals.csv` on the `data` branch — the same rows "
          "the Regime History page reads. Alerts fire on crossings, "
          "not levels; tune the rules in `desk/alerts.py`. Close this "
          "issue to acknowledge.*")
    return title, body
