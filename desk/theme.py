"""Shared visual identity for the Capital Markets Desk.

Tokens: ink-navy terminal background, amber accent, Spectral serif for
chapter-style headings, IBM Plex Mono for numerals. Every chart gets a
right-side price scale via style_fig().
"""
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
html, body, [class*="st-"], p, li { font-family: 'IBM Plex Sans', sans-serif; }
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
