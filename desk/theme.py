"""Shared visual identity for the Capital Markets Desk.

Tokens: ink-navy terminal background, amber accent, Spectral serif for
chapter-style headings, IBM Plex Mono for numerals. Every chart gets a
right-side price scale via style_fig().
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

INK = "#0D1117"
PANEL = "#161D2A"
TEXT = "#E6E4DC"
MUTED = "#8B95A7"
AMBER = "#E8A33D"
GREEN = "#26A269"
RED = "#D64545"
BLUE = "#5B8DC9"
PURPLE = "#9A6BD1"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Spectral:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, p, li, label, button, input, textarea, select {
  font-family: 'IBM Plex Sans', sans-serif; }
[data-testid="stIconMaterial"], [class*="material-symbols"],
span[translate="no"] {
  font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3 { font-family: 'Spectral', serif !important; font-weight: 600 !important; }
[data-testid="stMetricValue"], [data-testid="stMetricDelta"],
[data-testid="stDataFrame"] * { font-family: 'IBM Plex Mono', monospace; }
[data-testid="stDataFrame"] * { font-size: 0.84rem; }
[data-testid="stSidebarNav"] a span { font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.4rem; max-width: 1250px; }
.desk-eyebrow { font-family:'IBM Plex Mono',monospace; font-size:0.72rem;
  letter-spacing:0.24em; color:#E8A33D; text-transform:uppercase; }
.desk-rule { height:2px; border:0; margin:0.5rem 0 1.0rem 0;
  background:linear-gradient(90deg,#E8A33D 0,#E8A33D 72px,
             rgba(232,163,61,0.18) 72px, transparent 100%); }
.desk-caption { color:#8B95A7; font-size:0.92rem; margin-bottom:0.4rem; }
.desk-note { color:#8B95A7; font-size:0.8rem; font-family:'IBM Plex Mono',monospace; }
</style>
"""


def header(eyebrow: str, title: str, caption: str | None = None) -> None:
    """Chapter-style page header: eyebrow, serif title, amber rule, caption."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="desk-eyebrow">{eyebrow}</div>',
                unsafe_allow_html=True)
    st.title(title)
    st.markdown('<div class="desk-rule"></div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="desk-caption">{caption}</div>',
                    unsafe_allow_html=True)


def style_fig(fig: go.Figure, title: str | None = None,
              height: int = 300, unified_hover: bool = True) -> go.Figure:
    """House chart style: transparent, right-side scale, quiet grid."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono, monospace", size=11.5, color=TEXT),
        height=height,
        margin=dict(l=8, r=8, t=44 if title else 16, b=8),
        legend=dict(orientation="h", y=1.09, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hovermode="x unified" if unified_hover else "closest",
        hoverlabel=dict(bgcolor=PANEL, font_family="IBM Plex Mono, monospace"),
    )
    if title:
        fig.update_layout(title=dict(
            text=title, x=0.0, xanchor="left",
            font=dict(family="IBM Plex Sans, sans-serif", size=15,
                      color=TEXT)))
    fig.update_xaxes(showgrid=False, linecolor="rgba(139,149,167,0.3)",
                     tickcolor="rgba(139,149,167,0.3)")
    fig.update_yaxes(side="right", showgrid=True, zeroline=False,
                     gridcolor="rgba(139,149,167,0.12)",
                     linecolor="rgba(139,149,167,0.3)",
                     tickcolor="rgba(139,149,167,0.3)")
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


def note(text: str) -> None:
    """Small interpretive caption under a chart: how to read it."""
    st.markdown(f'<div class="desk-note" style="margin:-6px 0 14px 2px">'
                f'{text}</div>', unsafe_allow_html=True)

def recession_bands(fig: go.Figure, usrec, start=None, end=None) -> go.Figure:
    """Gray NBER recession bands (FRED USREC) behind a chart's traces.

    Bands are clipped to [start, end] so they respect the lookback window.
    No-op if the USREC series is missing or no recession falls in view.
    """
    import pandas as pd

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
                      fillcolor="rgba(139,149,167,0.14)")
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
