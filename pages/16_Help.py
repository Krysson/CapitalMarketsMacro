"""Help — the desk's function reference and operating manual.

HELP <GO> used to dump a table inline under the command bar; it
outgrew that. This page is the full reference: every function with its
real-machine equivalent, how the command bar thinks, the desk's
conventions (colors, tiers, notes vs readouts), the daily rhythm, and
the keys that unlock the gated pages.
"""
import pandas as pd
import streamlit as st

from desk import alerts, theme

st.set_page_config(page_title="Help — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · OPERATING MANUAL",
    "Help & Functions",
    "Type the function, hit GO. Same habit as the terminal: navigate "
    "by mnemonic, not by mouse — the point is transferable muscle "
    "memory.")

theme.panel_bar("Functions", "every page, every command")
st.markdown(theme.FUNCTIONS_TABLE)

theme.panel_bar("How the command bar thinks", "priority order")
st.markdown("""
The parser resolves a command in this order — ties go to the earlier
rule, which is why `VIX` opens the Volatility page while `^VIX` charts
the index:

1. **Page mnemonics** (`MKT`, `VOL`, `HIST`, `GEN`…) — one token,
   exact match.
2. **`FRED <ID>` / `EIA <ID>`** — explicit source prefix charts any
   series by ID.
3. **`SEARCH <words>`** — searches FRED's ~800k-series catalog.
4. **Macro aliases** (`CPI`, `NFP`, `SOFR`, `10Y`, `CURVE`…) — chart
   the FRED series.
5. **Energy aliases** (`CUSHING`, `CRUDE`, `GASOLINE`, `NATGAS`,
   `WTISPOT`…) — chart the EIA series (needs `EIA_API_KEY`).
6. **Anything ticker-shaped** goes to the Quote page via Yahoo:
   indexes need a caret (`^VIX`, `^GSPC`), futures a suffix (`GC=F`,
   `CL=F`), crypto a pair (`BTC-USD`). Add `FA` or `DES` for
   financials or the profile (`GOOG FA`).
""")

theme.panel_bar("Reading the desk", "conventions that never change")
st.markdown("""
**Colors are direction, never advice.** Green = rising / loose,
red = falling / tight, yellow = mixed. A red Growth dial is
information, not an instruction.

**Every chart carries two captions.** The gray `note` teaches how to
read the chart — it never changes. The bordered `readout` states what
the chart shows *right now* — it changes with the data. Learn from the
note; act from the readout; log in the Notebook.

**Data reliability tiers ride every claim.** `[T1]` observable
primary-source facts (FRED, EIA, CFTC filings) · `[T2]` market data
and reputable estimates (Yahoo, delayed quotes) · `[E]` your own
estimates · `[I]` your inferences · Tier 5 = narrative. The Wire's
two-tape split is this appendix made visible; the API-vs-EIA crude
prints are the canonical lesson (paid private preview Tuesday, free
official count Wednesday 10:30).

**The record is live-accrued.** The nightly bot commits one row per
session to the `data` branch; published Notebook entries land beside
it. Nothing is backfilled — a reconstructed record is a claim, this
one is evidence. `HIST` shows it; git history audits it.
""")

theme.panel_bar("Charts — navigation (v4.1)", "opens clean, power available")
st.markdown("""
Wheel to zoom · drag a box to zoom both axes · drag to pan ·
double-click to reset · trimmed toolbar has camera-download. Range
buttons re-slice server-side so the scale refits the window. Quote
page extras: **D/W/M bars** (MAs compute on the bars displayed — same
label, different question per interval), **LOG** toggle, and
**expression charts** — `HYG/LQD`, `GC=F/SI=F`, `RB=F*42 - CL=F`.
The rule: `/` and `*` bind anywhere; `+` and `-` need spaces around
them, so `BTC-USD` stays a ticker. Cross-asset rows on Launchpad and
Summary click through to the Quote page.
""")
st.divider()

theme.panel_bar("The daily rhythm", "when to read, when to decide")
st.markdown("""
**7:45–8:15 ET — the read.** `CIR` runs the circuit; write priors and
falsification levels *before* the 8:30 prints exist, so the number
tests the prior instead of writing it. Friday is the liquidity
morning (WALCL posts Thursday 4:30).

**8:30 — the prints test you.** CPI / NFP / claims. You already wrote
what would change your mind.

**10:00–10:30 — position.** The open's first half hour is the least
informative price of the day; by 10:00 the range exists, breadth
means something, and the vol complex is readable. Decisions and the
Notebook's Decision line belong here — publish the entry if it's a
call you'd stake your name on.

**~15 extra minutes — the Ch. 15 drill.** `GEN` runs the eight
generators; the scan log ships to the Notebook in one click. "Nothing
clears the bar today" is a professional answer — *especially* then.

**Close — the bot takes over.** The snapshot commits the row; alert
crossings open a `desk-alert` issue and GitHub emails you. Evening is
for post-mortems, graded against the record, mirrored to published
entries.
""")

theme.panel_bar("Alerts — the active tripwires",
                "evaluated nightly by the bot · delivered as GitHub issues")
st.dataframe(pd.DataFrame(alerts.rules_table()), hide_index=True,
             use_container_width=True)
st.markdown("""
Alerts fire on **crossings and changes, never levels** — a level you
already know about is a condition; a crossing is news. When any rule
trips, the nightly run opens a GitHub issue labeled `desk-alert` and
GitHub emails you; closing the issue is your "acknowledged."

**To tune a threshold:** every number above lives in ONE dictionary —
`THRESHOLDS` at the top of `desk/alerts.py`. Edit the value, commit to
main, and the next nightly run uses it (this table updates itself,
because it renders from the same dictionary). Resist loosening rules
until they cry weekly — an alert channel you've muted is worse than
none.
""")

theme.panel_bar("Keys & gated pages", "what unlocks what")
st.markdown("""
| Secret | Where it lives | What it unlocks |
|---|---|---|
| `FRED_API_KEY` | App secrets **and** GitHub Actions secrets | Reliable FRED + ALFRED vintages; the nightly snapshot |
| `EIA_API_KEY` | App secrets | Energy series (`CUSHING`, `CRUDE`, `EIA <ID>`) — no keyless fallback |
| `ANTHROPIC_API_KEY` | App secrets | Desk Analyst (`ASK`) and the Idea Desk generator (`GEN`) |
| `DESK_CHAT_PASSCODE` | App secrets | Gates `ASK` and `GEN` so strangers can't spend your credits |
| `GH_TOKEN` | App secrets | Publishing Notebook entries to the public record |
| `FINRA_API_CLIENT_ID` + `FINRA_API_SECRET` | App secrets | ATS dark-venue weekly data on the Flow page |

Setup steps for each are in the README. Everything else on the desk —
every chart, dial, tape, and the whole quote panel minus EIA — runs
free and keyless.
""")

theme.note("This page is the manual; the README is the runbook "
           "(deploy, workflows, gotchas). When something on the desk "
           "surprises you, the order to check: the chart's note, this "
           "page, the README's gotchas — in that order, because that's "
           "fastest.")