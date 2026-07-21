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
| Notebook | `NOTE` | Evidence → Interpretation → Risks → Falsification → Decision, JSON export/restore |
| Wire | `TOP` | Dual RSS tape: primary (Fed/BLS/BEA) vs narrative (media, labeled Tier 5) |
| Rates & Credit | `GC` | Full Treasury curve (today/-1m/-1y), 2s10s & 3m10y, real/breakeven split, ICE BofA HY & IG OAS |
| Futures | `CTM` | Commodity board by complex (energy/metals/grains/softs/livestock) + real term-structure curves |
| Global | `WEI` | World index board (Americas/EMEA/APAC) + G8 FX cross matrix + DXY readout |
| Fed Diff | `DIFF` | The FOMC statement redlined against the prior one — added/removed words, churn readout |
| Time Machine | `TM` | The desk as of any past date: ALFRED macro vintages + price history cut at the date + "what happened next" |
| Desk Analyst | `ASK` | Claude wired to the live desk: morning reads, positioning views in desk grammar, Notebook drafts, teaching (needs ANTHROPIC_API_KEY; set DESK_CHAT_PASSCODE on public deployments) |
| Calendar | `ECO` | Verified CPI/NFP/FOMC anchors + live full economic calendar (TradingView events widget) |
| Regime History | `HIST` | The four dials recorded nightly by a bot — colored strips over SPX, current streaks, and (once >30 rows) what SPX did after each red flip |
| Quote | any ticker | Security/series lookup — `GOOG`, `GOOG FA`, `GOOG DES`, `CPI`, `EFFR`, `FRED DGS30` |

Every page has a **command line** at the top — type a function, hit GO.
It is security-aware, like the machine: any ticker (`GOOG`, `^VIX`,
`GC=F`, `BTC-USD`) opens the Quote page; `GOOG FA` / `GOOG DES` open
financials or the profile; macro aliases (`CPI`, `NFP`, `EFFR`, `SOFR`,
`10Y`, `CURVE`) chart the FRED series; `FRED <ID>` charts anything.
`HELP <GO>` lists all functions with their real Bloomberg equivalents.
The point is transferable muscle memory: navigate by mnemonic, not mouse.

Current version: **v3.7.0** (shown in the sidebar). Flaky endpoints
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

## Run locally

    pip install -r requirements.txt
    export FRED_API_KEY=your_key   # optional
    streamlit run app.py

## Nightly signal snapshot (the track record)

A GitHub Action (`.github/workflows/snapshot.yml`) runs
`scripts/snapshot.py` weekdays at 22:30 UTC — after the US close — and
appends one row (dial scores + SPX, VIX, VIX/VIX3M, RSP/SPY, HYG/LQD,
2s10s, HY OAS, net liquidity, DXY) to `history/signals.csv`. The row is
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
  evidence anyone can audit.

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

## Known limitations

- Notebook entries persist to a local JSON file; on Community Cloud it
  resets on redeploy — use the download/restore buttons.
- Breadth internals (S5TH, ADD) exist in no free API; RSP/SPY is the
  in-app proxy and TradingView remains the home for full internals.
