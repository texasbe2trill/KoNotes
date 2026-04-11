"""All-annotations view — cross-book search, filter, and paginated list."""
from __future__ import annotations

import streamlit as st

from models.annotation import Annotation
from models.book import Book

_PAGE_SIZE = 25


def render_annotations(books: list[Book]) -> None:
    st.markdown("## 🔍 All Annotations")

    all_annotations: list[tuple[Annotation, str]] = [
        (ann, book.title) for book in books for ann in book.annotations
    ]

    if not all_annotations:
        st.info("No annotations loaded yet.")
        return

    # --- Filters ---
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        query = st.text_input(
            "Search annotation text",
            placeholder="Search…",
            key="ann_search",
        )
    with fc2:
        kind_filter = st.selectbox(
            "Type",
            options=["All", "Highlights", "Notes", "Other"],
            key="ann_kind",
        )
    with fc3:
        book_titles = sorted({b.title for b in books})
        book_filter = st.selectbox(
            "Book",
            options=["All books"] + book_titles,
            key="ann_book",
        )

    filtered = _apply_filters(all_annotations, query, kind_filter, book_filter)
    st.caption(f"Showing {len(filtered)} of {len(all_annotations)} annotation(s)")
    st.divider()

    # --- Pagination ---
    page_key = "ann_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(st.session_state[page_key], total_pages - 1)
    page_items = filtered[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]

    # --- Render ---
    for ann, book_title in page_items:
        with st.container(border=True):
            badge = _kind_badge(ann.kind)
            meta = f"{badge} · **{book_title}**"
            if ann.chapter:
                meta += f" · *{ann.chapter}*"
            if ann.location:
                meta += f" · 📍 {ann.location}"
            st.markdown(meta)

            if ann.kind == "highlight":
                st.markdown(f"> {ann.text}")
            else:
                st.markdown(ann.text)

            if ann.created_at:
                st.caption(ann.created_at.strftime("%Y-%m-%d"))

    # --- Pagination controls ---
    if total_pages > 1:
        st.markdown("")
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("← Previous", disabled=page == 0, key="ann_prev"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with p2:
            st.markdown(
                f"<div style='text-align:center; padding-top:0.4rem;'>"
                f"Page {page + 1} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next →", disabled=page >= total_pages - 1, key="ann_next"):
                st.session_state[page_key] = page + 1
                st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_filters(
    items: list[tuple[Annotation, str]],
    query: str,
    kind_filter: str,
    book_filter: str,
) -> list[tuple[Annotation, str]]:
    result = items
    if book_filter != "All books":
        result = [(a, t) for a, t in result if t == book_filter]
    if kind_filter == "Highlights":
        result = [(a, t) for a, t in result if a.kind == "highlight"]
    elif kind_filter == "Notes":
        result = [(a, t) for a, t in result if a.kind == "note"]
    elif kind_filter == "Other":
        result = [(a, t) for a, t in result if a.kind == "unknown"]
    if query.strip():
        q = query.lower()
        result = [(a, t) for a, t in result if q in a.text.lower()]
    return result


def _kind_badge(kind: str) -> str:
    return {"highlight": "🟡 Highlight", "note": "🔵 Note"}.get(kind, "⚪ Annotation")
