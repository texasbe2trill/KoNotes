"""Per-book detail view with annotations, filter, search, and Markdown export."""
from __future__ import annotations

import re
from typing import Callable

import streamlit as st

from models.annotation import Annotation
from models.book import Book
from services.export_markdown import export_book_markdown

_PAGE_SIZE = 20


def render_book_detail(book: Book, navigate: Callable[..., None]) -> None:
    # --- Back button ---
    if st.button("← Back to library"):
        navigate("library")
        st.rerun()

    # --- Header ---
    st.markdown(f"# {book.title}")
    if book.author:
        st.caption(f"by {book.author}")

    h_count = sum(1 for a in book.annotations if a.kind == "highlight")
    n_count = sum(1 for a in book.annotations if a.kind == "note")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Highlights", h_count)
    c2.metric("Notes", n_count)
    c3.metric("Total", len(book.annotations))
    c4.download_button(
        label="⬇ Export Markdown",
        data=export_book_markdown(book).encode("utf-8"),
        file_name=f"{_safe_filename(book.title)}_konotes.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.divider()

    # --- Filters ---
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        search = st.text_input(
            "Search annotations",
            placeholder="Search text…",
            key=f"bd_search_{book.id}",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=["All", "Highlights", "Notes", "Other"],
            key=f"bd_filter_{book.id}",
        )

    filtered = _apply_filters(book.annotations, kind_filter, search)

    if not filtered:
        st.info("No annotations match the current filter.")
        return

    st.caption(f"Showing {len(filtered)} annotation(s)")

    # --- Pagination ---
    page_key = f"bd_page_{book.id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = st.session_state[page_key]
    page = min(page, total_pages - 1)
    page_items = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    # --- Annotation cards ---
    current_chapter: str | None = None
    for ann in page_items:
        # Chapter subheading when it changes
        if ann.chapter and ann.chapter != current_chapter:
            current_chapter = ann.chapter
            st.markdown(f"#### {current_chapter}")

        with st.container(border=True):
            badge = _kind_badge(ann.kind)
            meta_parts = [badge]
            if ann.location:
                meta_parts.append(f"📍 {ann.location}")
            if ann.created_at:
                meta_parts.append(ann.created_at.strftime("%Y-%m-%d"))
            st.caption(" · ".join(meta_parts))

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
                f"<div style='text-align:center; padding-top:0.4rem;'>"
                f"Page {page + 1} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next →", disabled=page >= total_pages - 1, key=f"bd_next_{book.id}"):
                st.session_state[page_key] = page + 1
                st.rerun()


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
    elif kind_filter == "Other":
        result = [a for a in result if a.kind == "unknown"]
    if search.strip():
        q = search.lower()
        result = [a for a in result if q in a.text.lower()]
    return result


def _kind_badge(kind: str) -> str:
    return {"highlight": "🟡 Highlight", "note": "🔵 Note"}.get(kind, "⚪ Annotation")


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:60]
