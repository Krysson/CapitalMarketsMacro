"""News Wire — free RSS/Atom feeds rendered as a terminal tape.

Two tapes, deliberately separated to teach the Data Reliability Tiers:
PRIMARY   — the agencies themselves (Fed, BLS, BEA).
NARRATIVE — financial media; never evidence on its own.
Fetching lives in desk/wire.py (concurrent, short timeouts, fail-soft).
"""
import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st

from desk import theme, wire

st.set_page_config(page_title="Wire — Desk", page_icon="▪", layout="wide")
st.markdown(
    "<style>.wireln{color:#E8E6E1;text-decoration:none}"
    ".wireln:visited{color:#8A8880}"
    ".wireln:hover{color:#FF9F1C}</style>", unsafe_allow_html=True)
theme.header(
    "BOOK III · THE WIRE",
    "News Wire",
    "Two tapes. The primary tape is the source; the narrative tape is the "
    "story being told about the source. Never confuse the two.")


def tape(label: str, tier: str, feeds: list[tuple[str, str]],
         src_color: str, preloaded=None) -> None:
    st.subheader(label)
    st.markdown(f'<div class="desk-eyebrow" style="color:{theme.MUTED}">'
                f'{tier}</div>', unsafe_allow_html=True)
    if preloaded is not None:
        items, dead = preloaded
    else:
        with st.spinner("Pulling the tape…"):
            items, dead = wire.fetch_tape(feeds)
    items = wire.us_filter(items)
    if dead:
        st.markdown(f'<div class="desk-note" style="color:{theme.RED}">'
                    f'FEED DOWN: {", ".join(dead)} — tape continues '
                    f'without it.</div>', unsafe_allow_html=True)
    if not items:
        st.warning("No items — all feeds unreachable. Try again shortly.")
        return
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    lines, fresh = [], 0
    for it in items:
        seen = st.session_state.setdefault("wire_seen", set())
        is_today = bool(it["when"]) and it["when"].date() == today
        is_new = is_today and it["link"] not in seen
        fresh += int(is_new)
        stamp = (it["when"].strftime("%d-%b %H:%M") if it["when"]
                 else "        --:--")
        title = it["title"].replace("<", "&lt;").replace(">", "&gt;")
        # Today's stories carry the flag at full brightness; older ones
        # dim — the eye should find NEW before it reads anything.
        chip = (f'<span style="color:{theme.INK};background:{src_color};'
                f'font-size:0.62rem;padding:0 5px;border-radius:2px;'
                f'font-weight:600;letter-spacing:0.08em;'
                f'margin-right:8px">NEW</span>' if is_new else "")
        row_style = (
            f'background:rgba(255,159,28,0.06);'
            f'border-left:2px solid {src_color};padding-left:8px;'
            if is_new else 'opacity:0.62;padding-left:10px;')
        lines.append(
            f'<div style="padding:4px 0;{row_style}'
            f'border-bottom:1px solid rgba(232,230,225,0.06);'
            f'break-inside:avoid">'
            f'<span style="color:{theme.MUTED}">{stamp} ET</span>'
            f'<span style="color:{src_color};margin:0 10px">'
            f'{it["src"]:>4}</span>{chip}'
            f'<a class="wireln" href="{it["link"]}" '
            f'target="_blank">{title}</a></div>')
    st.session_state["wire_seen"].update(
        it["link"] for it in items if it.get("link"))
    if fresh:
        st.markdown(f'<div class="desk-note" style="color:{src_color}">'
                    f'{fresh} NEW SINCE YOU LAST LOOKED '
                    f'· dimmed rows: seen this session or older</div>',
                    unsafe_allow_html=True)
    # CSS multi-column: up to 3 columns of >=340px, so wide screens read
    # like a broadsheet while phones collapse to one column on their own
    # — no separate mobile layout to maintain. break-inside:avoid keeps
    # a headline from splitting across columns.
    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace;'
        f'font-size:0.82rem;background:{theme.PANEL};padding:10px 14px;'
        f'border-left:3px solid {src_color};border-radius:2px;'
        f'columns:340px 3;column-gap:28px;'
        f'column-rule:1px solid rgba(232,230,225,0.08)">'
        + "".join(lines) + "</div>",
        unsafe_allow_html=True)


with st.spinner("Pulling the tape…"):
    prim_items, prim_dead = wire.fetch_tape(wire.PRIMARY_FEEDS)
tape("Primary tape", "TIER 1–2 · OFFICIAL RELEASES · THE SOURCE ITSELF",
     wire.PRIMARY_FEEDS, theme.AMBER,
     preloaded=(prim_items, prim_dead))
theme.note("Press releases from the Fed, BLS, and BEA — the actual "
           "documents markets reprice on, before anyone paraphrases them. "
           "When a headline here conflicts with a headline below, this "
           "one wins by definition.")

# BLS sits behind Akamai, which blocks many cloud hosts. When its lane
# is down, surface the aggregator release-chasers as a LABELED backup —
# same headlines, honestly tiered.
if any(d.startswith("BLS") for d in prim_dead):
    tape("BLS backup — via Google News",
         "TIER 5 AGGREGATOR STANDING IN FOR A BLOCKED TIER 1 FEED",
         wire.BLS_BACKUP_FEEDS, theme.YELLOW)
    theme.note("The direct BLS feeds are blocked from this host (Akamai "
               "filters many datacenter IPs; they work when the desk "
               "runs locally). These lanes chase the same releases "
               "through an aggregator — fast and usually accurate, but "
               "Tier 5 by definition: for a Notebook entry, click "
               "through and confirm the number at bls.gov before "
               "treating it as fact.")

st.divider()

tape("Narrative tape", "TIER 5 · MEDIA + AGGREGATOR · THE STORY ABOUT "
     "THE SOURCE",
     wire.NARRATIVE_FEEDS + wire.GOOGLE_NARRATIVE_FEEDS, theme.PURPLE)
theme.note("Financial media plus Google News topic lanes (Fed, rates, "
           "oil, markets — keyless RSS queries). This tape tells you "
           "what the crowd is being told — which is worth knowing — but "
           "narrative is Tier 5 data: it can lag, lead, or invert the "
           "truth. Evidence for a Notebook entry comes from the tape "
           "above, never this one.")

st.page_link("pages/4_Notebook.py",
             label="Something on the tape worth logging? → Notebook",
             )
