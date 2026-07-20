"""News Wire — free RSS/Atom feeds rendered as a terminal tape.

Two tapes, deliberately separated to teach the Data Reliability Tiers:
PRIMARY   — the agencies themselves (Fed, BLS, BEA).
NARRATIVE — financial media; never evidence on its own.
Fetching lives in desk/wire.py (concurrent, short timeouts, fail-soft).
"""
import streamlit as st

from desk import theme, wire

st.set_page_config(page_title="Wire — Desk", page_icon="🗞️", layout="wide")
theme.header(
    "BOOK III · THE WIRE",
    "News Wire",
    "Two tapes. The primary tape is the source; the narrative tape is the "
    "story being told about the source. Never confuse the two.")


def tape(label: str, tier: str, feeds: list[tuple[str, str]],
         src_color: str) -> None:
    st.subheader(label)
    st.markdown(f'<div class="desk-eyebrow" style="color:{theme.MUTED}">'
                f'{tier}</div>', unsafe_allow_html=True)
    with st.spinner("Pulling the tape…"):
        items, dead = wire.fetch_tape(feeds)
    if dead:
        st.markdown(f'<div class="desk-note" style="color:{theme.RED}">'
                    f'FEED DOWN: {", ".join(dead)} — tape continues '
                    f'without it.</div>', unsafe_allow_html=True)
    if not items:
        st.warning("No items — all feeds unreachable. Try again shortly.")
        return
    lines = []
    for it in items:
        stamp = (it["when"].strftime("%d-%b %H:%M") if it["when"]
                 else "        --:--")
        title = it["title"].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div style="padding:3px 0;border-bottom:1px solid '
            f'rgba(232,230,225,0.06)">'
            f'<span style="color:{theme.MUTED}">{stamp} ET</span>'
            f'<span style="color:{src_color};margin:0 10px">'
            f'{it["src"]:>4}</span>'
            f'<a href="{it["link"]}" target="_blank" style="color:'
            f'{theme.TEXT};text-decoration:none">{title}</a></div>')
    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.82rem;background:{theme.PANEL};padding:10px 14px;'
        f'border-left:3px solid {src_color};border-radius:2px">'
        + "".join(lines) + "</div>",
        unsafe_allow_html=True)


tape("Primary tape", "TIER 1–2 · OFFICIAL RELEASES · THE SOURCE ITSELF",
     wire.PRIMARY_FEEDS, theme.AMBER)
theme.note("Press releases from the Fed, BLS, and BEA — the actual "
           "documents markets reprice on, before anyone paraphrases them. "
           "When a headline here conflicts with a headline below, this "
           "one wins by definition. (BLS blocks some cloud hosts — if its "
           "lane shows down with HTTP 403, it will still work when the "
           "desk runs locally.)")

st.divider()

tape("Narrative tape", "TIER 5 · MEDIA · THE STORY ABOUT THE SOURCE",
     wire.NARRATIVE_FEEDS, theme.PURPLE)
theme.note("Financial media. This tape tells you what the crowd is being "
           "told — which is worth knowing — but narrative is Tier 5 data: "
           "it can lag, lead, or invert the truth. Evidence for a "
           "Notebook entry comes from the tape above, never this one.")

st.page_link("pages/4_Notebook.py",
             label="Something on the tape worth logging? → Notebook",
             icon="📓")
