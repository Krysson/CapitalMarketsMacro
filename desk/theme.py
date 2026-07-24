"""Shared visual identity for the Capital Markets Desk — TERMINAL EDITION.

Pure black, amber-on-black hierarchy, monospace everywhere, squared
corners, dense layout. Built to feel like the machine the desk's readers
are training for. Every chart keeps its right-side scale via style_fig()
and its reading note via note(). The command line (in every header)
teaches Bloomberg-style mnemonic navigation: type a function, hit GO.
"""
import re

import pandas as pd
import plotly.graph_objects as go
import json

import streamlit as st

from desk import data as _data

VERSION = "4.2.0"

INK = "#000000"
PANEL = "#0D0D0D"
TEXT = "#E8E6E1"
MUTED = "#6E6E6E"
AMBER = "#FF9F1C"
YELLOW = "#FFD75E"
GREEN = "#00B061"
RED = "#E5484D"
BLUE = "#4DA6FF"
PURPLE = "#B18CFF"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
html, body, p, li, label, button, input, textarea, select {
  font-family: 'IBM Plex Sans', sans-serif; }
[data-testid="stIconMaterial"], [class*="material-symbols"],
span[translate="no"] {
  font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important;
  font-weight: 600 !important; text-transform: uppercase;
  letter-spacing: 0.06em; color: #FF9F1C !important; }
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.05rem !important; }
h3 { font-size: 0.95rem !important; }
[data-testid="stMetricValue"], [data-testid="stMetricDelta"],
[data-testid="stDataFrame"] * { font-family: 'IBM Plex Mono', monospace; }
[data-testid="stDataFrame"] * { font-size: 0.8rem; }
[data-testid="stSidebar"] { background: #050505;
  border-right: 1px solid rgba(255,159,28,0.25); }
[data-testid="stSidebarNav"] a span {
  font-family: 'IBM Plex Mono', monospace; text-transform: uppercase;
  font-size: 0.8rem; letter-spacing: 0.08em; }
[data-testid="stExpander"] { border-radius: 2px !important;
  border-color: rgba(255,159,28,0.25) !important; }
.stButton button, .stFormSubmitButton button {
  border-radius: 2px !important; font-family: 'IBM Plex Mono', monospace;
  text-transform: uppercase; letter-spacing: 0.08em;
  border-color: rgba(255,159,28,0.5) !important; }
.stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
  border-radius: 2px !important;
  font-family: 'IBM Plex Mono', monospace !important; }
#MainMenu, footer { visibility: hidden; }
/* Streamlit floats a ~3.75rem toolbar over the page; padding must clear
   it or the tape / command bar render underneath. Solid black background
   so content scrolling beneath it looks intentional, not clipped. */
[data-testid="stHeader"] { background: #000000; }
.block-container { padding-top: 4.6rem; max-width: 1400px; }
.desk-eyebrow { font-family:'IBM Plex Mono',monospace; font-size:0.72rem;
  letter-spacing:0.24em; color:#FF9F1C; text-transform:uppercase; }
.desk-rule { height:1px; border:0; margin:0.45rem 0 0.9rem 0;
  background:linear-gradient(90deg,#FF9F1C 0,#FF9F1C 96px,
             rgba(255,159,28,0.25) 96px, rgba(255,159,28,0.06) 100%); }
.desk-caption { color:#6E6E6E; font-size:0.88rem; margin-bottom:0.4rem; }
.desk-note { color:#6E6E6E; font-size:0.78rem;
  font-family:'IBM Plex Mono',monospace; }
/* The Bloomberg amber input: solid amber field, black text. Scoped by
   placeholder so only the command line gets it, never Notebook forms. */
input[placeholder^="COMMAND"] {
  background:#FF9F1C !important; color:#000000 !important;
  font-weight:600 !important; letter-spacing:0.06em;
  border-radius:2px !important; }
input[placeholder^="COMMAND"]::placeholder {
  color:rgba(0,0,0,0.55) !important; }
div[data-baseweb="input"]:has(> input[placeholder^="COMMAND"]) {
  background:#FF9F1C !important;
  border-color:#FF9F1C !important; border-radius:2px !important; }

/* ---- full-width on wide/multi-monitor windows (v4.1.3) ----
   Streamlit caps and centers the main block; on a stretched window
   that parks content mid-screen. The desk fills what it's given. */
[data-testid="stMainBlockContainer"],
section.main .block-container {
  max-width: 100% !important;
  padding-left: 2.2rem !important;
  padding-right: 2.2rem !important; }

/* ---- terminal chrome: navigation & controls (v3.16) ---- */
section[data-testid="stSidebar"] {
  background: #000; border-right: 1px solid #1A1A1A; }
[data-testid="stSidebarNav"] span,
section[data-testid="stSidebar"] a span {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.76rem !important; letter-spacing: 0.07em;
  text-transform: uppercase; }
[data-testid="stSidebarNav"] header,
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {
  font-family: 'IBM Plex Mono', monospace !important;
  color: #FF9F1C !important; letter-spacing: 0.14em;
  text-transform: uppercase; font-size: 0.66rem !important; }
.stButton > button, .stDownloadButton > button,
.stFormSubmitButton > button {
  font-family: 'IBM Plex Mono', monospace !important;
  text-transform: uppercase; letter-spacing: 0.08em;
  border-radius: 2px !important; font-size: 0.78rem !important; }
.stTabs [data-baseweb="tab"] {
  font-family: 'IBM Plex Mono', monospace !important;
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.74rem !important; }
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.78rem !important; letter-spacing: 0.05em; }
</style>
"""

# Command-line routes. Mnemonics chosen to match the real Bloomberg
# function where one exists — the point is transferable muscle memory.
_ROUTES = {
    "HOME": "pages/0_Summary.py", "SUM": "pages/0_Summary.py",
    "CIR": "pages/0_Daily_Circuit.py", "CIRCUIT": "pages/0_Daily_Circuit.py",
    "MAC": "pages/1_Macro.py", "MACRO": "pages/1_Macro.py",
    "ECO": "pages/13_Calendar.py", "CAL": "pages/13_Calendar.py",
    "WEI": "pages/9_Global.py", "FXC": "pages/9_Global.py",
    "GLOBAL": "pages/9_Global.py",
    "MKT": "pages/2_Market.py",
    "VOL": "pages/3_Volatility.py", "VIX": "pages/3_Volatility.py",
    "NOTE": "pages/4_Notebook.py", "NB": "pages/4_Notebook.py",
    "TOP": "pages/5_Wire.py", "N": "pages/5_Wire.py",
    "WIRE": "pages/5_Wire.py",
    "BLP": "pages/00_Launchpad.py", "PAD": "pages/00_Launchpad.py",
    "Q": "pages/6_Quote.py", "QUOTE": "pages/6_Quote.py",
    "ASK": "pages/12_Desk_Analyst.py",
    "ANALYST": "pages/12_Desk_Analyst.py",
    "IB": "pages/12_Desk_Analyst.py",
    "FED": "pages/10_Fed.py", "DIFF": "pages/10_Fed.py",
    "TIME": "pages/11_Time_Machine.py", "TM": "pages/11_Time_Machine.py",
    "REWIND": "pages/11_Time_Machine.py",
    "FUT": "pages/8_Futures.py", "CTM": "pages/8_Futures.py",
    "CMDTY": "pages/8_Futures.py",
    "GC": "pages/7_Rates.py", "YC": "pages/7_Rates.py",
    "RATES": "pages/7_Rates.py", "CRV": "pages/7_Rates.py",
    "HIST": "pages/14_History.py", "TRACK": "pages/14_History.py",
    "HISTORY": "pages/14_History.py",
    "GEN": "pages/15_Ideas.py", "IDEA": "pages/15_Ideas.py",
    "IDEAS": "pages/15_Ideas.py",
    "PAPER": "pages/18_Paper.py", "PB": "pages/18_Paper.py",
    "BOOK": "pages/18_Paper.py",
    "FLOW": "pages/17_Flow.py", "FLOWS": "pages/17_Flow.py",
}

_FUNC_TOKENS = {"GP", "DES", "FA"}


def _parse_command(c: str) -> tuple:
    """Pure command parser. Returns one of:
    ("help",) · ("page", path) · ("quote", "fred"|"yf", symbol, func)
    · ("unknown", token) · ("none",)
    Priority: page mnemonics > FRED aliases > ticker shape — so VIX still
    opens the Volatility page; use ^VIX for the raw chart.
    """
    toks = c.split()
    if not toks:
        return ("none",)
    if toks[0] in ("HELP", "?"):
        return ("page", "pages/16_Help.py")
    if len(toks) == 1 and toks[0] in _ROUTES:
        return ("page", _ROUTES[toks[0]])
    if toks[0] == "FRED" and len(toks) >= 2:
        return ("quote", "fred", toks[1], "")
    if toks[0] == "EIA" and len(toks) >= 2:
        return ("quote", "eia", toks[1], "")
    if toks[0] in ("SEARCH", "FIND") and len(toks) >= 2:
        return ("search", " ".join(toks[1:]))
    if len(toks) == 1 and toks[0] in _data.FRED_ALIASES:
        return ("quote", "fred", _data.FRED_ALIASES[toks[0]], "")
    if len(toks) == 1 and toks[0] in _data.EIA_ALIASES:
        return ("quote", "eia", _data.EIA_ALIASES[toks[0]][0], "")
    if len(toks) == 1 and toks[0] in _data.CBOE_ALIASES:
        return ("quote", "cboe", _data.CBOE_ALIASES[toks[0]], "")
    joined = " ".join(toks)
    if ("/" in joined or "*" in joined
            or any(tk in ("+", "-") for tk in toks)):
        import re as _re
        if _re.fullmatch(r"[A-Z0-9\^=\.\-\s\+\*/\(\)]+", joined):
            return ("quote", "expr", joined, "")
    if toks[0] in ("CRACK", "CRACK321", "CRACKS"):
        return ("quote", "calc", "CRACK", "")
    if re.fullmatch(r"[A-Z0-9.\-^=]{1,12}", toks[0]):
        func = toks[1] if len(toks) > 1 and toks[1] in _FUNC_TOKENS else ""
        return ("quote", "yf", toks[0], func)
    return ("unknown", toks[0])

FUNCTIONS_TABLE = """
| FUNCTION | PAGE | ON THE REAL MACHINE |
|---|---|---|
| `HOME` | Summary | HOME — your start page |
| `BLP` | Launchpad | BLP — Launchpad, everything tiled at once |
| `CIR` | Daily Circuit | (house function — your routine) |
| `MAC` | Macro | macro dials & panels |
| `ECO` / `CAL` | Calendar | ECO — economic calendar · anchors + full schedule |
| `MKT` | Market (US) | trend, breadth, credit ratios |
| `WEI` / `FXC` | Global | WEI — world equity indices · FXC — FX crosses |
| `VIX` / `VOL` | Volatility | VIX Index GP, VCAL |
| `NOTE` | Notebook | NOTE — notes & ideas |
| `TOP` / `N` | News Wire | TOP — top news · N — news |
| `GC` / `YC` | Rates & Credit | GC — graph curves · yield curve + OAS |
| `CTM` / `FUT` | Futures | CTM — contract table · board + term structure + COT |
| `DIFF` / `FED` | Fed Statement Diff | redline vs the prior statement |
| `TM` / `TIME` | Time Machine | the desk as of any past date (ALFRED vintages) |
| `HIST` / `TRACK` | Regime History | the dials' live-accrued track record, one git commit per night |
| `GEN` / `IDEA` | Idea Desk | Ch. 15's eight generators + five gates — passcode-gated |
| `PAPER` / `PB` | Paper Desk | test what cleared the gates — the ticket refuses orders without a kill switch |
| `FLOW` | Flow Desk | rotation monitor, FINRA short-volume ratios, live-accrued ETF flows + streaks |
| `HELP` / `?` | Help | this table + the operating manual |
| `ASK` / `IB` | Desk Analyst | chat with the desk's AI analyst (IB — chat, on the machine) |
| `GOOG` · `GOOG FA` · `GOOG DES` | Quote | GOOG US Equity GP / FA / DES |
| `CPI` `NFP` `EFFR` `SOFR` `10Y` `CURVE`… | Quote | ECO series graph |
| `FRED <SERIES_ID>` | Quote | any FRED series, e.g. FRED DGS30 |
| `CUSHING` `CRUDE` `GASOLINE` `NATGAS` `WTISPOT`… | Quote | EIA weekly petroleum/gas series (needs EIA_API_KEY) |
| `SKEW` / `VVIX` | Quote | Cboe index history from Cboe's own CDN |
| `CRACK` | Quote | computed 3-2-1 / gasoline / diesel crack spreads from CL, RB, HO |
| `HYG/LQD` · `GC=F/SI=F` · `RB=F*42 - CL=F` | Quote | expression charts — `/` and `*` bind anywhere; `+` and `-` need spaces (so `BTC-USD` stays a ticker) |
| `EIA <SERIES_ID>` | Quote | any EIA v1 series ID, e.g. EIA PET.WCESTUS1.W |
| `SEARCH <words>` | Quote | search FRED's catalog, e.g. SEARCH housing starts |

"""


def command_line() -> None:
    """Bloomberg-style command field. Renders on every page via header().
    The LIVE toggle (right) flips the market fetchers onto a ~60s cache
    so computed charts track the streaming tape during a session."""
    left, right = st.columns([10, 1.6])
    with left:
        with st.form("deskcmd", clear_on_submit=True, border=False):
            c1, c2 = st.columns([9, 1])
            cmd = c1.text_input(
                "command", label_visibility="collapsed",
                placeholder="COMMAND <GO>   ·   TYPE HELP FOR FUNCTIONS")
            go = c2.form_submit_button("GO", use_container_width=True)
    with right:
        st.toggle("LIVE", key="intraday",
                  help="~60s market-data polling while you watch a "
                       "session (prices/quotes only — FRED, chains, "
                       "and records keep their schedules). The tape "
                       "streams; the charts poll.")
    if not (go and cmd.strip()):
        return
    c = cmd.upper().replace("<GO>", "").strip()
    action = _parse_command(c)
    if action[0] == "page":
        st.switch_page(action[1])
    elif action[0] == "quote":
        st.session_state["quote_query"] = action[1:]
        st.session_state.pop("fred_search", None)
        st.switch_page("pages/6_Quote.py")
    elif action[0] == "search":
        st.session_state["fred_search"] = action[1]
        st.session_state.pop("quote_query", None)
        st.switch_page("pages/6_Quote.py")
    elif action[0] == "unknown":
        st.markdown(
            f'<div class="desk-note" style="color:{RED}">{action[1]} — '
            f'UNKNOWN FUNCTION. TYPE HELP &lt;GO&gt; FOR THE LIST.</div>',
            unsafe_allow_html=True)


TAPE_SYMBOLS = [
    {"proName": "FOREXCOM:SPXUSD",  "title": "S&P 500"},      # RT CFD
    {"proName": "FOREXCOM:NSXUSD",  "title": "Nasdaq 100"},   # RT CFD
    {"proName": "CAPITALCOM:RTY",   "title": "Russell 2000"}, # RT CFD (verify — see note)
    {"proName": "FOREXCOM:DJI",     "title": "Dow"},          # RT CFD
    {"proName": "US10Y",       "title": "US 10Y"},       # FRED:DGS10
    {"proName": "CAPITALCOM:DXY",   "title": "Dollar"},       # RT CFD
    {"proName": "TVC:GOLD",         "title": "Gold"},         # RT spot
    {"proName": "TVC:SILVER",       "title": "SILVER"},         # RT spot
    {"proName": "TVC:USOIL",        "title": "WTI"},          # RT CFD
    {"proName": "BITSTAMP:BTCUSD",  "title": "Bitcoin"},      # RT
    {"proName": "CAPITALCOM:VIX",   "title": "VIX"},          # RT CFD mirror
]


def embed(html: str, height: int) -> None:
    """House renderer for script-bearing HTML (the TradingView glass).

    GOTCHA (July 2026): streamlit.components.v1.html was deprecated and
    then REMOVED after 2026-06-01 — when Streamlit Cloud rolled past
    the removal, every widget rendered blank. st.iframe is the official
    replacement and accepts raw HTML directly. The fallback keeps older
    local installs working; the try/except keeps display glass from
    ever taking down a page of computed signals — the glass is
    decoration, the signals are the desk.
    """
    try:
        if hasattr(st, "iframe"):
            # components.html clipped overflow by default; st.iframe does
            # not, and its document keeps default body margins — every
            # widget grew a scrollbar. Reset both inside the iframe's own
            # document (we author this HTML, so this is in-bounds).
            reset = ("<style>html,body{margin:0!important;"
                     "padding:0!important;overflow:hidden!important}"
                     "::-webkit-scrollbar{display:none}"
                     "html{scrollbar-width:none}</style>")
            st.iframe(reset + html, height=height)
            return
        import streamlit.components.v1 as components
        components.html(html, height=height)
    except Exception:
        pass


def tape() -> None:
    """The terminal's ticker tape — rendered by header() on every page."""
    html = f"""
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js"
    async>
  {{
    "symbols": {json.dumps(TAPE_SYMBOLS)},
    "showSymbolLogo": false,
    "colorTheme": "dark",
    "isTransparent": true,
    "displayMode": "regular",
    "locale": "en"
  }}
  </script>
</div>
"""
    embed(html, height=48)


def news_marquee() -> None:
    """Scrolling headline ticker: Tier 1 agencies amber and first,
    aggregator/media purple behind them. Hover pauses."""
    try:
        from desk import wire
        items = wire.ticker_items()
    except Exception:
        items = []
    if not items:
        return
    spans = []
    for i in items:
        color = AMBER if i.get("primary") else "#B39DDB"
        src = i.get("src", "")
        title = (i["title"][:110].replace("<", "&lt;")
                 .replace("$", "&#36;"))
        link = i.get("link") or "#"
        spans.append(
            f'<a href="{link}" target="_blank" style="color:{color};'
            f'text-decoration:none"><span style="opacity:0.6">{src}'
            f'</span> {title}</a>')
    track = ' <span style="color:#3A3A3A">\u25c6</span> '.join(spans)
    dur = max(40, 7 * len(items))
    st.markdown(
        f'<style>@keyframes deskscroll {{from{{transform:translateX(0)}}'
        f'to{{transform:translateX(-50%)}}}}'
        f'.desk-marquee:hover .desk-track'
        f'{{animation-play-state:paused}}</style>'
        f'<div class="desk-marquee" style="overflow:hidden;'
        f'white-space:nowrap;border-top:1px solid #1B1B1B;'
        f'border-bottom:1px solid #1B1B1B;padding:3px 0;'
        f'margin-bottom:6px">'
        f'<div class="desk-track" style="display:inline-block;'
        f'white-space:nowrap;font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.72rem;letter-spacing:0.02em;'
        f'animation:deskscroll {dur}s linear infinite">'
        f'{track} <span style="color:#3A3A3A">\u25c6</span> {track}'
        f'</div></div>', unsafe_allow_html=True)


def header(eyebrow: str, title: str, caption: str | None = None) -> None:
    """Terminal page header: command line, eyebrow, title, amber rule."""
    st.markdown(_CSS, unsafe_allow_html=True)
    tape()
    news_marquee()
    st.sidebar.markdown(
        f'<div class="desk-note" style="text-align:center;'
        f'letter-spacing:0.12em;margin-top:6px">CAPITAL MARKETS DESK '
        f'&middot; v{VERSION}</div>', unsafe_allow_html=True)
    command_line()
    st.markdown(f'<div class="desk-eyebrow">{eyebrow}</div>',
                unsafe_allow_html=True)
    st.title(title)
    st.markdown('<div class="desk-rule"></div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="desk-caption">{caption}</div>',
                    unsafe_allow_html=True)


# Mobile-safe chart config: no toolbar, no scroll-capture, double-tap
# resets. Applied by theme.plot() — the one way charts reach the screen.
# Bloomberg posture: opens clean, power available. Wheel + box zoom,
# pan, double-click reset; toolbar trimmed to the four buttons that
# matter. Chart CONTENT (MAs, bands, notes) is untouched by this.
_PLOTLY_CFG = {"displayModeBar": True, "scrollZoom": True,
               "doubleClick": "reset", "displaylogo": False,
               "modeBarButtonsToRemove": [
                   "lasso2d", "select2d", "autoScale2d",
                   "hoverClosestCartesian", "hoverCompareCartesian",
                   "toggleSpikelines"]}


_LOOKBACKS = {"1M": 1/12, "3M": 0.25, "6M": 0.5, "1Y": 1.0,
              "2Y": 2.0, "5Y": 5.0, "10Y": 10.0, "MAX": 99.0}


def lookback(key: str, default: str = "1Y",
             options: tuple = ("1M", "3M", "6M", "1Y", "2Y", "5Y",
                               "MAX")) -> float:
    """Range buttons, desk-style: server-side re-slice so the y-axis
    refits the window perfectly (what Plotly's own x-zoom can't do).
    Returns years as float."""
    picker = getattr(st, "segmented_control", None)
    if picker:
        sel = picker(" ", options, default=default, key=key,
                     label_visibility="collapsed")
    else:                                   # older Streamlit fallback
        sel = st.radio(" ", options, index=options.index(default),
                       key=key, horizontal=True,
                       label_visibility="collapsed")
    return _LOOKBACKS.get(sel or default, 1.0)


def fmt_last(series) -> str:
    """'JUN 2026 · 6.72' — the last print, title-ready."""
    try:
        s = series.dropna()
        ts, v = s.index[-1], float(s.iloc[-1])
        val = f"{v:,.2f}" if abs(v) >= 1 else f"{v:,.3f}"
        return f"{ts:%b %Y} · {val}".upper()
    except Exception:
        return ""


def plot(fig: go.Figure, **kwargs) -> None:
    """House renderer: full width + mobile config on every chart."""
    kwargs.setdefault("use_container_width", True)
    cfg = {**_PLOTLY_CFG, **kwargs.pop("config", {})}
    st.plotly_chart(fig, config=cfg, **kwargs)


def style_fig(fig: go.Figure, title: str | None = None,
              height: int = 300, unified_hover: bool = True,
              right_text: str | None = None,
              right_color: str | None = None) -> go.Figure:
    """House chart style: black terminal, right-side scale, quiet grid.

    Top-band layout (the un-mashing): title row on top, legend row
    BELOW it, plot below that — they no longer share one margin band.
    right_text renders on the title row, right-aligned (last price,
    current value, etc.).
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono, monospace", size=11, color=TEXT),
        height=height,
        margin=dict(l=8, r=8, t=70 if title else 34, b=8),
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10.5)),
        hovermode="x unified" if unified_hover else "closest",
        hoverlabel=dict(bgcolor=PANEL,
                        font_family="IBM Plex Mono, monospace"),
        dragmode=False,   # charts must never trap a phone's scroll
    )
    if title:
        fig.update_layout(title=dict(
            text=title.upper(), x=0.0, xanchor="left",
            y=0.985, yanchor="top",
            font=dict(family="IBM Plex Mono, monospace", size=12.5,
                      color=AMBER)))
    if right_text:
        fig.add_annotation(
            text=right_text, xref="paper", yref="paper",
            x=1.0, y=1.0, xanchor="right", yanchor="bottom",
            yshift=26 if title else 4, showarrow=False,
            font=dict(family="IBM Plex Mono, monospace", size=12.5,
                      color=right_color or TEXT))
    fig.update_xaxes(showgrid=False, linecolor="rgba(232,230,225,0.25)",
                     tickcolor="rgba(232,230,225,0.25)")
    fig.update_yaxes(side="right", showgrid=True, zeroline=False,
                     gridcolor="rgba(232,230,225,0.07)",
                     linecolor="rgba(232,230,225,0.25)",
                     tickcolor="rgba(232,230,225,0.25)")
    return fig


def candles(df, name: str = "") -> go.Candlestick:
    """House candlestick trace from an OHLC frame."""
    return go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=name,
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED, decreasing_fillcolor=RED,
        line=dict(width=1), whiskerwidth=0.6,
    )


def neg_red(styler, subset=None):
    """House rule (v3.17): negative numbers read RED in every table —
    the eye finds the drawdown before the label. Chain after
    .style.format(); leaves non-numerics and NaN alone."""
    return styler.map(
        lambda v: f"color: {RED}"
        if isinstance(v, (int, float)) and pd.notna(v) and v < 0 else "",
        subset=subset)


def note(text: str) -> None:
    """Small interpretive caption under a chart: how to read it."""
    st.markdown(f'<div class="desk-note" style="margin:-6px 0 14px 2px">'
                f'{text}</div>', unsafe_allow_html=True)


def recession_bands(fig: go.Figure, usrec, start=None, end=None) -> go.Figure:
    """Gray NBER recession bands (FRED USREC) behind a chart's traces.

    Bands are clipped to [start, end] so they respect the lookback window.
    No-op if the USREC series is missing or no recession falls in view.
    """
    if usrec is None or getattr(usrec, "empty", True):
        return fig
    s = usrec.dropna()
    if start is not None:
        s = s[s.index >= (pd.Timestamp(start) - pd.DateOffset(months=2))]
    if s.empty:
        return fig

    blocks, run_start, prev = [], None, None
    for ts, val in (s >= 0.5).items():
        if val and run_start is None:
            run_start = ts
        elif not val and run_start is not None:
            blocks.append((run_start, prev))
            run_start = None
        prev = ts
    if run_start is not None:                      # recession ongoing at end
        blocks.append((run_start, s.index.max()))

    for b0, b1 in blocks:
        b1 = b1 + pd.DateOffset(months=1)          # USREC=1 covers the month
        if end is not None and b0 > end:
            continue
        if start is not None and b1 < start:
            continue
        x0 = max(b0, pd.Timestamp(start)) if start is not None else b0
        x1 = min(b1, pd.Timestamp(end)) if end is not None else b1
        fig.add_vrect(x0=x0, x1=x1, layer="below", line_width=0,
                      fillcolor="rgba(200,200,200,0.10)")
    return fig


def sparkline_svg(s, color: str = AMBER, width: int = 210,
                  height: int = 34) -> str:
    """Tiny inline-SVG sparkline for the Summary cards. '' if no data."""
    s = s.dropna()
    if len(s) < 2:
        return ""
    if len(s) > 80:                                # thin dense daily series
        step = -(-len(s) // 80)                    # ceiling division
        s = pd.concat([s.iloc[::step], s.iloc[[-1]]]).drop_duplicates()
    vals = s.to_numpy(dtype=float)
    lo, hi = vals.min(), vals.max()
    rng = (hi - lo) or 1.0
    pad, n = 3.0, len(vals)
    pts = [(pad + i * (width - 2 * pad) / (n - 1),
            height - pad - (v - lo) / rng * (height - 2 * pad))
           for i, v in enumerate(vals)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" style="display:block;margin-top:10px">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" '
        f'stroke-width="1.6" stroke-opacity="0.9" '
        f'vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2" fill="{color}"/></svg>'
    )


def panel_bar(title: str, right: str = "") -> None:
    """Bloomberg-style panel title bar: function name left, value right."""
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:baseline;background:#161616;'
        f'border-top:2px solid {AMBER};padding:3px 10px;'
        f'margin:8px 0 4px 0;border-radius:2px 2px 0 0">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.72rem;letter-spacing:0.18em;color:{AMBER};'
        f'text-transform:uppercase">{title}</span>'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.78rem;color:{TEXT}">{right}</span></div>',
        unsafe_allow_html=True)


def readout(color: str, text: str) -> None:
    """Live verdict line under a chart: what it shows RIGHT NOW.

    The static note() teaches how to read the chart; this states the
    current reading. Color = regime/direction, never good vs. bad.
    """
    st.markdown(
        f'<div style="border-left:3px solid {color};padding:6px 12px;'
        f'background:{PANEL};border-radius:0;'
        f'margin:8px 0 4px 0;font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.9rem;color:{TEXT}">{text}</div>',
        unsafe_allow_html=True)
