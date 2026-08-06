"""Economic Calendar — ECO <GO>. The desk's schedule of scheduled risk.

Two layers, deliberately: the desk's own verified anchors (hardcoded
from BLS/Fed source documents — Tier 1) on top, and a live aggregator
calendar below for everything else. When they disagree, trust the
anchors and tell us.
"""
import streamlit as st

from desk import data, events, theme

st.set_page_config(page_title="Calendar — Desk", page_icon="▪",
                   layout="wide")
theme.header(
    "BOOK II · SCHEDULED RISK",
    "Economic Calendar",
    "ECO on the real machine is the economic calendar — same here. "
    "Anchors first (verified at the source), the wide net below. "
    "Every event on this page is a known date wearing a price — the "
    "vol surface shows you which ones the market is paying attention "
    "to.")

# ------------------------------------------------- verified anchors ----
try:
    bundle = data.macro_bundle()
    prints = data.print_lines(data.latest_prints(bundle))
except Exception:
    prints = {}
cols = st.columns(3)
for col, (label, ev) in zip(cols, (("CPI", events.next_cpi()),
                                   ("NFP", events.next_nfp()),
                                   ("FOMC", events.next_fomc()))):
    with col:
        st.markdown(
            f'<div style="background:{theme.PANEL};padding:10px 14px;'
            f'border-radius:2px;border-left:3px solid {theme.AMBER}">'
            f'<span class="desk-eyebrow" style="color:{theme.MUTED}">'
            f'{label}</span><br>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;'
            f'color:{theme.TEXT};font-size:1.05rem">{ev.when}</span>'
            + (f'<br><span style="font-family:\'IBM Plex Mono\','
               f'monospace;color:{theme.YELLOW};font-size:0.8rem">'
               f'{prints[label]}</span>' if prints.get(label) else "")
            + '</div>', unsafe_allow_html=True)
theme.note("These three anchors are hardcoded from the BLS release "
           "schedule and the Fed's meeting calendar — primary source, "
           "Tier 1, refreshed each time the agencies publish next "
           "year's dates. The widget below is an aggregator: Tier 3 "
           "convenience. If the two ever disagree, the anchors win.")

st.divider()

# ------------------------------------------------- v4.9.0: OpEx ----
theme.panel_bar("Options expiration",
                "pure computation · third Fridays · nothing to fail")
_ops = events.opex_dates(6)
_opc = st.columns(len(_ops)) if _ops else []
for _c, _o in zip(_opc, _ops):
    _wt = _o["witching"]
    _c.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;'
        f'padding:8px 10px;background:{theme.PANEL};'
        f'border-left:3px solid '
        f'{theme.RED if _wt else theme.AMBER};border-radius:2px">'
        f'<span style="color:{theme.TEXT};font-size:1.0rem">'
        f'{_o["date"]:%d %b %Y}</span><br>'
        f'<span style="color:'
        f'{theme.RED if _wt else theme.MUTED};font-size:0.72rem;'
        f'letter-spacing:0.06em">'
        f'{"TRIPLE WITCHING" if _wt else "monthly opex"}</span>'
        f'</div>', unsafe_allow_html=True)
theme.note("Third Friday each month; March, June, September, and "
           "December add expiring index futures and futures options — "
           "'triple witching', the heaviest mechanical volume days of "
           "the quarter. This is when the walls (Volatility page) "
           "matter most and then RESET: pinning pressure into the "
           "date, unclamped tape after it. Computed from the calendar "
           "itself, not fetched — [T1] by construction.")

st.divider()

# ---------------------------------------------------- the wide net ----
theme.panel_bar("Full calendar", "aggregator · all releases · live")
_CAL = """
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-events.js"
    async>
  {
    "colorTheme": "dark",
    "isTransparent": true,
    "width": "100%",
    "height": 700,
    "locale": "en",
    "importanceFilter": "0,1",
    "countryFilter": "us,eu,gb,jp,cn,ca,au,ch"
  }
  </script>
</div>"""
theme.embed(_CAL, height=710)
theme.note("Filtered to medium/high importance across the majors' "
           "economies — the releases that move the pairs on the Global "
           "page. Reading discipline: the FORECAST column is the "
           "market's priced expectation; the surprise (actual minus "
           "forecast) is what moves price, not the level. A 'bad' "
           "number better than forecast is a bullish print. That "
           "inversion confuses every trainee once.")
