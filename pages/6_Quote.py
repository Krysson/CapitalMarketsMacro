"""Quote — security & series lookup. The desk's DES / GP / FA.

Reached from the command bar: a ticker (GOOG, ^VIX, GC=F, BTC-USD), a
macro alias (CPI, NFP, EFFR, SOFR, 10Y, CURVE), or FRED <SERIES_ID>.
Equities via Yahoo (delayed, Tier 2); series via FRED (Tier 1).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, theme

st.set_page_config(page_title="Quote — Desk", page_icon="▪", layout="wide")
theme.header(
    "BOOK III · QUOTE",
    "Security / Series Lookup",
    "Type it in the command bar: GOOG · GOOG FA · GOOG DES · CPI · "
    "EFFR · 10Y · FRED DGS30. Page mnemonics win ties — VIX opens the "
    "Volatility page, ^VIX charts the index.")

def fred_search_ui(prefill: str = "") -> None:
    """FRED catalog search: type words, pick a series, chart it."""
    theme.panel_bar("FRED catalog search",
                    "~800,000 series · popularity-ranked")
    query = st.text_input("Search FRED series", value=prefill,
                          placeholder="e.g. housing starts, M2, "
                                      "delinquency rate, japan cpi")
    if not query.strip():
        return
    results = data.fred_search(query)
    if not results:
        st.markdown(
            '<div class="desk-note">No results — or no FRED_API_KEY in '
            'secrets (the search endpoint needs one; charts work '
            'without). Browse the full catalog at '
            '<a href="https://fred.stlouisfed.org/search?st='
            + query.replace(" ", "+")
            + '" target="_blank" style="color:#FF9F1C">'
            'fred.stlouisfed.org</a>.</div>', unsafe_allow_html=True)
        return
    df = pd.DataFrame(results).rename(columns={
        "id": "ID", "title": "Title", "freq": "Freq",
        "units": "Units", "pop": "Pop"})
    st.dataframe(df, hide_index=True, use_container_width=True,
                 height=min(420, 40 + 35 * len(df)))
    pick = st.selectbox(
        "Chart one", [f'{r["id"]} — {r["title"][:70]}' for r in results])
    if st.button("Chart it \u2192"):
        st.session_state["quote_query"] = ("fred", pick.split(" — ")[0],
                                           "")
        st.session_state.pop("fred_search", None)
        st.rerun()
    theme.note("Popularity is FRED's own usage rank — a decent proxy for "
               "'the series people actually mean'. Check Freq and Units "
               "before trusting a chart: same concept, five variants "
               "(SA vs NSA, level vs %-change) is the classic FRED trap.")


search_q = st.session_state.get("fred_search")
if search_q is not None:
    fred_search_ui(search_q)
    st.stop()

q = st.session_state.get("quote_query")
if not q:
    st.markdown(
        "| Try | You get |\n|---|---|\n"
        "| `GOOG` | price graph + key stats |\n"
        "| `GOOG FA` | same, financials open |\n"
        "| `GOOG DES` | same, profile open |\n"
        "| `CPI` / `NFP` / `EFFR` / `SOFR` / `10Y` / `CURVE` | the FRED "
        "series, charted |\n"
        "| `FRED DGS30` | any FRED series by ID |\n"
        "| `CUSHING` / `CRUDE` / `GASOLINE` / `NATGAS` / `WTISPOT` | "
        "EIA weekly energy series, charted |\n"
        "| `EIA PET.WCESTUS1.W` | any EIA series by ID |\n"
        "| `SEARCH housing starts` | search FRED's catalog |")
    st.divider()
    fred_search_ui()
    st.stop()

kind, sym, func = q

# ---------------------------------------------------------- Cboe mode --
if kind == "cboe":
    s = data.cboe_series(sym)
    if s.empty:
        st.error(f"{sym} — Cboe CDN unreachable; try again shortly.")
        st.stop()
    years = st.selectbox("Lookback (years)", [1, 2, 5, 10, 15], index=1)
    tail = data.tail_years(s, years)
    wow = float(s.iloc[-1]) - float(s.iloc[-2]) if len(s) > 1 else None
    theme.panel_bar(f"Cboe · {sym}",
                    f"{float(s.iloc[-1]):,.2f}  ({s.index[-1]:%d-%b-%Y})")
    fig = go.Figure(go.Scatter(x=tail.index, y=tail.values, mode="lines",
                               line=dict(width=1.8, color=theme.AMBER)))
    theme.plot(theme.style_fig(
        fig, None, height=380,
        right_text=(f"d/d {wow:+.2f}" if wow is not None else None),
        right_color=(theme.RED if wow is not None and wow > 0
                     else theme.GREEN)),
        use_container_width=True)
    theme.note("Straight from Cboe's own daily-history CDN — the index "
               "owner's file, which is why this works where Yahoo's "
               "^-symbols went dark. [T1] For SKEW: Cboe has announced "
               "a coming methodology revision (2025 consultation) — "
               "when it takes effect, new prints won't be comparable "
               "to this history; the desk will say so.")
    st.stop()

# ----------------------------------------------------------- EIA mode --
if kind == "eia":
    # Resolve a friendly name if the ID matches a known alias.
    nice = next((n for _, (sid, n) in data.EIA_ALIASES.items()
                 if sid == sym), None)
    s = data.eia_series(sym)
    if s.empty:
        if not data._eia_key():
            st.error("EIA series need an EIA_API_KEY in app secrets — "
                     "free from eia.gov/opendata (setup steps in the "
                     "README). Unlike FRED, the EIA API has no keyless "
                     "fallback.")
        else:
            st.error(f"{sym} — no data from the EIA API. Check the "
                     f"series ID at eia.gov/opendata (v1-style IDs, "
                     f"e.g. PET.WCESTUS1.W).")
        st.stop()
    years = st.selectbox("Lookback (years)", [1, 2, 5, 10, 20], index=2)
    tail = data.tail_years(s, years)
    theme.panel_bar(nice or f"EIA · {sym}",
                    f"{float(s.iloc[-1]):,.1f}  ({s.index[-1]:%d-%b-%Y})")
    st.markdown(
        f'<div class="desk-note">EIA:{sym} · Weekly Petroleum Status '
        f'Report family (Wed 10:30 ET) · '
        f'<a href="https://www.eia.gov/opendata/" target="_blank" '
        f'style="color:{theme.AMBER}">eia.gov/opendata</a></div>',
        unsafe_allow_html=True)
    wow = (float(s.iloc[-1]) - float(s.iloc[-2])) if len(s) > 1 else None
    fig = go.Figure(go.Scatter(x=tail.index, y=tail.values, mode="lines",
                               line=dict(width=1.8, color=theme.AMBER)))
    theme.recession_bands(fig, data.usrec(), start=tail.index.min(),
                          end=tail.index.max())
    theme.plot(theme.style_fig(
        fig, None, height=380,
        right_text=(f"w/w {wow:+,.0f}" if wow is not None else None),
        right_color=(theme.GREEN if wow is not None and wow >= 0
                     else theme.RED)),
        use_container_width=True)
    pts = data.series_hist_points(s)
    if pts:
        cols = st.columns(len(pts))
        for c, (label, txt) in zip(cols, pts):
            with c:
                st.markdown(
                    f'<div style="background:{theme.PANEL};'
                    f'padding:6px 10px;border-radius:2px;'
                    f'font-family:\'IBM Plex Mono\',monospace">'
                    f'<span class="desk-eyebrow" '
                    f'style="color:{theme.MUTED}">{label}</span><br>'
                    f'<span style="color:{theme.TEXT};'
                    f'font-size:0.9rem">{txt}</span></div>',
                    unsafe_allow_html=True)
    theme.note("Tier 1 — the government's official count, published "
               "Wednesdays 10:30 ET. The API (American Petroleum "
               "Institute) number that hits the Wire Tuesday evening is "
               "a PAID private survey with no free feed — it moves "
               "crude precisely because it previews THIS print. When "
               "they diverge, Wednesday resolves it. The desk charts "
               "the number of record and lets the Wire carry the "
               "preview, tiered honestly.")
    st.stop()

# ---------------------------------------------------------- FRED mode --
if kind == "fred":
    s = data.fred_series(sym, start="1990-01-01")
    if s.empty:
        st.error(f"{sym} — no data on FRED. Check the series ID at "
                 f"fred.stlouisfed.org.")
        st.stop()
    years = st.selectbox("Lookback (years)", [1, 2, 5, 10, 20, 35],
                         index=2)
    tail = data.tail_years(s, years)
    meta = data.fred_meta(sym)
    title = meta.get("title") or f"FRED \u00b7 {sym}"
    theme.panel_bar(title, f"{float(s.iloc[-1]):,.2f}  "
                    f"({s.index[-1]:%d-%b-%Y})")
    meta_bits = [f"FRED:{sym}"] + [meta[k] for k in
                 ("freq", "units", "sa") if meta.get(k)]
    if meta.get("updated"):
        meta_bits.append(f"updated {meta['updated']}")
    st.markdown(
        f'<div class="desk-note">{" \u00b7 ".join(meta_bits)} \u00b7 '
        f'<a href="https://fred.stlouisfed.org/series/{sym}" '
        f'target="_blank" style="color:{theme.AMBER}">view on FRED'
        f'</a></div>', unsafe_allow_html=True)
    fig = go.Figure(go.Scatter(x=tail.index, y=tail.values, mode="lines",
                               line=dict(width=1.8, color=theme.AMBER)))
    theme.recession_bands(fig, data.usrec(), start=tail.index.min(),
                          end=tail.index.max())
    theme.plot(theme.style_fig(fig, None, height=380),
                    use_container_width=True)
    pts = data.series_hist_points(s)
    if pts:
        cols = st.columns(len(pts))
        for c, (label, txt) in zip(cols, pts):
            with c:
                st.markdown(
                    f'<div style="background:{theme.PANEL};'
                    f'padding:6px 10px;border-radius:2px;'
                    f'font-family:\'IBM Plex Mono\',monospace">'
                    f'<span class="desk-eyebrow" '
                    f'style="color:{theme.MUTED}">{label}</span><br>'
                    f'<span style="color:{theme.TEXT};'
                    f'font-size:0.9rem">{txt}</span></div>',
                    unsafe_allow_html=True)
    theme.note("Tier 1 primary-source data via FRED. Gray bands = NBER "
               "recessions. 1Y \u0394 is in the series' native units. "
               "If this series belongs on a panel, the ECO page is its "
               "curated home.")
    st.stop()

# -------------------------------------------------------- ticker mode --
snap = data.ticker_snapshot(sym)
ohlc = data.ohlc(sym, period="1y")
if not snap and ohlc.empty:
    st.error(f"{sym} — nothing on Yahoo Finance. Indexes need a caret "
             f"(^VIX, ^GSPC); futures a suffix (GC=F, CL=F); crypto a "
             f"pair (BTC-USD).")
    # Fallback ladder: Stooq (computable, [T2]) then the TradingView
    # widget (display glass — anything TV knows, shown, never computed).
    alt = data.stooq_series(sym)
    if not alt.empty:
        theme.panel_bar(f"Stooq fallback · {sym}",
                        f"{float(alt.iloc[-1]):,.2f}  "
                        f"({alt.index[-1]:%d-%b-%Y})")
        tail = data.tail_years(alt, 2)
        fig = go.Figure(go.Scatter(x=tail.index, y=tail.values,
                                   mode="lines",
                                   line=dict(width=1.8,
                                             color=theme.AMBER)))
        theme.plot(theme.style_fig(fig, None, height=340),
                   use_container_width=True)
        theme.note("Yahoo doesn't carry this one; Stooq (free CSV) "
                   "does. [T2] Daily closes only — good enough to "
                   "read, not wired into any computed signal.")
    else:
        st.markdown('<div class="desk-note">Trying the TradingView '
                    'glass — display only, never feeds signals. If it '
                    'renders, the symbol exists there under this or a '
                    'prefixed name (e.g. CBOE:SKEW).</div>',
                    unsafe_allow_html=True)
        theme.embed(f"""
        <div class="tradingview-widget-container">
          <div id="tv_fallback"></div>
          <script src="https://s3.tradingview.com/tv.js"></script>
          <script>
          new TradingView.widget({{
            "container_id": "tv_fallback", "symbol": "{sym}",
            "interval": "D", "timezone": "America/New_York",
            "theme": "dark", "style": "1", "locale": "en",
            "allow_symbol_change": true, "width": "100%",
            "height": 460 }});
          </script>
        </div>""", height=470)
    st.stop()

name = snap.get("name", sym)
price = snap.get("price")
prev = snap.get("prev_close")
chg = ((price / prev - 1) * 100) if price and prev else None
chg_txt = (f'<span style="color:'
           f'{theme.GREEN if chg >= 0 else theme.RED}">{chg:+.2f}%'
           f'</span>' if chg is not None else "")
st.markdown(
    f'<div style="display:flex;justify-content:space-between;'
    f'align-items:baseline;font-family:\'IBM Plex Mono\',monospace">'
    f'<span style="font-size:1.15rem;color:{theme.AMBER}">{sym}'
    f'<span style="color:{theme.MUTED};font-size:0.85rem;margin-left:12px">'
    f'{name}</span></span>'
    f'<span style="font-size:1.3rem;color:{theme.TEXT}">'
    f'{price:,.2f} {chg_txt}</span></div>'
    if price else f'<div class="desk-eyebrow">{sym} · {name}</div>',
    unsafe_allow_html=True)

if not ohlc.empty:
    close = ohlc["Close"]
    fig = go.Figure()
    fig.add_trace(theme.candles(ohlc, sym))
    for win, colr in ((50, theme.BLUE), (200, theme.RED)):
        ma = close.rolling(win).mean()
        fig.add_scatter(x=ma.index, y=ma.values, mode="lines",
                        name=f"SMA {win}",
                        line=dict(width=1.1, color=colr))
    fig.update_layout(xaxis_rangeslider_visible=False)
    theme.plot(
        theme.style_fig(fig, f"{sym} — 1Y DAILY", height=400,
                        unified_hover=False),
        use_container_width=True)
else:
    st.warning("Price history unavailable (Yahoo rate limit?) — "
               "stats below may still load.")

stats = [("MKT CAP", snap.get("market_cap"),
          lambda v: f"{v/1e9:,.1f}B"),
         ("P/E", snap.get("pe"), lambda v: f"{v:,.1f}"),
         ("FWD P/E", snap.get("fwd_pe"), lambda v: f"{v:,.1f}"),
         ("DIV YLD", snap.get("div_yield"),
          lambda v: f"{v:.2f}%" if v > 1 else f"{v*100:.2f}%"),
         ("BETA", snap.get("beta"), lambda v: f"{v:,.2f}"),
         ("52W RANGE", (snap.get("year_low"), snap.get("year_high")),
          lambda v: f"{v[0]:,.2f}\u2013{v[1]:,.2f}"
          if v[0] and v[1] else None)]
cells = []
for label, val, f in stats:
    try:
        txt = f(val) if val not in (None, (None, None)) else None
    except Exception:
        txt = None
    if txt:
        cells.append((label, txt))
if cells:
    cols = st.columns(len(cells))
    for c, (label, txt) in zip(cols, cells):
        with c:
            st.markdown(
                f'<div style="background:{theme.PANEL};padding:6px 10px;'
                f'border-radius:2px;font-family:\'IBM Plex Mono\','
                f'monospace"><span class="desk-eyebrow" '
                f'style="color:{theme.MUTED}">{label}</span><br>'
                f'<span style="color:{theme.TEXT};font-size:0.9rem">'
                f'{txt}</span></div>', unsafe_allow_html=True)

with st.expander("DES — profile", expanded=(func == "DES")):
    sec, ind = snap.get("sector"), snap.get("industry")
    if sec or ind:
        st.markdown(f'<div class="desk-eyebrow">{sec or ""}'
                    f'{" · " + ind if ind else ""}</div>',
                    unsafe_allow_html=True)
    st.markdown(snap.get("summary") or
                "No profile available for this security type.")

with st.expander("FA — financials (annual, $bn)", expanded=(func == "FA")):
    fin = data.ticker_financials(sym)
    if fin.empty:
        st.markdown('<div class="desk-note">Financials unavailable — '
                    'not a company, or Yahoo is rate-limiting this '
                    'endpoint. Try again in a minute.</div>',
                    unsafe_allow_html=True)
    else:
        st.dataframe(theme.neg_red((fin / 1e9).style.format("{:,.2f}")),
                     use_container_width=True)

theme.note("Yahoo Finance, delayed — Tier 2 market data, Tier 3 once "
           "you're reading estimates. A quote page tells you what IS; "
           "the Notebook is where you write what you think it MEANS.")
