"""Regime History — the desk's live-accrued track record."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from desk import history, theme

st.set_page_config(page_title="History — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · TRACK RECORD", "Regime History",
    "The four dials, recorded nightly by a bot and committed to git — "
    "live-accrued, append-only, nothing backfilled. Colors show "
    "direction, not good vs. bad.")

df = history.load()

# ---------------------------------------------------------- empty state ----
if df.empty:
    theme.readout(
        theme.YELLOW,
        "NO HISTORY YET — the record starts accruing from the snapshot "
        "workflow's first run.")
    st.markdown(
        "This page will fill in one row per US trading day, written by a "
        "GitHub Action after the close and committed to the repo's `data` "
        "branch. Nothing is backfilled — **that's the point**. You could "
        "reconstruct most of these values retroactively from FRED, but a "
        "reconstructed record is a claim; a live-accrued one, where every "
        "row is a timestamped git commit anyone can audit, is evidence. "
        "The record only exists from the day it starts — which is why it "
        "starts now, thin, rather than later, impressive.\n\n"
        "**To start it:** add `FRED_API_KEY` to the repo's Actions "
        "secrets, set the `OWNER` constant in `desk/history.py`, and run "
        "the *Nightly signal snapshot* workflow once from the Actions "
        "tab (full steps in the README). Rows appear here within an hour "
        "of each commit.")
    st.stop()

CAT_COLOR = {0: theme.RED, 1: theme.YELLOW, 2: theme.GREEN}
CAT_NAME = {0: "red", 1: "yellow", 2: "green"}
DIAL_TITLES = {"growth": "Growth", "inflation": "Inflation",
               "policy": "Policy", "liquidity": "Liquidity"}

n_rows = len(df)
first, last = df.index.min(), df.index.max()

# ------------------------------------------------- strips over the SPX ----
fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    vertical_spacing=0.04, row_heights=[0.34, 0.66])

z, custom, ylabels = [], [], []
for d in reversed(history.DIALS):            # Growth on top of the block
    cats = df[f"{d}_score"].map(history.category)
    z.append([c if c is not None else None for c in cats])
    custom.append([
        (f"{DIAL_TITLES[d]} {int(s)}/4 — {l}" if pd.notna(s)
         else f"{DIAL_TITLES[d]} — incomplete")
        for s, l in zip(df[f"{d}_score"], df[f"{d}_label"])])
    ylabels.append(DIAL_TITLES[d].upper())

fig.add_trace(go.Heatmap(
    x=df.index, y=ylabels, z=z, customdata=custom,
    zmin=0, zmax=2, showscale=False, xgap=0.5, ygap=2,
    colorscale=[[0.0, theme.RED], [0.33, theme.RED],
                [0.34, theme.YELLOW], [0.66, theme.YELLOW],
                [0.67, theme.GREEN], [1.0, theme.GREEN]],
    hovertemplate="%{x|%d-%b-%y} · %{customdata}<extra></extra>"),
    row=1, col=1)

spx = df["spx"].dropna()
if not spx.empty:
    fig.add_trace(go.Scatter(
        x=spx.index, y=spx.values, mode="lines", name="S&P 500",
        line=dict(width=1.6, color=theme.TEXT),
        hovertemplate="%{x|%d-%b-%y} · SPX %{y:,.0f}<extra></extra>"),
        row=2, col=1)

theme.style_fig(
    fig, "THE FOUR DIALS OVER THE TAPE",
    height=440, unified_hover=False,
    right_text=f"{n_rows} sessions · since {first:%d-%b-%y}")
fig.update_layout(showlegend=False)
fig.update_yaxes(showgrid=False, row=1, col=1)
theme.plot(fig, use_container_width=True)
theme.note(
    "Each strip is one dial, one cell per recorded session: green = "
    "score 3–4 (rising / loose), yellow = 2 (mixed), red = 0–1 "
    "(falling / tight). The SPX line below comes from the SAME rows — "
    "so you're reading how regimes and the tape moved together, on the "
    "record, not from memory. Gaps are holidays or missed runs.")

# ---------------------------------------------------------- streaks ----
stk = history.streaks(df)
if stk:
    parts = [f"{DIAL_TITLES[d].upper()} {CAT_NAME[c]} "
             f"{n} session{'s' if n != 1 else ''}"
             for d, (c, n) in stk.items()]
    theme.readout(theme.AMBER,
                  "CURRENT STREAKS — " + " · ".join(parts) +
                  f". Last recorded {last:%a %d-%b-%Y}.")
    theme.note(
        "A streak is how long each dial has held its current color. Long "
        "streaks are the regime; fresh flips are the news — and a fresh "
        "flip is exactly when a Notebook entry should exist.")

st.divider()

# ------------------------------------------------------ track record ----
theme.panel_bar("Track record — what happened after red flips",
                f"{n_rows} rows")
if n_rows <= 30:
    theme.readout(
        theme.YELLOW,
        f"ACCRUING — {n_rows} of the 30 sessions needed before this "
        "block turns on. No shortcuts: the record grades itself only "
        "once it has enough of itself to grade.")
    theme.note(
        "When live, this block counts each dial's flips into red and "
        "measures SPX's forward one-month move after each — computed "
        "from these rows alone, so the record can never quietly borrow "
        "evidence it didn't earn.")
else:
    rows = []
    for d in history.DIALS:
        flips = history.red_flips(df, d)
        graded = flips.dropna(subset=["fwd_1m_pct"]) if not flips.empty \
            else flips
        rows.append({
            "Dial": DIAL_TITLES[d],
            "Flips into red": 0 if flips.empty else len(flips),
            "Graded (1m elapsed)": 0 if graded.empty else len(graded),
            "Avg fwd 1m %": (float(graded["fwd_1m_pct"].mean())
                             if not graded.empty else float("nan")),
            "% positive": (float((graded["fwd_1m_pct"] > 0).mean() * 100)
                           if not graded.empty else float("nan")),
        })
    rec = pd.DataFrame(rows).set_index("Dial")
    st.dataframe(
        theme.neg_red(
            rec.style.format({"Avg fwd 1m %": "{:+.2f}",
                              "% positive": "{:.0f}"}, na_rep="—")),
        use_container_width=True)
    theme.note(
        "A 'flip into red' is a session where a dial's color turned red "
        "after not being red. Forward returns use SPX from these rows, "
        "21 recorded sessions ahead — flips younger than a month sit "
        "ungraded until the record catches up. Small samples for years; "
        "read counts before averages. Direction, not advice.")

st.divider()
st.markdown(
    "**Why this exists.** Every row above was written by a bot on the "
    "evening it describes and committed to the `data` branch — the git "
    "log is the audit trail. Anyone claiming a framework 'would have "
    "caught' something owes you receipts; this page is the desk paying "
    "that debt in advance, one honest row at a time.")
