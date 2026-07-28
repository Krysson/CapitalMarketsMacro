"""Publisher for Notebook entries — the desk's public record.

Mirrors a real desk: the scratchpad is private by default, and
PUBLISHING is a deliberate act. A published entry is committed to the
repo's `data` branch (never main — no redeploy, no Notebook wipe) as a
markdown file under notebook/. The commit timestamp is the receipt:
the call is dated before the outcome, and the git history is the
audit trail. Post-mortem grades are mirrored to the same file — once a
call is on the record, its reckoning belongs there too.

Requires a fine-grained GitHub personal access token in the app's
Streamlit secrets as GH_TOKEN, scoped to ONLY this repo with
Contents: Read and write (setup steps in the README). Everything
fails soft: no token, no data branch yet, or no network simply
disables publishing — the local scratchpad is never affected.

PRIVACY: files on a public repo are public the moment they land.
That is the point of the record — publish only what you would stake
your name on.
"""
from __future__ import annotations

import base64
import re

import requests
import streamlit as st

from desk.history import OWNER, REPO

_API = "https://api.github.com"
BRANCH = "data"


def _token() -> str | None:
    try:
        if "GH_TOKEN" in st.secrets:
            return str(st.secrets["GH_TOKEN"]).strip()
    except Exception:
        pass
    return None


def enabled() -> bool:
    """Publishing is live only when both one-time setups are done."""
    return OWNER != "OWNER" and _token() is not None


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def slugify(text: str, fallback: str = "entry") -> str:
    """Filename-safe slug from the decision line. Pure."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:40].rstrip("-") or fallback)


def entry_markdown(e: dict) -> str:
    """Render one entry as the published markdown file. Pure."""
    lines = [
        f"# Analyst's Notebook — {e.get('date', '')}",
        "",
        "*Published from the Capital Markets Desk at save time. This "
        "file's git history is the audit trail: the commit timestamp "
        "is the receipt — the call is dated before the outcome.*",
        "",
        f"**Call:** {e.get('call', 'No call')} · "
        f"**Instrument:** {e.get('instrument', '^GSPC')}",
        "",
    ]
    for field, title in (("evidence", "Evidence"),
                         ("interpretation", "Interpretation"),
                         ("risks", "Risks"),
                         ("falsification", "Falsification"),
                         ("decision", "Decision")):
        lines += [f"## {title}", "", e.get(field, "") or "*(blank)*", ""]
    grade = e.get("grade")
    if grade and grade != "ungraded":
        lines += ["## Post-Mortem", "",
                  f"**Grade:** {grade}", "",
                  "*Direction is graded by the machine; reasoning only "
                  "by the author. This section was added when the entry "
                  "was graded — the commit history shows when.*", ""]
    return "\n".join(lines)


def _get_sha(path: str) -> str | None:
    """Blob sha if the file already exists on the data branch."""
    try:
        r = requests.get(f"{_API}/repos/{OWNER}/{REPO}/contents/{path}",
                         params={"ref": BRANCH}, headers=_headers(),
                         timeout=15)
        if r.ok:
            return r.json().get("sha")
    except Exception:
        pass
    return None


def _put(path: str, content: str, message: str,
         sha: str | None = None) -> tuple[bool, str]:
    """Create or update one file on the data branch via the contents
    API. Returns (ok, detail) — detail is the html_url on success, a
    human-readable reason on failure. Never raises."""
    body = {"message": message, "branch": BRANCH,
            "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(f"{_API}/repos/{OWNER}/{REPO}/contents/{path}",
                         json=body, headers=_headers(), timeout=20)
        if r.ok:
            return True, (r.json().get("content", {}) or {}).get(
                "html_url", "")
        if r.status_code == 404:
            return False, ("GitHub said 404 — check the GH_TOKEN is "
                           "scoped to this repo with Contents: Read "
                           "and write.")
        if r.status_code == 422 and "branch" in r.text.lower():
            return False, (f"the `{BRANCH}` branch doesn't exist yet — "
                           "run the Nightly signal snapshot workflow "
                           "once first (it creates the branch).")
        if r.status_code == 422:
            return False, ("file already exists with different "
                           "history — try again (sha refresh).")
        if r.status_code in (401, 403):
            return False, "token rejected — check GH_TOKEN in app secrets."
        return False, f"GitHub returned {r.status_code}."
    except Exception as ex:
        return False, f"network error ({type(ex).__name__})."


def publish_entry(e: dict) -> tuple[bool, str, str]:
    """Publish a new entry. Returns (ok, path, detail). Picks a
    non-colliding filename; never overwrites a different entry."""
    if not enabled():
        return False, "", "publishing not configured (see README)."
    base = f"notebook/{e.get('date', 'undated')}_{slugify(e.get('decision', ''))}"
    path = base + ".md"
    n = 2
    while _get_sha(path) is not None and n < 10:  # same-day collision
        path = f"{base}-{n}.md"
        n += 1
    ok, detail = _put(path, entry_markdown(e),
                      f"notebook: {e.get('date', '')} entry")
    if ok:
        published_files.clear()  # refresh the record list
    return ok, (path if ok else ""), detail


def republish_entry(e: dict) -> tuple[bool, str]:
    """Update an already-published entry in place (post-mortem mirror).
    The git history preserves every prior version — an edit is itself
    on the record."""
    path = e.get("published_path")
    if not path:
        return False, "entry has no published path."
    if not enabled():
        return False, "publishing not configured."
    sha = _get_sha(path)
    if sha is None:
        return False, "published file not found on the data branch."
    ok, detail = _put(path, entry_markdown(e),
                      f"notebook: post-mortem for {e.get('date', '')}", sha)
    if ok:
        published_files.clear()
    return ok, detail


@st.cache_data(ttl=900, show_spinner=False)
def publish_file(path: str, content: str, msg: str) -> tuple[bool, str]:
    """Generic publisher (v4.4) — morning reads live at reads/."""
    if not enabled():
        return False, "publishing not configured (see README)."
    return _put(path, content, msg, _get_sha(path))


def published_files() -> list[dict]:
    """The public record's file list (name + link), newest first.
    [] before anything is published or on any failure."""
    try:
        r = requests.get(
            f"{_API}/repos/{OWNER}/{REPO}/contents/notebook",
            params={"ref": BRANCH}, headers=_headers(), timeout=15)
        if not r.ok:
            return []
        out = [{"name": f.get("name", ""), "url": f.get("html_url", "")}
               for f in r.json() if f.get("type") == "file"]
        return sorted(out, key=lambda x: x["name"], reverse=True)
    except Exception:
        return []
