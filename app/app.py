"""KoNotes Streamlit application.

Entry point: run with ``streamlit run app/app.py``
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so sibling-package imports work
# regardless of how Streamlit is launched.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from models.book import Book
from parser.export_parsers import get_parser_for_extension
from parser.normalizer import normalize
from parser.sqlite_parser import parse_sqlite
from services.stats import compute_stats

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KoNotes",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

if "books" not in st.session_state:
    st.session_state["books"] = []
if "view" not in st.session_state:
    st.session_state["view"] = "welcome"  # welcome | library | book_detail
if "selected_book_id" not in st.session_state:
    st.session_state["selected_book_id"] = None

# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _go_to(view: str, book_id: str | None = None) -> None:
    st.session_state["view"] = view
    st.session_state["selected_book_id"] = book_id

# ---------------------------------------------------------------------------
# Sidebar — file upload & processing
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 📖 KoNotes")
    st.caption("Turn your Kobo highlights and reading data into structured, readable insight.")
    st.divider()

    uploaded_exports = st.file_uploader(
        "Upload annotation exports",
        type=["html", "htm", "txt", "md", "markdown"],
        accept_multiple_files=True,
        help="Kobo export files: HTML, TXT, or Markdown.",
    )

    uploaded_sqlite = st.file_uploader(
        "Upload KoboReader.sqlite (optional)",
        type=["sqlite", "sqlite3", "db"],
        help="Found on your Kobo device at .kobo/KoboReader.sqlite",
    )

    has_files = bool(uploaded_exports) or uploaded_sqlite is not None
    process_btn = st.button(
        "Load annotations",
        type="primary",
        use_container_width=True,
        disabled=not has_files,
    )

    if process_btn and has_files:
        all_books: list[Book] = []
        errors: list[str] = []

        # --- Export files ---
        for f in uploaded_exports or []:
            ext = Path(f.name).suffix.lower()
            parser = get_parser_for_extension(ext)
            if parser is None:
                errors.append(f"Unsupported file type: {f.name}")
                continue
            try:
                content = f.read().decode("utf-8", errors="replace")
                raw = parser.parse(content)
                books = normalize(raw, source=parser.source_name)
                all_books.extend(books)
            except Exception as exc:
                errors.append(f"Error parsing {f.name}: {exc}")

        # --- SQLite ---
        if uploaded_sqlite is not None:
            tmp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
                    tmp.write(uploaded_sqlite.read())
                    tmp_path = Path(tmp.name)
                raw = parse_sqlite(tmp_path)
                books = normalize(raw, source="kobo_sqlite")
                all_books.extend(books)
            except Exception as exc:
                errors.append(f"Error parsing KoboReader.sqlite: {exc}")
            finally:
                if tmp_path is not None:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        # Merge books with the same id
        merged: dict[str, Book] = {}
        for book in all_books:
            if book.id in merged:
                existing = merged[book.id]
                existing_ids = {a.id for a in existing.annotations}
                for ann in book.annotations:
                    if ann.id not in existing_ids:
                        existing.annotations.append(ann)
            else:
                merged[book.id] = book

        st.session_state["books"] = list(merged.values())

        for err in errors:
            st.error(err)

        if merged:
            total_ann = sum(len(b.annotations) for b in merged.values())
            st.success(f"Loaded **{len(merged)}** book(s), **{total_ann}** annotation(s).")
            _go_to("library")
            st.rerun()
        elif not errors:
            st.warning("No annotations found in the uploaded file(s).")

    # Show library nav when data is loaded
    if st.session_state["books"]:
        st.divider()
        if st.button("📚  Library", use_container_width=True):
            _go_to("library")
            st.rerun()
        if st.button("🔍  All Annotations", use_container_width=True):
            _go_to("annotations")
            st.rerun()

    st.divider()
    st.caption("v0.1.0 · Phase 1 MVP")

# ---------------------------------------------------------------------------
# Main area — view routing
# ---------------------------------------------------------------------------

books: list[Book] = st.session_state.get("books", [])
view: str = st.session_state.get("view", "welcome")

# ---------------------------------------------------------------------------
# Welcome view
# ---------------------------------------------------------------------------
if not books or view == "welcome":
    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 0 0.5rem 0;">
            <h1 style="font-size:2.6rem; margin-bottom:0.2rem;">📖 KoNotes</h1>
            <p style="font-size:1.15rem; color:#777; margin-top:0;">
                Turn your Kobo highlights and reading data into structured, readable insight.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.markdown("### Getting started")
        st.markdown(
            """
1. **Export annotations** from the Kobo app  
   *Library → Book → ⋯ → Export annotations*
2. **Upload** the file(s) using the sidebar
3. Optionally add your `KoboReader.sqlite`  
   *(found on-device at `.kobo/KoboReader.sqlite`)*
4. Click **Load annotations**
            """
        )

    with col_r:
        st.markdown("### Supported formats")
        st.markdown(
            """
| Format | Extension |
|--------|-----------|
| Kobo HTML export | `.html` |
| Kobo plain-text export | `.txt` |
| Kobo Markdown export | `.md` |
| KoboReader SQLite | `.sqlite` |
            """
        )

    st.divider()
    st.markdown(
        '<p style="text-align:center; color:#999; font-size:0.85rem;">'
        "Upload a file in the sidebar to get started.</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Library view
# ---------------------------------------------------------------------------
elif view == "library":
    from app.pages.library import render_library
    render_library(books, navigate=_go_to)

# ---------------------------------------------------------------------------
# Book detail view
# ---------------------------------------------------------------------------
elif view == "book_detail":
    from app.pages.book_detail import render_book_detail

    selected_id = st.session_state.get("selected_book_id")
    selected_book = next((b for b in books if b.id == selected_id), None)
    if selected_book:
        render_book_detail(selected_book, navigate=_go_to)
    else:
        st.error("Book not found.")
        if st.button("← Back to library"):
            _go_to("library")
            st.rerun()

# ---------------------------------------------------------------------------
# All-annotations view
# ---------------------------------------------------------------------------
elif view == "annotations":
    from app.pages.annotations import render_annotations
    render_annotations(books)
