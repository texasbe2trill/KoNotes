"""Share link builders — generate intent/compose URLs for social platforms.

Currently supports Bluesky via its compose-intent URL.  No external API
calls are made; the browser handles the actual posting.
"""
from __future__ import annotations

from urllib.parse import quote


def build_bluesky_share_url(text: str) -> str:
    """Return a Bluesky compose-intent URL with *text* pre-filled."""
    return f"https://bsky.app/intent/compose?text={quote(text, safe='')}"
