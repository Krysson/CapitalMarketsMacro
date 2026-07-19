# Capital Markets Desk (Streamlit)

Free, self-hosted version of the Book III dashboards: Summary signals,
Macro (FRED), Market, Volatility, and the Analyst's Notebook.

## Deploy on Streamlit Community Cloud (free)

1. Put this folder in a GitHub repo (public or private).
2. Go to share.streamlit.io -> New app -> pick the repo, main file `app.py`.
3. App settings -> Secrets -> add:

   FRED_API_KEY = "your_key_here"

   (The app also works without a key via FRED's public CSV endpoint,
   but the key is more reliable.)
4. Deploy. First load takes ~1 min while data caches.

## Run locally

    pip install -r requirements.txt
    export FRED_API_KEY=your_key   # optional
    streamlit run app.py

## Notes

- Market data via Yahoo Finance is delayed and occasionally rate-limited;
  charts recover on refresh. FRED data caches for 1 hour, market for 15 min.
- Notebook entries persist to a local JSON file. On Community Cloud that
  file resets on redeploy - use the download/restore buttons on the page.
- Breadth internals (S5TH, ADD) are not in any free API; RSP/SPY is the
  in-app proxy and TradingView remains the home for full internals.
- https://capitalmarketsmacro.streamlit.app/
