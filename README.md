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
| Macro | `ECO` | 15 FRED series + Net Liquidity (WALCL − TGA − RRP), NBER recession bands |
| Market | `WEI` | SPX candles + MA ribbon, RSP/SPY and HYG/LQD ratios, normalized cross-asset |
| Volatility | `VIX` | VIX/VIX3M tripwire (1.0 line), VVIX / MOVE / SKEW, live SPY IV skew curve |
| Notebook | `NOTE` | Evidence → Interpretation → Risks → Falsification → Decision, JSON export/restore |
| Wire | `TOP` | Dual RSS tape: primary (Fed/BLS/BEA) vs narrative (media, labeled Tier 5) |
| Rates & Credit | `GC` | Full Treasury curve (today/-1m/-1y), 2s10s & 3m10y, real/breakeven split, ICE BofA HY & IG OAS |
| Futures | `CTM` | Commodity board by complex (energy/metals/grains/softs/livestock) + real term-structure curves |
| Quote | any ticker | Security/series lookup — `GOOG`, `GOOG FA`, `GOOG DES`, `CPI`, `EFFR`, `FRED DGS30` |

Every page has a **command line** at the top — type a function, hit GO.
It is security-aware, like the machine: any ticker (`GOOG`, `^VIX`,
`GC=F`, `BTC-USD`) opens the Quote page; `GOOG FA` / `GOOG DES` open
financials or the profile; macro aliases (`CPI`, `NFP`, `EFFR`, `SOFR`,
`10Y`, `CURVE`) chart the FRED series; `FRED <ID>` charts anything.
`HELP <GO>` lists all functions with their real Bloomberg equivalents.
The point is transferable muscle memory: navigate by mnemonic, not mouse.

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
- **RSS** — Fed / BLS / BEA press feeds (primary tape), CNBC /
  MarketWatch (narrative tape); fetched concurrently with short
  timeouts so one dead feed can never hang a page. Known limitation:
  BLS blocks some cloud hosts (HTTP 403 from Streamlit Cloud); its
  lane works when the desk runs locally
- **TradingView embeds** — ticker tape and optional widgets; display
  glass only, never inputs to computed signals

## House conventions

- Every chart carries a `theme.note()` reading note — the dashboard
  teaches you how to read it.
- Data claims follow the book's reliability tiers; the Wire's two-tape
  split is that appendix made visible.
- Signal heuristics label direction (rising/loose vs falling/tight),
  never good/bad, and are not trading signals or investment advice.

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
