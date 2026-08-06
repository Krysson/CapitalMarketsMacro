"""Desk Analyst — chat with Claude about the live desk. ASK <GO>.

The analyst reads the same dashboard the trainee reads: every message
carries a fresh snapshot of the desk's computed readings. It recommends
in positioning grammar only (long/short asset classes, duration, vol,
sector tilts — never single names), always with reasoning and
falsification, in the book's voice.
"""
import streamlit as st

from desk import analyst, theme

st.set_page_config(page_title="Analyst — Desk", page_icon="▪",
                   layout="wide")
theme.header(
    "BOOK III · THE DESK ANALYST",
    "Desk Analyst",
    "An analyst wired to this desk's live readings. Ask for the morning "
    "read, a positioning view, a Notebook draft, an explanation of "
    "anything on any page — or bring your own trade idea for "
    "validation through the Part V protocol. It reasons in the book's framework — "
    "positioning grammar, evidence tiers, mandatory falsification. "
    "Training desk — direction, not advice.")

def _secret(name: str, default: str = "") -> str:
    """st.secrets.get RAISES when no secrets file exists at all (fine
    on Cloud, fatal locally) — wrap it so the page runs anywhere."""
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


api_key = _secret("ANTHROPIC_API_KEY")
if not api_key:
    st.error("No ANTHROPIC_API_KEY in app secrets. Add it in Streamlit "
             "Cloud → App settings → Secrets:")
    st.code('ANTHROPIC_API_KEY = "sk-ant-..."\n'
            '# strongly recommended on a public app — gates the chat:\n'
            'DESK_CHAT_PASSCODE = "choose-a-passphrase"')
    st.stop()

# Cost gate: this page spends real API credits per message. On a public
# deployment, set DESK_CHAT_PASSCODE so strangers can't run your tab.
passcode = _secret("DESK_CHAT_PASSCODE")
if passcode and not st.session_state.get("analyst_ok"):
    entered = st.text_input("Desk passcode", type="password")
    if entered and entered == passcode:
        st.session_state["analyst_ok"] = True
        st.rerun()
    elif entered:
        st.error("Wrong passcode.")
    st.stop()
if not passcode:
    st.markdown('<div class="desk-note" style="color:#FFD75E">No '
                'DESK_CHAT_PASSCODE set — anyone who finds this public '
                'page can spend your API credits. Add one in secrets.'
                '</div>', unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
model = c2.selectbox("Model", ["claude-sonnet-4-6",
                               "claude-opus-4-8",
                               "claude-haiku-4-5-20251001"],
                     help="Sonnet = the daily driver. Opus = strongest "
                          "reasoning, highest cost — deep sessions. "
                          "Haiku = cheapest, quick questions.")
with c1:
    st.markdown('<div class="desk-note">Each message re-reads the live '
                'desk. Conversation is kept to the last 12 turns to '
                'control cost.</div>', unsafe_allow_html=True)

if "analyst_chat" not in st.session_state:
    st.session_state["analyst_chat"] = []

# ---- Part V: idea validation (always available, any point in chat) ----
with st.expander("Validate a trade idea — Book III Part V protocol"):
    st.markdown('<div class="desk-note">State your idea in your own '
                'words — instruments, direction, and why. Any '
                'instrument is fair game here (futures, options, '
                'bonds, sectors, ETFs, single stocks). The analyst '
                'runs it through the Part V gates — thesis, structure, '
                'edge, what\'s priced in, crowd, falsification, '
                'evidence tiers — and returns VALID / INVALID / '
                'INCOMPLETE with reasons. It validates; it never '
                'proposes trades.</div>', unsafe_allow_html=True)
    idea = st.text_area(
        "Your idea", height=120,
        placeholder="e.g. Long oil futures, short oil options and "
                    "short treasury bonds to capture the spread with "
                    "protection…")
    if st.button("Run the validation") and idea.strip():
        st.session_state["analyst_chat"].append(
            {"role": "user",
             "content": "VALIDATE THIS IDEA through the Part V "
                        "protocol:\n\n" + idea.strip()})
        st.rerun()

# canned openers — the workflows this page exists for
if not st.session_state["analyst_chat"]:
    b1, b2, b3, b4 = st.columns(4)
    CANNED = {
        "Morning read + positioning": (
            "Give me the morning read: walk the desk in Circuit order "
            "(dials → vol tripwire → breadth → cross-asset → rates & "
            "credit), then give your positioning view in the standard "
            "format."),
        "Draft today's Notebook entry": (
            "Draft today's Notebook entry from the current snapshot, "
            "in the exact template, ready to paste."),
        "What's the vol market saying?": (
            "Read the volatility complex for me — the VIX/VIX3M level, "
            "what the term structure implies here, and what would "
            "change the read."),
        "Quiz me on the desk": (
            "Act as the senior on the desk: ask me three questions "
            "about today's readings that a trainee should be able to "
            "answer, wait for my answers, then grade them."),
    }
    for col, (label, prompt) in zip((b1, b2, b3, b4), CANNED.items()):
        if col.button(label, width="stretch"):
            st.session_state["analyst_chat"].append(
                {"role": "user", "content": prompt})
            st.rerun()

def _md_safe(text: str) -> str:
    """Escape $ so Streamlit doesn't eat dollar amounts as LaTeX math
    ("$83 and $100" otherwise renders everything between as garbage)."""
    return text.replace("\\$", "$").replace("$", "\\$")


for msg in st.session_state["analyst_chat"]:
    with st.chat_message(msg["role"]):
        st.markdown(_md_safe(msg["content"]))

with st.expander("WHAT THE ANALYST SEES — the exact snapshot "
                 "(v4.7.2 transparency)"):
    st.code(analyst.desk_snapshot(), language=None)
    st.caption("This text is prepended to every message. If a block "
               "is missing here, the Analyst genuinely cannot see it "
               "— the glass is the diagnosis.")

prompt = st.chat_input("Ask the desk…")
if prompt:
    st.session_state["analyst_chat"].append(
        {"role": "user", "content": prompt})
    st.rerun()

chat = st.session_state["analyst_chat"]
if chat and chat[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Reading the desk…"):
            snapshot = analyst.desk_snapshot()
        system, history = analyst.build_messages(chat, snapshot)
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            is_validation = chat[-1]["content"].startswith(
                "VALIDATE THIS IDEA")
            with client.messages.stream(
                    model=model,
                    max_tokens=2000 if is_validation else 1500,
                    system=system, messages=history) as stream:
                # escape $ per chunk (single char — safe across chunk
                # boundaries) so live streaming doesn't LaTeX-mangle
                safe_chunks = (c.replace("$", "\\$")
                               for c in stream.text_stream)
                reply = st.write_stream(safe_chunks)
                try:
                    from desk import apilog
                    _u = stream.get_final_message().usage
                    apilog.log("analyst", _u.input_tokens,
                               _u.output_tokens)
                    st.caption(f"receipt: {_u.input_tokens:,} in / "
                               f"{_u.output_tokens:,} out · logged")
                except Exception:
                    pass
            if reply:
                reply = reply.replace("\\$", "$")   # store clean text
        except Exception as ex:
            reply = None
            st.error(f"API call failed: {type(ex).__name__} — check the "
                     f"key, model access, and account credits.")
    if reply:
        st.session_state["analyst_chat"].append(
            {"role": "assistant", "content": reply})

if chat:
    if st.button("Clear conversation"):
        st.session_state["analyst_chat"] = []
        st.rerun()

theme.note("What this demonstrates for trainees: a desk view is never "
           "'the analyst said so' — it's readings, reasoning, and a "
           "kill-switch, in that order. Anything the analyst drafts "
           "goes through the same Notebook discipline as your own "
           "calls. Positioning grammar only; single names are banned "
           "on purpose — ideas live at the factor level, vehicles come "
           "later.")
