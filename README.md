# Capital Markets Desk (Streamlit)

Free, self-hosted companion to the book: a terminal-styled training desk.
Every signal is computed from free primary sources; TradingView embeds are
display glass only. Colors mean **direction, not advice**.

**Live:** https://capitalmarketsmacro.streamlit.app/

## Pages

| Page | Command | What it is |
|---|---|---|
| Launchpad | `BLP` | Everything tiled at once — dials, tripwire, breadth, credit, liquidity, wire; no prose |
| Summary | `HOME` | Four scored signal cards with sparklines, CPI / NFP / FOMC countdown strip, cross-asset table |
| Daily Circuit | `CIR` | The book's 90-second read as a guided sequence, ending at the Notebook |
| Macro | `MAC` | 15 FRED series + Net Liquidity (WALCL − TGA − RRP), NBER recession bands |
| Market | `MKT` | SPX candles + MA ribbon, RSP/SPY and HYG/LQD ratios, normalized cross-asset |
| Volatility | `VIX` | VIX/VIX3M tripwire (1.0 line), VVIX / MOVE / SKEW, live SPY IV skew curve |
| Notebook | `NOTE` | Blotter for quick timestamped jots (private, promotable to entries) + Evidence → Interpretation → Risks → Falsification → Decision; private scratchpad by default, per-entry **publish to the record** (a dated git commit on the `data` branch), post-mortems mirrored to the published file |
| Wire | `TOP` | Dual RSS tape: primary (Fed/BLS/BEA) vs narrative (media, Tier 5); broadsheet columns on wide screens, single column on mobile, today's stories flagged NEW with older rows dimmed |
| Rates & Credit | `GC` | Full Treasury curve (today/-1m/-1y), 2s10s & 3m10y, real/breakeven split, ICE BofA HY & IG OAS; institutional demand: auction RESULTS (bid-to-cover, indirect/dealer shares) + NY Fed primary dealer net positions, all T1 keyless |
| Futures | `CTM` | Commodity board by complex (energy/metals/grains/softs/livestock) + real term-structure curves |
| Global | `WEI` | World index board (Americas/EMEA/APAC) + G8 FX cross matrix + DXY readout |
| Fed Diff | `DIFF` | The FOMC statement redlined against the prior one — added/removed words, churn readout |
| Time Machine | `TM` | The desk as of any past date: ALFRED macro vintages + price history cut at the date + "what happened next" |
| Desk Analyst | `ASK` | Claude wired to the live desk: morning reads, positioning views in desk grammar, Notebook drafts, teaching (needs ANTHROPIC_API_KEY; set DESK_CHAT_PASSCODE on public deployments) |
| Calendar | `ECO` | Verified CPI/NFP/FOMC anchors + live full economic calendar (TradingView events widget) |
| Idea Desk | `GEN` | Chapter 15 live: the eight generators (divergence, crowding via COT percentiles, catalyst, constraint map, regime tripwires, flow, relative value, narrative gap; automated where computable, honestly MANUAL where not), the five-gate funnel, a one-click scan log to the Notebook, and a passcode-gated Claude generator that runs the funnel |
| Flow Desk | `FLOW` | The Sector Flow Tracker's automatable half: live rotation monitor (23-ETF set), FINRA daily short-volume ratios (keyless, Tier 1, off-exchange), and the desk's own ETF flow record — Δshares × price accrued nightly to the data branch, with streak detection and the rotation-signature read; BlockLog and ATS paste stay in the workbook by honest necessity; plus overnight options OI footprints (SPY/QQQ) — strikes where open interest jumped, accrued nightly, side-of-trade honestly unknowable |
| Paper Desk | `PAPER` | Simulated capital across every asset class the desk watches (equities/ETFs, futures at real multipliers, FX, crypto — options in 4.1): fills at the desk's mark plus honest slippage, an order ticket that REFUSES orders without generator + five gates + a kill-switch sentence, P&L by generator, JSON export/restore |
| Help | `HELP` | The operating manual: full function table, command-bar priority rules, desk conventions, the daily rhythm, keys table |
| Regime History | `HIST` | The four dials recorded nightly by a bot — colored strips over SPX, current streaks, and (once >30 rows) what SPX did after each red flip |
| Quote | any ticker | Security/series lookup — `GOOG`, `GOOG FA`, `GOOG DES`, `CPI`, `EFFR`, `FRED DGS30`, `CUSHING`, `EIA <ID>` |

Every page has a **command line** at the top — type a function, hit GO.
It is security-aware, like the machine: any ticker (`GOOG`, `^VIX`,
`GC=F`, `BTC-USD`) opens the Quote page; `GOOG FA` / `GOOG DES` open
financials or the profile; macro aliases (`CPI`, `NFP`, `EFFR`, `SOFR`,
`10Y`, `CURVE`) chart the FRED series; `FRED <ID>` charts anything.
`HELP <GO>` opens the operating manual: full function table, tips, conventions.
The point is transferable muscle memory: navigate by mnemonic, not mouse.

Current version: **v4.0.0** (shown in the sidebar). Flaky endpoints
(Yahoo options chains) serve the last good pull with a timestamp when
throttled, instead of erroring.

## Deploy on Streamlit Community Cloud (free)

1. Put this folder in a GitHub repo (public or private).
2. share.streamlit.io → New app → pick the repo, main file `app.py`.
3. App settings → Secrets → add:

       FRED_API_KEY = "your_key_here"

   (The app also works without a key via FRED's public CSV endpoint,
   but the key is more reliable.)
4. Deploy. First load takes ~1 min while data caches. If a dependency
   changed (e.g. feedparser), reboot the app from the Cloud dashboard.

## v4.0 — the Paper Desk + LIVE mode

**Paper Desk (`PAPER`).** The curriculum's loop closes: learn → scan →
gate → pitch → TEST → post-mortem. A homegrown simulator (no broker
API covers the desk's whole watchlist free — Alpaca has no futures or
FX; IBKR can't run here), which is what makes it teachable: the
ticket enforces the funnel — no order without its generator, all five
gates, and the canonical kill-switch sentence. Fills = desk mark +
slippage always against you (a tick on futures, bps elsewhere);
futures at real multipliers; survivable-size check against cash;
closes prompt the kill-switch reckoning; a P&L-by-generator table
teaches which scans YOU read well. Book = local JSON like the
Notebook (export regularly; wiped on redeploy). Options are 4.1.

**LIVE toggle (the v3.18 intraday mode, folded in).** Next to the
command bar on every page: flips market_history / ohlc /
ticker_snapshot onto a ~60s cache so computed charts track the
streaming TradingView tape during a session. Prices only — FRED,
chains, and records keep their schedules. The tape streams; the
charts poll; nothing the desk teaches has edge inside a minute.

## v3.17 — SKEW lives, fallback ladder, red negatives

The SKEW index finally renders: Yahoo dropped Cboe's proprietary
indices, so the desk now reads them from **Cboe's own CDN** (keyless,
[T1]) — SKEW spark restored, a full SKEW panel on the Volatility page
with a 1-year percentile readout framed against the put/call pattern,
and `SKEW` / `VVIX` as quote commands. The Quote page's dead end
became a ladder: Yahoo → Stooq (computable fallback, [T2]) → the
TradingView symbol widget (display glass, anything TV knows). And a
house rule: **negative numbers read red in every table**
(`theme.neg_red`, chain it onto any new styled table).

## Look & feel (v3.16)

No emojis anywhere — a terminal has function codes, not pictures.
Dingbat marks (✓ ✘ ● →) stay; they're typography. `.streamlit/
config.toml` (new file — paste it too, folder starts with a dot)
aligns Streamlit's own chrome to black/amber/mono, and the theme CSS
dresses the sidebar nav, buttons, tabs, and expanders in IBM Plex
Mono uppercase. The Summary footer now carries a BOT STATUS strip:
last recorded session, counts for flows and footprints, links to the
Actions runs and the data branch — red with STALE if the record is
more than four days old.

## Navigation (v3.14)

The sidebar is organized by intent, not filename: **The Desk**
(Summary, Launchpad, Daily Circuit) → **Markets** (Macro, Market,
Volatility, Rates, Futures & COT, Global & FX, Flow) → **Research**
(Quote, Wire, Calendar, Fed) → **The Analyst** (Notebook, Idea Desk,
Desk Analyst, Regime History) → **Reference** (Time Machine, Help) at
the bottom. `app.py` is now a pure `st.navigation` router; the old
Summary content lives at `pages/0_Summary.py`, and every command-bar
route and page link still points at unchanged file paths.

## Run locally

    pip install -r requirements.txt
    export FRED_API_KEY=your_key   # optional
    streamlit run app.py

## Nightly signal snapshot (the track record)

A GitHub Action (`.github/workflows/snapshot.yml`) runs
`scripts/snapshot.py` weekdays at 22:30 UTC — after the US close — and
appends one row (dial scores + SPX, VIX, VIX/VIX3M, RSP/SPY, HYG/LQD,
2s10s, HY OAS, net liquidity, DXY) to `history/signals.csv`, and logs
shares outstanding × close for the 23-ETF flow set to
`history/flows.csv` (flow = Δshares × price computes in-app; the Flow
page reads it). The row is
committed to the **`data` branch, never main** — Streamlit Cloud
redeploys on every push to main, and a redeploy wipes the Notebook's
JSON storage. The `data` branch holds only the CSV, append-only; the
Regime History page (`HIST`) reads it over raw.githubusercontent,
cached an hour.

One-time setup:

1. Repo → Settings → Secrets and variables → **Actions** → New
   repository secret: `FRED_API_KEY` (same key as the app's).
2. Set the `OWNER` constant at the top of `desk/history.py` to your
   GitHub username (or add a `HISTORY_CSV_URL` app secret pointing at
   the raw CSV — the secret wins if both are set).
3. Actions tab → *Nightly signal snapshot* → **Run workflow** once.
   This first run creates the `data` branch and writes row one. (If
   Actions are disabled for the repo, enable them on that tab first.)
4. Nothing else. The cron takes over on the next weekday close. Market
   holidays skip themselves (the script refuses to stamp a stale SPX
   bar with a fresh date; `SNAPSHOT_FORCE=1` overrides).

Headless note: the desk modules import Streamlit, so the script's log
shows "No runtime found" cache warnings. Harmless — the fetchers run
uncached and the row computes identically.

## EIA energy data (Cushing, crude, gasoline, nat gas)

The quote panel charts the EIA's official weekly energy series: type
`CUSHING`, `CRUDE`, `GASOLINE`, `DISTILLATE`, `REFINERY`, `CRUDEPROD`,
`WTISPOT`, or `NATGAS` — or `EIA <SERIES_ID>` for anything (v1-style
IDs, e.g. `EIA PET.WCESTUS1.W`; browse at eia.gov/opendata). Setup:
register free at https://www.eia.gov/opendata/ (the key arrives by
email), then add to the **Streamlit app secrets**:

    EIA_API_KEY = "your_key"

Honesty note baked into the page: the Tuesday-evening API (American
Petroleum Institute) inventory number is a PAID private survey with no
free feed — it reaches this desk only as a Tier 5 Wire headline. The
EIA's Wednesday 10:30 ET print is the official number the API preview
front-runs; the desk charts the number of record. If it's official,
this desk can verify it free; if it's private, it's a headline — that
boundary is the lesson.

## Institutional flow (all keyless — no new API keys)

Where big players can't hide, per Ch. 15's observable-over-inferred
rule, three chokepoints are now on the desk, none needing a key:

1. **Options OI footprints** — the bot stores SPY/QQQ chains nightly
   (near expiries, ±10% of spot) as `history/oi_latest.csv` (working
   snapshot, overwritten) and appends qualifying overnight OI jumps
   (≥5,000 contracts and ≥50% of prior OI, or fresh strikes) to
   `history/oi_footprints.csv` (append-only record). OI says size
   ARRIVED at a strike; which side initiated is not observable — the
   Flow page repeats this every time. Footprints start on run two.
2. **Treasury auction results** — TreasuryDirect's public API; the
   Rates page shows bid-to-cover and bidder-class shares. Indirects ≈
   foreign/real money; a HIGH primary-dealer share means the forced
   bid absorbed what real demand didn't want.
3. **Primary dealer positions** — the NY Fed Markets Data API, weekly
   net positions ($mm), charted on the Rates page. The most
   institutional public dataset in existence.

**FINRA ATS dark-venue data (live as of v3.15).** Weekly per-security
ATS volumes on the Flow page, with shares-per-trade concentration
flags. Setup: register free at developer.finra.org → API console →
create an API credential, then add BOTH values to the **Streamlit app
secrets**:

    FINRA_API_CLIENT_ID = "..."
    FINRA_API_SECRET = "..."

The app exchanges them for a token automatically. Data is delayed 2
weeks for Tier 1 NMS securities BY RULE — fine for the accumulation
timescale the scan targets. Without credentials the panel shows a
setup note and the rest of the Flow page is unaffected. Keys table on
the Help page updated accordingly.

## Alerts (nightly tripwires → GitHub issues)

After writing its row, the snapshot bot evaluates crossing rules in
`desk/alerts.py` against the history CSV: VIX/VIX3M crossing 1.0
(either direction), any dial color flip, 2s10s sign change, HY OAS
jumping ≥0.30 in a session or through 5.00, a ≥$100bn one-session net
liquidity drop, RSP/SPY −3% over a recorded month; plus flow rules — a ≥$1bn one-sided ETF flow streak of ≥4 sessions, and the equity-out/fixed-income-in rotation signature; and ≥20k-contract overnight OI jumps in SPY/QQQ options. Trips open a GitHub
ISSUE labeled `desk-alert` — GitHub emails you (watch your own repo /
default notification settings), the alert is itself a timestamped
artifact, and closing the issue = acknowledged. No new keys: the
workflow's own token creates issues. Alerts fire on CROSSINGS, not
levels — an alert channel that cries weekly gets muted by Friday; tune
thresholds in `desk/alerts.py`.

## Publishing Notebook entries (the public record)

The Notebook mirrors a real desk: the scratchpad is private, and
publishing is a deliberate, per-entry act. A published entry is
committed at save time to the `data` branch as
`notebook/YYYY-MM-DD_slug.md` — a dated git commit, made before the
outcome. Post-mortem grades are mirrored to the same file; once a call
is on the tape, its reckoning belongs there too. **Privacy:** on a
public repo, published entries are public the moment they land — the
scratchpad default exists so only what you'd stake your name on goes
out.

One-time setup (needs the snapshot's `data` branch to exist first):

1. GitHub → your avatar → **Settings** → **Developer settings** (bottom
   of the left sidebar) → **Personal access tokens** → **Fine-grained
   tokens** → **Generate new token**.
2. Name it (e.g. `desk-notebook-publish`), pick an expiration (max one
   year — calendar a renewal), Resource owner: your account.
3. **Repository access** → *Only select repositories* →
   `CapitalMarketsMacro`. This is the part that matters: the token can
   touch nothing else.
4. **Permissions** → Repository permissions → **Contents** → *Read and
   write*. Leave everything else on No access. Generate, and copy the
   token — it's shown once.
5. Streamlit Cloud → your app → **Settings** → **Secrets** → add a line:

       GH_TOKEN = "github_pat_…"

   (App secrets, NOT GitHub Actions secrets — this one belongs to the
   running app.) Save; the app restarts and the publish checkbox goes
   live.

When the token expires, publishing silently disables (the checkbox
grays out) and the scratchpad keeps working — generate a fresh token
and update the secret.

## Maintenance calendar

`desk/events.py` hardcodes published release schedules on purpose — no
API, nothing to rate-limit. The trade: refresh the lists when agencies
publish new calendars (the Summary strip shows a nudge when a list runs
dry). Roughly once a year:

- **CPI + NFP** — BLS posts next-year schedules in the second half of the
  year: `bls.gov/schedule/news_release/cpi.htm` and `…/empsit.htm`
- **FOMC** — `federalreserve.gov/monetarypolicy/fomccalendars.htm`
  (dates beyond the current year are tentative until confirmed)

## Data sources (all free)

- **FRED** — all macro series, the full Treasury constant-maturity
  curve, TIPS real yields, ICE BofA credit OAS, USREC (1h cache)
- **Yahoo Finance / yfinance** — market history, OHLC, SPY options chain
  (15 min cache; delayed and occasionally rate-limited, charts recover
  on refresh — the skew curve legitimately fails sometimes)
- **Google News RSS** — query-based aggregator lanes for the news
  ticker (keyless; also the CPI/NFP fast path where BLS is blocked)
- **CFTC** — Commitments of Traders positioning (official weekly
  filings, public API); **TreasuryDirect** — auction calendar
- **FINRA Reg SHO daily files** — per-symbol off-exchange short
  volume, keyless CDN, same-day (the Flow page's Tier 1 layer)
- **RSS** — Fed / BLS / BEA press feeds (primary tape), CNBC /
  MarketWatch (narrative tape); fetched concurrently with short
  timeouts so one dead feed can never hang a page. Known limitation:
  BLS blocks some cloud hosts (HTTP 403 from Streamlit Cloud); its
  lane works when the desk runs locally
- **TradingView embeds** — ticker tape and optional widgets; display
  glass only, never inputs to computed signals
- **GitHub Actions + the `data` branch** — the nightly snapshot bot;
  the History page's only input is the CSV it commits (raw URL, 1h
  cache, fail-soft before the first run)

## House conventions

- Every chart carries a `theme.note()` reading note — the dashboard
  teaches you how to read it.
- Data claims follow the book's reliability tiers; the Wire's two-tape
  split is that appendix made visible.
- Signal heuristics label direction (rising/loose vs falling/tight),
  never good/bad, and are not trading signals or investment advice.
- The track record is **live-accrued and tamper-evident**: every
  nightly row is a timestamped git commit on the `data` branch, nothing
  is backfilled. A reconstructed record is a claim; this one is
  evidence anyone can audit. Published Notebook entries hold to the
  same standard — calls committed before outcomes, post-mortems
  appended in view of the same history.

## Gotchas (learned the hard way — don't regress)

- Never blanket-override fonts on `[class*="st-"]` — it breaks
  Streamlit's Material Symbols icon font. `theme.py` explicitly restores
  `[data-testid="stIconMaterial"]`.
- Streamlit Cloud runs current pandas: `Series.last("30D")` is gone —
  use `data.tail_years()`. Weekly FRED series need resample-to-monthly
  before `shift(12)` for YoY — use `data.yoy_pct()`.
- TradingView embed failures on index symbols are usually **licensing,
  not typos** (Cboe VIX, ICE DXY, TVC US10Y won't render in embeds).
  Swap the data source — CAPITALCOM CFDs or `FRED:` symbols — not the
  widget. Fallbacks are commented in `app.py`'s `TAPE_SYMBOLS`.
- Format dataframes with `.style.format` or floats print six decimals.
- `streamlit.components.v1.html` was REMOVED after 2026-06-01 — every
  TradingView widget went blank when Cloud rolled past it. All
  script-bearing embeds now go through `theme.embed()` (st.iframe
  with a components fallback, fail-soft). Never call components.html
  directly again. st.iframe also shows scrollbars where
  components.html clipped — embed() injects a margin/overflow reset
  into the iframe document; don't remove it.
- Inside a `clear_on_submit` form, never prefill a widget via a
  transient `value=` — the reverted value changes the widget's
  auto-ID on the submit rerun and the form returns a blank. Seed a
  stable `key` in session_state before the form renders (see the
  Notebook's promote flow).

## Known limitations

- Notebook entries persist to a local JSON file; on Community Cloud it
  resets on redeploy — use the download/restore buttons.
- Breadth internals (S5TH, ADD) exist in no free API; RSP/SPY is the
  in-app proxy and TradingView remains the home for full internals.
