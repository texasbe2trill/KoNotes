"""Per-book detail view with annotations, filter, search, and export."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable

import streamlit as st

from models.annotation import Annotation
from models.book import Book
from services.export_json import export_book_json
from services.export_markdown import export_book_markdown
from services.export_text import export_book_text

_PAGE_SIZE = 20


def render_book_detail(book: Book, navigate: Callable[..., None]) -> None:
    # --- Back button ---
    if st.button("← Library", key="bd_back"):
        navigate("library")
        st.rerun()

    # --- Header ---
    st.markdown(f"## {book.title}")
    meta_parts: list[str] = []
    if book.author:
        meta_parts.append(f"by **{book.author}**")
    if book.publisher:
        meta_parts.append(book.publisher)
    if book.language:
        meta_parts.append(book.language.upper())
    if meta_parts:
        st.markdown(" · ".join(meta_parts))

    h_count = sum(1 for a in book.annotations if a.kind == "highlight")
    n_count = sum(1 for a in book.annotations if a.kind == "note")

    # --- Stats + Export row ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Highlights", h_count)
    c2.metric("Notes", n_count)
    if book.read_percent is not None:
        c3.metric("Progress", f"{book.read_percent:.0f}%")
    else:
        c3.metric("Total", len(book.annotations))

    # Export buttons
    st.markdown("")
    e1, e2, e3, e4 = st.columns([1, 1, 1, 3])
    e1.download_button(
        label="Markdown",
        data=export_book_markdown(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.md",
        mime="text/markdown",
        use_container_width=True,
    )
    e2.download_button(
        label="JSON",
        data=export_book_json(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.json",
        mime="application/json",
        use_container_width=True,
    )
    e3.download_button(
        label="Plain Text",
        data=export_book_text(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()

    # --- Filters ---
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        search = st.text_input(
            "Search annotations",
            placeholder="Search text...",
            key=f"bd_search_{book.id}",
            label_visibility="collapsed",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=["All", "Highlights", "Notes"],
            key=f"bd_filter_{book.id}",
            label_visibility="collapsed",
        )

    # Sort by timestamp
    _sentinel = datetime(1970, 1, 1)
    sorted_anns = sorted(book.annotations, key=lambda a: a.created_at or _sentinel)
    filtered = _apply_filters(sorted_anns, kind_filter, search)

    if not filtered:
        st.info("No annotations match the current filter.")
        return

    st.caption(f"{len(filtered)} annotation(s)")

    # --- Pagination ---
    page_key = f"bd_page_{book.id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(st.session_state[page_key], total_pages - 1)
    page_items = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    # --- Annotation cards ---
    current_chapter: str | None = None
    for ann in page_items:
        if ann.chapter and ann.chapter != current_chapter:
            current_chapter = ann.chapter
            st.markdown(
                f'<div class="kn-chapter">{current_chapter}</div>',
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            # Badge + metadata line
            badge_class = {
                "highlight": "kn-badge-highlight",
                "note": "kn-badge-note",
            }.get(ann.kind, "kn-badge-other")
            badge_label = {"highlight": "Highlight", "note": "Note"}.get(ann.kind, "Annotation")

            meta_html = f'<span class="kn-badge {badge_class}">{badge_label}</span>'
            if ann.location:
                meta_html += f' <span style="font-size:0.78rem; color:#888;">Loc: {ann.location}</span>'
            if ann.created_at:
                meta_html += f' <span style="font-size:0.78rem; color:#888;">· {ann.created_at.strftime("%b %d, %Y")}</span>'
            st.markdown(meta_html, unsafe_allow_html=True)

            if ann.kind == "highlight":
                st.markdown(f"> {ann.text}")
            else:
                st.markdown(ann.text)

    # --- Pagination controls ---
    if total_pages > 1:
        st.markdown("")
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("← Previous", disabled=page == 0, key=f"bd_prev_{book.id}"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with p2:
            st.markdown(
                f'<div style="text-align:center; padding-top:0.4rem; font-size:0.85rem; color:#888;">'
                f'Page {page + 1} of {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next →", disabled=page >= total_pages - 1, key=f"bd_next_{book.id}"):
                st.session_state[page_key] = page + 1
                st.rerun()

    st.markdown(
        '<div class="kn-footer">Made with love for the Kobo community.</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_filters(
    annotations: list[Annotation], kind_filter: str, search: str
) -> list[Annotation]:
    result = annotations
    if kind_filter == "Highlights":
        result = [a for a in result if a.kind == "highlight"]
    elif kind_filter == "Notes":
        result = [a for a in result if a.kind == "note"]
    if search.strip():
        q = search.lower()
        result = [a for a in result if q in a.text.lower()]
    return result


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:60]
