"""Daily Circuit — the book's 90-second read as a guided sequence.

Four steps, in order: macro dials → vol tripwire → breadth → cross-asset
confirmation. Each step ends in a check; the circuit ends at the Notebook.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from desk import data, events, signals, theme

st.set_page_config(page_title="Daily Circuit — Desk", page_icon="▪",
                   layout="wide")
theme.header(
    "BOOK III · THE DAILY CIRCUIT",
    "Daily Circuit",
    "The 90-second read, in order: state → stress → participation → "
    "confirmation. Run it the same way every day — the value is in the "
    "repetition, not any single reading. Direction, not advice.")

cpi, nfp, fomc = events.next_cpi(), events.next_nfp(), events.next_fomc()
theme.note(f"On the calendar: CPI {cpi.when} · NFP {nfp.when} · "
           f"FOMC {fomc.when}. "
           "Known vol events — a wild print on the day itself is scheduled "
           "noise until proven otherwise.")

bundle = data.macro_bundle()
sigs = signals.compute_signals(bundle)
hist = data.market_history(period="1y")

OK, WARN, NA = theme.GREEN, theme.AMBER, theme.MUTED


def step(n: int, title: str) -> None:
    st.markdown(
        f'<div style="margin-top:1.6rem">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;'
        f'color:{theme.AMBER};font-size:0.85rem">STEP {n}</span>'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:1.05rem;'
        f'font-weight:600;color:{theme.TEXT};margin-left:12px">{title}'
        f'</span></div>', unsafe_allow_html=True)


verdict = theme.readout


def col_series(t: str) -> pd.Series:
    if hist.empty or t not in hist.columns:
        return pd.Series(dtype=float)
    return hist[t].dropna()


def chg(s: pd.Series, n: int = 21) -> float | None:
    s = s.dropna()
    if len(s) <= n:
        return None
    return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100


# ---------------------------------------------------- 1 · macro dials ----
step(1, "Where does the machine stand?")
chips = st.columns(4)
for c, s in zip(chips, sigs):
    with c:
        st.markdown(
            f'<div style="border-radius:2px;padding:10px 12px;'
            f'background:{theme.PANEL};border-left:3px solid {s.color}">'
            f'<span class="desk-eyebrow" style="color:{theme.MUTED}">'
            f'{s.category}</span><br>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;'
            f'color:{s.color};font-size:0.95rem">{s.label} · {s.score}/4'
            f'</span></div>', unsafe_allow_html=True)
theme.note("Read the four dials, then ask the only question that matters "
           "at this step: did any of them CHANGE since yesterday? A dial "
           "flipping color is information; a dial holding its color is "
           "just weather. Details live on the Summary and Macro pages.")

# --------------------------------------------------- 2 · vol tripwire ----
step(2, "Is the vol market braced?")
vix, vix3m = col_series("^VIX"), col_series("^VIX3M")
if vix.empty or vix3m.empty:
    verdict(NA, "VIX / VIX3M unavailable (Yahoo Finance) — check the "
                "Volatility page or TradingView, then continue.")
else:
    ratio = (vix / vix3m).dropna()
    last = float(ratio.iloc[-1])
    if last < 1.0:
        verdict(OK, f"VIX/VIX3M = {last:.3f} — below 1.0. Term structure "
                    "in contango: near-term fear priced BELOW later fear. "
                    "Normal regime.")
    else:
        verdict(WARN, f"VIX/VIX3M = {last:.3f} — AT/ABOVE 1.0. Inverted: "
                      "the market pays up for protection NOW. Stress "
                      "regime — everything after this step reads "
                      "differently.")
    r6 = data.tail_years(ratio, 0.5)
    fig = go.Figure(go.Scatter(x=r6.index, y=r6.values, mode="lines",
                               line=dict(width=1.8, color=theme.PURPLE)))
    fig.add_hline(y=1.0, line=dict(color=theme.RED, width=1, dash="dash"))
    theme.plot(theme.style_fig(fig, "VIX / VIX3M — 6 months",
                                    height=240), use_container_width=True)
    theme.note("The tripwire, not a timing tool. Crosses above 1.0 mark "
               "regime shifts; how long it STAYS above matters more than "
               "the cross itself. Full complex (VVIX, MOVE, SKEW, the "
               "live SPY skew curve) on the Volatility page.")

# ------------------------------------------------------- 3 · breadth ----
step(3, "Is everyone coming along?")
rsp, spy = col_series("RSP"), col_series("SPY")
if rsp.empty or spy.empty:
    verdict(NA, "RSP / SPY unavailable (Yahoo Finance) — skip, note it, "
                "continue.")
else:
    br = (rsp / spy).dropna()
    d = chg(br, 21)
    if d is None:
        verdict(NA, "Not enough history for a monthly read.")
    elif d > 0:
        verdict(OK, f"RSP/SPY {d:+.2f}% over ~1 month — the average stock "
                    "is keeping up. Broad participation.")
    else:
        verdict(WARN, f"RSP/SPY {d:+.2f}% over ~1 month — cap-weight "
                      "leading. Narrow leadership: the index is being "
                      "carried, not lifted.")
    b6 = data.tail_years(br, 0.5)
    ma50 = br.rolling(50).mean().reindex(b6.index)
    fig = go.Figure()
    fig.add_scatter(x=b6.index, y=b6.values, mode="lines", name="RSP/SPY",
                    line=dict(width=1.8, color=theme.BLUE))
    fig.add_scatter(x=ma50.index, y=ma50.values, mode="lines", name="50d MA",
                    line=dict(width=1, color=theme.MUTED, dash="dot"))
    theme.plot(theme.style_fig(fig, "RSP / SPY — 6 months",
                                    height=240), use_container_width=True)
    theme.note("Breadth proxy — narrow leadership can persist far longer "
               "than feels reasonable, so this is a fragility read, not a "
               "sell signal. New index highs WITH a falling ratio = the "
               "divergence worth writing down.")

# -------------------------------------------- 4 · cross-asset confirm ----
step(4, "Does the rest of the world agree?")
reads = [
    ("HYG/LQD", None, "credit risk appetite",
     "rising = credit confirms risk-on", "falling = credit dissenting"),
    ("DX-Y.NYB", "Dollar", "the global tide",
     "falling = tailwind for risk & EM", "rising = tightening tide"),
    ("GC=F", "Gold", "the hedge bid",
     "flat/soft = little fear premium", "surging = someone is hedging"),
    ("HG=F", "Copper", "real-economy demand",
     "rising = growth confirmed", "falling = growth doubted"),
]
cc = st.columns(4)
flags = 0
for col, (key, label, sub, up_txt, dn_txt) in zip(cc, reads):
    if key == "HYG/LQD":
        h, l = col_series("HYG"), col_series("LQD")
        s = (h / l).dropna() if not h.empty and not l.empty \
            else pd.Series(dtype=float)
        label = "HYG/LQD"
    else:
        s = col_series(key)
    d = chg(s, 21)
    with col:
        if d is None:
            st.markdown(f'<div style="border-radius:2px;padding:10px 12px;'
                        f'background:{theme.PANEL};border-left:3px solid '
                        f'{NA}"><span class="desk-eyebrow" style="color:'
                        f'{theme.MUTED}">{label}</span><br>'
                        f'<span class="desk-note">no data</span></div>',
                        unsafe_allow_html=True)
            continue
        risk_off = (d < 0) if key in ("HYG/LQD", "HG=F") else (d > 0)
        color = WARN if risk_off else OK
        flags += int(risk_off)
        st.markdown(
            f'<div style="border-radius:2px;padding:10px 12px;'
            f'background:{theme.PANEL};border-left:3px solid {color}">'
            f'<span class="desk-eyebrow" style="color:{theme.MUTED}">'
            f'{label}</span><br>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;'
            f'color:{color};font-size:0.95rem">{d:+.2f}% / 1m</span><br>'
            f'<span class="desk-note">{dn_txt if risk_off else up_txt}'
            f'</span></div>', unsafe_allow_html=True)
theme.note("One-month direction of each confirmation channel. Amber ≠ "
           "bad — it means that channel is leaning against equities, "
           "which is only interesting when the channels DISAGREE with "
           "each other or with stocks. Normalized overlay on the Market "
           "page.")

# ----------------------------------------------------------- log it ----
st.divider()
step(5, "Close the loop")
if flags >= 2:
    verdict(WARN, f"{flags} of 4 confirmation channels leaning risk-off. "
                  "If equities are rising anyway, that disagreement is "
                  "today's Notebook entry.")
else:
    verdict(OK, "Confirmation channels broadly agree. A quiet circuit is "
                "still a data point — log the regime, note nothing "
                "changed, done in 90 seconds.")
st.page_link("pages/4_Notebook.py",
             label="Log a Notebook entry → Evidence first, opinion last",
             )
theme.note("The circuit isn't finished when you've LOOKED — it's finished "
           "when you've written. Evidence → Interpretation → Risks → "
           "Falsification → Decision. Most days the honest entry is "
           "'no change'; the discipline is writing it anyway.")
