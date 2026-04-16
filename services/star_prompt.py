"""Tasteful star-prompt helpers for CLI and Streamlit.

All star/attribution prompts are centralised here so the rest of the
codebase stays clean.  The helpers are intentionally lightweight:

* **CLI**: ``maybe_show_cli_star_prompt()`` prints a one-time Rich
  console nudge after meaningful data has been processed.  It persists
  a tiny marker file so the user only ever sees it once.
* **Streamlit**: ``maybe_show_streamlit_star_prompt()`` renders a
  one-time ``st.info`` after data is visible in the session.
* **Export**: ``STAR_LINE`` / ``STAR_LINE_HTML`` provide a single-line
  attribution string for re-use across export formats.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_URL = "https://github.com/texasbe2trill/KoNotes"

STAR_LINE = (
    "If this was useful, consider starring KoNotes: "
    "https://github.com/texasbe2trill/KoNotes"
)

STAR_LINE_HTML = (
    'If this was useful, consider starring '
    '<a href="https://github.com/texasbe2trill/KoNotes">KoNotes</a> on GitHub.'
)

# ---------------------------------------------------------------------------
# Persistent "seen" tracking  (one tiny dot-file in ~/.config/konotes)
# ---------------------------------------------------------------------------

_STATE_DIR = Path(os.environ.get("KONOTES_STATE_DIR", ""))
if not _STATE_DIR.is_absolute():
    _STATE_DIR = Path.home() / ".config" / "konotes"

_CLI_SEEN_FILE = _STATE_DIR / ".star_prompt_seen"


def _mark_cli_seen() -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _CLI_SEEN_FILE.write_text("1")
    except OSError:
        pass  # best-effort


def _cli_already_seen() -> bool:
    return _CLI_SEEN_FILE.exists()


# ---------------------------------------------------------------------------
# CLI prompt
# ---------------------------------------------------------------------------

def maybe_show_cli_star_prompt(*, item_count: int = 0) -> None:
    """Print a one-time star nudge on the CLI after a successful run.

    Parameters
    ----------
    item_count:
        Number of meaningful items processed (books, annotations, etc.).
        The prompt is suppressed when this is zero.
    """
    if item_count <= 0:
        return
    if _cli_already_seen():
        return

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print()
    console.print(
        Panel(
            "[dim]Enjoying KoNotes?[/dim]\n\n"
            "If this surfaced something meaningful from your reading,\n"
            "consider starring the repo — it helps others find it.\n\n"
            f"[link={REPO_URL}]{REPO_URL}[/link]",
            border_style="dim",
            expand=False,
            padding=(1, 2),
        )
    )
    _mark_cli_seen()


# ---------------------------------------------------------------------------
# Streamlit prompt
# ---------------------------------------------------------------------------

def maybe_show_streamlit_star_prompt() -> None:
    """Render a one-per-session star nudge in the Streamlit UI.

    Call this **after** meaningful data (books / insights) has been
    rendered so the user has already seen value.  The nudge uses
    ``st.session_state`` to avoid repeating within the same session.
    """
    import streamlit as st

    if st.session_state.get("_star_prompt_shown"):
        return

    st.session_state["_star_prompt_shown"] = True

    st.markdown("")
    st.info(
        "**Enjoying KoNotes?**  \n"
        "If this helped you rediscover something from your reading, "
        "consider starring the project on GitHub — it helps others find it.  \n\n"
        f"[⭐ Star on GitHub]({REPO_URL})",
        icon="⭐",
    )
