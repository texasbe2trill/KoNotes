"""Reusable book-cover rendering component.

Renders either:
- a real cover image (local path or URL), or
- a clean initials placeholder when no cover is available.

``render_book_cover`` writes directly to Streamlit via st.markdown.
``cover_html_fragment`` returns a raw HTML string for embedding inside
larger HTML blocks (e.g. recommendation cards rendered via st.markdown).

Sizes use stable HTML class names defined in ``app/assets/styles.css``.
Cover resolution lives in ``services/book_covers.py``.
"""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from typing import Literal

import streamlit as st

from models.book import Book
from services.book_covers import (
    SOURCE_LOCAL,
    SOURCE_URL,
    CoverResult,
    resolve_book_cover,
)

CoverSize = Literal["small", "medium", "large"]

# Pixel widths used by ``st.image`` when rendering local paths.
_SIZE_PX: dict[str, int] = {
    "small": 56,
    "medium": 110,
    "large": 180,
}


def render_book_cover(
    book: Book | None,
    *,
    size: CoverSize = "small",
    cover: CoverResult | None = None,
) -> None:
    """Render a cover for *book* at the requested size.

    Real images are emitted as ``<img>`` tags so they participate in the
    same flex/CSS layout as the placeholder. When neither image nor book
    is available, this is a no-op.
    """
    if cover is None:
        if book is None:
            return
        cover = resolve_book_cover(book)

    if cover.source in (SOURCE_LOCAL, SOURCE_URL) and (cover.url or cover.path):
        src = cover.url or cover.path or ""
        # Local file paths are rendered through Streamlit's image helper to
        # benefit from caching; remote URLs go straight to <img>.
        if cover.source == SOURCE_LOCAL and cover.path:
            st.image(cover.path, width=_SIZE_PX[size])
            return
        _render_html(
            f'<img src="{escape(src)}" alt="{escape(cover.title)} cover" '
            f'class="kn-cover kn-cover--{size}" loading="lazy" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling&&'
            f'(this.nextElementSibling.style.display=\'flex\');" />'
            # Sibling fallback is rendered hidden; flipped on by the onerror handler.
            f'{_placeholder_html(cover, size, hidden=True)}'
        )
        return

    _render_html(_placeholder_html(cover, size))


def render_book_cover_with_fallback(book: Book | None, *, size: CoverSize = "small") -> None:
    """Alias kept for clarity at call sites — fallback is always handled."""
    render_book_cover(book, size=size)


def cover_html_fragment(
    book: Book | None,
    *,
    cover: CoverResult | None = None,
    fallback_title: str = "",
    css_class: str = "kn-rec-card-cover",
) -> str:
    """Return an HTML string for a book cover suitable for embedding inside a larger element.

    Unlike ``render_book_cover()``, this does **not** call ``st.markdown()`` —
    it returns a raw HTML fragment to be composed into a bigger block.

    - URL cover  → ``<img loading=lazy onerror=…>`` with hidden sibling placeholder
    - Local file → base64-encoded ``<img>`` (Streamlit can't serve arbitrary file paths)
    - Fallback   → gradient placeholder div with initials

    Parameters
    ----------
    book:
        Source book. When None, renders a placeholder from *fallback_title*.
    cover:
        Pre-resolved CoverResult. Resolved automatically when not supplied.
    fallback_title:
        Title to use for initials when *book* is None. Ignored when book is set.
    css_class:
        CSS class applied to the wrapper / image element. Default matches the
        recommendation card cover slot (.kn-rec-card-cover).
    """
    if cover is None:
        if book is not None:
            cover = resolve_book_cover(book)

    if cover is not None and cover.has_image:
        label = escape(cover.fallback_label)
        title_attr = escape(cover.title)

        if cover.url:
            # Remote / metadata URL — lazy load, onerror reveals sibling placeholder
            return (
                f'<img src="{escape(cover.url)}" alt="{title_attr}" '
                f'class="{css_class}__img" loading="lazy" '
                f'onerror="this.style.display=\'none\';'
                f'var s=this.nextElementSibling;if(s)s.style.display=\'flex\';">'
                f'<div class="{css_class}__placeholder" style="display:none;">'
                f'<span>{label}</span></div>'
            )

        if cover.path:
            try:
                data = Path(cover.path).read_bytes()
                b64 = base64.b64encode(data).decode()
                suffix = Path(cover.path).suffix.lower().lstrip(".")
                mime = "jpeg" if suffix in ("jpg", "jpeg") else (suffix or "jpeg")
                return (
                    f'<img src="data:image/{mime};base64,{b64}" '
                    f'alt="{title_attr}" class="{css_class}__img">'
                )
            except Exception:
                pass

    # Fallback placeholder — use pre-computed initials from the CoverResult
    # when available; otherwise derive from the fallback_title string.
    from services.book_covers import _initials  # noqa: PLC0415

    if cover is not None and cover.fallback_label:
        # Already two-char initials — use as-is.
        initials = cover.fallback_label
    else:
        initials = _initials(fallback_title)
    return (
        f'<div class="{css_class}__placeholder">'
        f'<span>{escape(initials)}</span>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _render_html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _placeholder_html(cover: CoverResult, size: str, *, hidden: bool = False) -> str:
    style = "display:none;" if hidden else ""
    return (
        f'<div class="kn-cover kn-cover--{size} kn-cover--placeholder" '
        f'style="{style}" title="{escape(cover.title)}">'
        f'<span class="kn-cover-initials">{escape(cover.fallback_label)}</span>'
        f'</div>'
    )
