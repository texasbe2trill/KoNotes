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
from parser.device_detection import detect_devices
from parser.export_parsers import get_parser_for_extension
from parser.normalizer import normalize
from parser.sqlite_parser import parse_sqlite
from services.stats import compute_stats

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KoNotes",
    page_icon="KN",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load custom CSS
# ---------------------------------------------------------------------------

_ASSETS = Path(__file__).resolve().parent / "assets"
_CSS_FILE = _ASSETS / "styles.css"
if _CSS_FILE.exists():
    st.markdown(f"<style>{_CSS_FILE.read_text()}</style>", unsafe_allow_html=True)

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
    # --- Brand ---
    st.markdown(
        '<div style="text-align:center; padding: 0.2rem 0;">'
        '<span style="font-size:1.5rem; font-weight:800; letter-spacing:-0.02em;">'
        '<span style="color:#4a9eff;">Ko</span>Notes</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Turn your Kobo highlights into structured, readable insight.")
    st.divider()

    # --- Auto-detect connected Kobo device ---
    devices = detect_devices()
    if devices:
        dev = devices[0]
        st.markdown(
            f'<div style="padding:0.5rem 0.75rem; border-radius:8px; border:1px solid rgba(74,158,255,0.2); '
            f'background:rgba(74,158,255,0.06); margin-bottom:0.5rem;">'
            f'<div style="font-weight:600; font-size:0.9rem;">Kobo device detected</div>'
            f'<div style="font-size:0.78rem; color:#888; margin-top:2px;">{dev.label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Consent gate — user must explicitly confirm before reading device data
        consent_key = "device_consent"
        if consent_key not in st.session_state:
            st.session_state[consent_key] = False

        if not st.session_state[consent_key]:
            st.markdown(
                '<div style="font-size:0.85rem; padding:0.3rem 0;">'
                'Do you want to read local data from this device?</div>',
                unsafe_allow_html=True,
            )
            c_yes, c_no = st.columns(2)
            if c_yes.button("Yes, load data", type="primary", use_container_width=True, key="consent_yes"):
                st.session_state[consent_key] = True
                st.rerun()
            if c_no.button("No", use_container_width=True, key="consent_no"):
                st.session_state[consent_key] = False
        else:
            # Consent given — auto-load on first detection
            if not st.session_state["books"] and "device_loaded" not in st.session_state:
                st.session_state["device_loaded"] = True
                try:
                    raw = parse_sqlite(dev.db_path)
                    device_books = normalize(raw, source="kobo_sqlite")
                    if device_books:
                        st.session_state["books"] = device_books
                        _go_to("library")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Error reading device: {exc}")

            if st.button("Reload from device", use_container_width=True, key="load_device"):
                try:
                    raw = parse_sqlite(dev.db_path)
                    device_books = normalize(raw, source="kobo_sqlite")
                    if device_books:
                        st.session_state["books"] = device_books
                        total_ann = sum(len(b.annotations) for b in device_books)
                        st.toast(f"Loaded {len(device_books)} book(s), {total_ann} annotations")
                        _go_to("library")
                        st.rerun()
                    else:
                        st.warning("No annotations found on device.")
                except Exception as exc:
                    st.error(f"Error reading device: {exc}")
        st.divider()

    # --- Manual upload ---
    with st.expander("Upload files manually", expanded=not bool(devices) and not st.session_state["books"]):
        uploaded_sqlite = st.file_uploader(
            "KoboReader.sqlite",
            type=["sqlite", "sqlite3", "db"],
            help="Found on your Kobo device at .kobo/KoboReader.sqlite",
        )

        uploaded_exports = st.file_uploader(
            "Annotation exports",
            type=["html", "htm", "txt", "md", "markdown"],
            accept_multiple_files=True,
            help="HTML, TXT, or Markdown annotation exports.",
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
                st.toast(f"Loaded {len(merged)} book(s), {total_ann} annotations")
                _go_to("library")
                st.rerun()
            elif not errors:
                st.warning("No annotations found in the uploaded file(s).")

    # --- Navigation links ---
    if st.session_state["books"]:
        st.divider()
        current_view = st.session_state.get("view", "welcome")

        # Library nav
        lib_style = (
            "background:rgba(74,158,255,0.12); border-left:3px solid #4a9eff; font-weight:600;"
            if current_view == "library"
            else "border-left:3px solid transparent;"
        )
        if st.button("Library", use_container_width=True, key="nav_library"):
            _go_to("library")
            st.rerun()

        # Annotations nav
        ann_style = (
            "background:rgba(74,158,255,0.12); border-left:3px solid #4a9eff; font-weight:600;"
            if current_view == "annotations"
            else "border-left:3px solid transparent;"
        )
        if st.button("All Annotations", use_container_width=True, key="nav_annotations"):
            _go_to("annotations")
            st.rerun()

        # Quick stats in sidebar
        total_books = len(st.session_state["books"])
        total_ann = sum(len(b.annotations) for b in st.session_state["books"])
        st.markdown(
            f'<div style="padding:0.6rem 0; font-size:0.78rem; color:#888;">'
            f'{total_books} book(s) · {total_ann} annotations loaded</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        '<div style="text-align:center; font-size:0.72rem; color:#666;">v0.2.0</div>',
        unsafe_allow_html=True,
    )

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
        '<div class="kn-hero">'
        '<h1>KoNotes</h1>'
        '<p>Turn your Kobo highlights into structured, readable insight.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # --- Step cards ---
    s1, s2, s3 = st.columns(3, gap="medium")
    with s1:
        st.markdown(
            '<div class="kn-step">'
            '<div class="kn-step-num">1</div>'
            '<h4>Connect</h4>'
            '<p>Plug in your Kobo via USB. KoNotes detects it automatically.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            '<div class="kn-step">'
            '<div class="kn-step-num">2</div>'
            '<h4>Parse</h4>'
            '<p>Annotations are extracted from the SQLite database — '
            'or upload HTML/TXT/MD exports.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            '<div class="kn-step">'
            '<div class="kn-step-num">3</div>'
            '<h4>Export</h4>'
            '<p>Browse your library, search across books, and export as '
            'Markdown, JSON, or plain text.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.divider()

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("##### Supported formats")
        st.markdown(
            "| Format | Extension | Priority |\n"
            "|--------|-----------|----------|\n"
            "| KoboReader SQLite | `.sqlite` | **Primary** |\n"
            "| HTML export | `.html` | Secondary |\n"
            "| Plain-text export | `.txt` | Secondary |\n"
            "| Markdown export | `.md` | Secondary |"
        )
    with c2:
        st.markdown("##### How it works")
        st.markdown(
            "- **Fully local** — nothing leaves your machine\n"
            "- **Read-only** — your Kobo data is never modified\n"
            "- **Smart dedup** — annotations merged across sources\n"
            "- **Chapter names** — cleaned from raw Kobo IDs\n"
            "- **Rich metadata** — shelves, progress, publisher, ISBN"
        )

    st.markdown(
        '<div class="kn-footer">'
        'Connect your Kobo or upload a file in the sidebar to get started.'
        '</div>',
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
