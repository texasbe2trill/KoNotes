"""KoNotes Streamlit application.

Entry point: run with ``streamlit run app/app.py``
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Suppress noisy deprecation warnings from the ``transformers`` library's
# lazy import system (hundreds of "Accessing __path__" lines).
# ---------------------------------------------------------------------------
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so sibling-package imports work
# regardless of how Streamlit is launched.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from models.activity import ProgressSnapshot, ReadingSession
from models.book import Book
from parser.device_detection import detect_devices
from parser.kindle_parser import KindleClippingsParser, is_kindle_clippings
from parser.normalizer import normalize
from parser.sqlite_parser import (
    extract_page_turns,
    extract_progress_snapshots,
    extract_ratings,
    extract_reading_sessions,
    extract_shelves,
    extract_word_lookups,
    parse_sqlite,
)

# ---------------------------------------------------------------------------
# Page config — must be the FIRST Streamlit command.
# page_title controls the <title> tag used by link-preview crawlers
# (OpenGraph / Twitter Cards), so changing it here fixes how the app
# appears when shared on Bluesky, Slack, Discord, etc.
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="KoNotes",
    page_icon="📖",
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

# Visible app header — reinforces branding and provides the description
# that link-preview crawlers surface via the rendered HTML.
st.title("📖 KoNotes")
st.caption("Turn your Kobo & Kindle reading data into structured insight")

# ---------------------------------------------------------------------------
# Hosted demo mode flag (used for behavior only; no top-page banner)
# ---------------------------------------------------------------------------

_IS_HOSTED_DEMO = bool(os.environ.get("IS_HOSTED_DEMO"))

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "books": [],
    "view": "welcome",
    "selected_book_id": None,
    "sessions": [],
    "snapshots": [],
    "shelves": [],
    "word_lookups": [],
    "db_path": None,
    "using_demo": False,
    "data_source": "kobo",
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

_NAV_ITEMS = ["Overview", "Activity", "Insights", "Library", "Annotations", "Vocabulary", "Chat"]


def _go_to(view: str, book_id: str | None = None) -> None:
    st.session_state["view"] = view
    st.session_state["selected_book_id"] = book_id


import shutil


def _safe_device_copy(device_path: Path) -> Path:
    """Copy device SQLite to a temp file to avoid holding a lock on the mounted Kobo."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    tmp.close()
    shutil.copy2(device_path, tmp.name)
    return Path(tmp.name)


def _load_telemetry(db_path: Path) -> None:
    """Extract reading sessions, progress snapshots, shelves, vocabulary, and ratings from SQLite."""
    try:
        st.session_state["sessions"] = extract_reading_sessions(db_path)
    except Exception:
        st.session_state["sessions"] = []
    try:
        st.session_state["snapshots"] = extract_progress_snapshots(db_path)
    except Exception:
        st.session_state["snapshots"] = []
    try:
        st.session_state["shelves"] = extract_shelves(db_path)
    except Exception:
        st.session_state["shelves"] = []
    try:
        st.session_state["word_lookups"] = extract_word_lookups(db_path)
    except Exception:
        st.session_state["word_lookups"] = []
    # Enrich books with ratings and page turns
    try:
        ratings = extract_ratings(db_path)
        page_turns = extract_page_turns(db_path)
        if ratings or page_turns:
            # Build ContentID → book title lookup from SQLite
            cid_title: dict[str, tuple[str, str | None]] = {}
            try:
                uri = db_path.as_uri() + "?mode=ro"
                conn = sqlite3.connect(uri, uri=True)
                conn.row_factory = sqlite3.Row
                for row in conn.execute(
                    "SELECT ContentID, Title, Attribution FROM content WHERE ContentType = 6"
                ):
                    cid_title[row["ContentID"]] = (
                        row["Title"] or "Unknown Book",
                        row["Attribution"] or None,
                    )
                conn.close()
            except Exception:
                pass

            # Build title-based index into loaded books
            book_by_title: dict[str, Book] = {}
            for book in st.session_state.get("books", []):
                key = (book.title, book.author)
                book_by_title[str(key)] = book

            for cid, rating in ratings.items():
                info = cid_title.get(cid)
                if info:
                    key = str(info)
                    if key in book_by_title:
                        book_by_title[key].rating = rating

            for cid, turns in page_turns.items():
                info = cid_title.get(cid)
                if info:
                    key = str(info)
                    if key in book_by_title:
                        book_by_title[key].page_turns = turns
    except Exception:
        pass
    st.session_state["db_path"] = db_path

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    # --- Brand ---
    st.markdown(
        '<div style="text-align:center; padding: 0.4rem 0 0.2rem;">'
        '<span style="font-size:1.5rem; font-weight:800; letter-spacing:-0.02em;">'
        '<span style="color:#3b82f6;">Ko</span>Notes</span>'
        '<div style="font-size:0.72rem; color:#666; margin-top:2px;">Reading Intelligence</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # --- Auto-detect connected Kobo device ---
    devices = detect_devices()
    if devices:
        dev = devices[0]
        st.markdown(
            f'<div style="padding:0.5rem 0.75rem; border-radius:8px; '
            f'border:1px solid rgba(16,185,129,0.2); '
            f'background:rgba(16,185,129,0.04); margin-bottom:0.5rem;">'
            f'<div style="font-weight:600; font-size:0.85rem; color:#10b981;">'
            f'Kobo Connected</div>'
            f'<div style="font-size:0.75rem; color:#888; margin-top:2px;">{dev.label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        consent_key = "device_consent"
        if consent_key not in st.session_state:
            st.session_state[consent_key] = False

        if not st.session_state[consent_key]:
            st.markdown(
                '<div style="font-size:0.85rem; padding:0.3rem 0;">'
                'Read local data from this device?</div>',
                unsafe_allow_html=True,
            )
            c_yes, c_no = st.columns(2)
            if c_yes.button("Yes, load data", type="primary", width="stretch", key="consent_yes"):
                st.session_state[consent_key] = True
                st.rerun()
            if c_no.button("No", width="stretch", key="consent_no"):
                st.session_state[consent_key] = False
        else:
            if not st.session_state["books"] and "device_loaded" not in st.session_state:
                st.session_state["device_loaded"] = True
                tmp_path: Path | None = None
                try:
                    tmp_path = _safe_device_copy(dev.db_path)
                    raw = parse_sqlite(tmp_path)
                    device_books = normalize(raw, source="kobo_sqlite")
                    if device_books:
                        st.session_state["books"] = device_books
                        st.session_state["using_demo"] = False
                        st.session_state["data_source"] = "kobo"
                        _load_telemetry(tmp_path)
                        _go_to("overview")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Error reading device: {exc}")
                finally:
                    if tmp_path is not None:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

            if st.button("Reload from device", width="stretch", key="load_device"):
                tmp_path_reload: Path | None = None
                try:
                    tmp_path_reload = _safe_device_copy(dev.db_path)
                    raw = parse_sqlite(tmp_path_reload)
                    device_books = normalize(raw, source="kobo_sqlite")
                    if device_books:
                        st.session_state["books"] = device_books
                        st.session_state["using_demo"] = False
                        st.session_state["data_source"] = "kobo"
                        _load_telemetry(tmp_path_reload)
                        total_ann = sum(len(b.annotations) for b in device_books)
                        st.toast(f"Loaded {len(device_books)} book(s), {total_ann} annotations")
                        _go_to("overview")
                        st.rerun()
                    else:
                        st.warning("No annotations found on device.")
                except Exception as exc:
                    st.error(f"Error reading device: {exc}")
                finally:
                    if tmp_path_reload is not None:
                        try:
                            os.unlink(tmp_path_reload)
                        except OSError:
                            pass
        st.divider()

    # --- Manual upload ---
    with st.expander("Upload file", expanded=not bool(devices) and not st.session_state["books"]):
        upload_tab_kobo, upload_tab_kindle = st.tabs(["Kobo", "Kindle"])

        # ---- Kobo SQLite upload ----
        with upload_tab_kobo:
            uploaded_sqlite = st.file_uploader(
                "KoboReader.sqlite",
                type=["sqlite", "sqlite3", "db"],
                help="Found on your Kobo at .kobo/KoboReader.sqlite",
            )
            kobo_btn = st.button(
                "Load annotations",
                type="primary",
                width="stretch",
                disabled=uploaded_sqlite is None,
                key="load_kobo",
            )

            if kobo_btn and uploaded_sqlite is not None:
                all_books: list[Book] = []
                errors: list[str] = []

                st.session_state["using_demo"] = False
                st.session_state["data_source"] = "kobo"
                tmp_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
                        tmp.write(uploaded_sqlite.read())
                        tmp_path = Path(tmp.name)
                    raw = parse_sqlite(tmp_path)
                    books = normalize(raw, source="kobo_sqlite")
                    all_books.extend(books)
                    _load_telemetry(tmp_path)
                except Exception as exc:
                    errors.append(f"Error parsing KoboReader.sqlite: {exc}")
                finally:
                    if tmp_path is not None:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

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
                    total_hl = sum(
                        sum(1 for a in b.annotations if a.kind == "highlight")
                        for b in merged.values()
                    )
                    st.toast(
                        f"✅ Loaded {len(merged)} book(s) — "
                        f"{total_hl} highlights, {total_ann - total_hl} notes",
                        icon="📚",
                    )
                    _go_to("overview")
                    st.rerun()
                elif not errors:
                    st.warning("No annotations found in the uploaded file(s).")

        # ---- Kindle My Clippings.txt upload ----
        with upload_tab_kindle:
            uploaded_kindle = st.file_uploader(
                "My Clippings.txt",
                type=["txt"],
                help="Found at the root of your Kindle device",
                key="kindle_uploader",
            )
            kindle_btn = st.button(
                "Load clippings",
                type="primary",
                width="stretch",
                disabled=uploaded_kindle is None,
                key="load_kindle",
            )

            if kindle_btn and uploaded_kindle is not None:
                st.session_state["using_demo"] = False
                st.session_state["data_source"] = "kindle"
                content = uploaded_kindle.read().decode("utf-8", errors="replace")

                if not is_kindle_clippings(content):
                    st.error(
                        "This doesn't look like a Kindle My Clippings.txt file. "
                        "Expected `==========` separators and Kindle metadata lines."
                    )
                else:
                    try:
                        parser = KindleClippingsParser()
                        raw_kindle = parser.parse(content)
                        kindle_books = normalize(raw_kindle, source="kindle")

                        # Kindle has no telemetry — clear stale Kobo telemetry
                        st.session_state["sessions"] = []
                        st.session_state["snapshots"] = []
                        st.session_state["shelves"] = []
                        st.session_state["word_lookups"] = []
                        st.session_state["db_path"] = None

                        merged_k: dict[str, Book] = {}
                        for book in kindle_books:
                            if book.id in merged_k:
                                existing = merged_k[book.id]
                                existing_ids = {a.id for a in existing.annotations}
                                for ann in book.annotations:
                                    if ann.id not in existing_ids:
                                        existing.annotations.append(ann)
                            else:
                                merged_k[book.id] = book

                        st.session_state["books"] = list(merged_k.values())

                        if merged_k:
                            total_ann = sum(len(b.annotations) for b in merged_k.values())
                            total_hl = sum(
                                sum(1 for a in b.annotations if a.kind == "highlight")
                                for b in merged_k.values()
                            )
                            st.toast(
                                f"✅ Loaded {len(merged_k)} book(s) — "
                                f"{total_hl} highlights, {total_ann - total_hl} notes",
                                icon="📚",
                            )
                            _go_to("overview")
                            st.rerun()
                        else:
                            st.warning("No annotations found in the clippings file.")
                    except Exception as exc:
                        st.error(f"Error parsing Kindle clippings: {exc}")

    # --- Navigation ---
    if st.session_state["books"]:
        st.divider()

        # Build nav items dynamically based on data source
        _is_kindle = st.session_state.get("data_source") == "kindle"
        _active_nav = [n for n in _NAV_ITEMS if not (_is_kindle and n == "Vocabulary")]

        # Map current view to radio index
        current_view = st.session_state.get("view", "welcome")
        _view_to_nav = {
            "overview": "Overview",
            "library": "Library",
            "annotations": "Annotations",
            "activity": "Activity",
            "vocabulary": "Vocabulary",
            "insights": "Insights",
            "chat": "Chat",
        }
        current_nav = _view_to_nav.get(current_view, "Overview")
        current_idx = _active_nav.index(current_nav) if current_nav in _active_nav else 0

        selected_nav = st.radio(
            "Navigate",
            _active_nav,
            index=current_idx,
            label_visibility="collapsed",
            key="nav_radio",
        )

        # Sync radio selection to view state
        _nav_to_view = {
            "Overview": "overview",
            "Library": "library",
            "Annotations": "annotations",
            "Activity": "activity",
            "Vocabulary": "vocabulary",
            "Insights": "insights",
            "Chat": "chat",
        }
        new_view = _nav_to_view.get(selected_nav, "overview")
        if new_view != current_view and current_view != "book_detail":
            _go_to(new_view)
            st.rerun()

        # Quick library summary
        total_books = len(st.session_state["books"])
        total_ann = sum(len(b.annotations) for b in st.session_state["books"])
        total_hl = sum(
            sum(1 for a in b.annotations if a.kind == "highlight")
            for b in st.session_state["books"]
        )
        st.markdown(
            f'<div style="padding:0.5rem 0; font-size:0.75rem; color:#64748b; line-height:1.6;">'
            f'{total_books} books &middot; {total_ann} annotations &middot; {total_hl} highlights'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Export buttons
        with st.expander("Export"):
            if st.button("Export static HTML site", width="stretch", key="export_html"):
                from services.export_html import export_static_site
                from services.insight_feed import build_feed
                import tempfile

                export_books = st.session_state["books"]
                word_lookups = st.session_state.get("word_lookups", [])
                cards = build_feed(export_books, word_lookups=word_lookups)

                with tempfile.TemporaryDirectory() as tmp_dir:
                    export_static_site(
                        export_books, tmp_dir, insight_cards=cards,
                        sessions=st.session_state.get("sessions"),
                        snapshots=st.session_state.get("snapshots"),
                        word_lookups=word_lookups,
                    )
                    html_content = (Path(tmp_dir) / "index.html").read_text(encoding="utf-8")
                    st.download_button(
                        "Download site (.html)",
                        data=html_content,
                        file_name="konotes.html",
                        mime="text/html",
                        key="dl_html",
                    )

            if st.button("Export CSV", width="stretch", key="export_csv"):
                from services.export_csv import export_book_csv

                export_books = st.session_state["books"]
                csv_parts = [export_book_csv(b) for b in export_books]
                # Merge: keep header from first file, strip headers from rest
                merged_lines: list[str] = []
                for i, part in enumerate(csv_parts):
                    lines = part.splitlines(keepends=True)
                    if i == 0:
                        merged_lines.extend(lines)
                    else:
                        merged_lines.extend(lines[1:])  # skip header row
                csv_data = "".join(merged_lines)
                st.download_button(
                    "Download annotations (.csv)",
                    data=csv_data,
                    file_name="konotes_annotations.csv",
                    mime="text/csv",
                    key="dl_csv",
                )

    st.divider()
    st.markdown(
        '<div style="text-align:center; font-size:0.68rem; color:#475569;">v0.6.0</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main area -- view routing
# ---------------------------------------------------------------------------

books: list[Book] = st.session_state.get("books", [])
view: str = st.session_state.get("view", "welcome")

# Warm the cover cache in parallel once per library load. Runs in a
# background daemon thread so the first render is never blocked; covers
# materialize on the next rerun once lookups finish.
if books:
    _cover_sig = (len(books), st.session_state.get("data_source"))
    if st.session_state.get("_cover_prefetch_sig") != _cover_sig:
        from services.book_covers import prefetch_covers
        prefetch_covers(books)
        st.session_state["_cover_prefetch_sig"] = _cover_sig

# ---------------------------------------------------------------------------
# Demo switcher — shown on any view when viewing demo data
# ---------------------------------------------------------------------------
if st.session_state.get("using_demo") and books and not devices:
    from services.demo_loader import demo_db_available, kindle_demo_available, load_demo_dataset, load_kindle_demo_dataset

    _demo_source = "Kindle" if st.session_state.get("data_source") == "kindle" else "Kobo"
    _col_info, _col_btn = st.columns([4, 1])
    with _col_info:
        st.info(
            f"📚 **Loaded {_demo_source} demo dataset** — you're viewing synthetic reading data.  \n"
            "Upload your own KoboReader.sqlite or Kindle My Clippings.txt in the sidebar "
            "to explore your library.",
            icon="ℹ️",
        )
    with _col_btn:
        if _demo_source == "Kobo" and kindle_demo_available():
            if st.button("🔄 Switch to Kindle demo", key="switch_kindle_demo"):
                load_kindle_demo_dataset()
                _go_to("overview")
                st.rerun()
        elif _demo_source == "Kindle" and demo_db_available():
            if st.button("🔄 Switch to Kobo demo", key="switch_kobo_demo"):
                load_demo_dataset()
                st.session_state["data_source"] = "kobo"
                _go_to("overview")
                st.rerun()

# ---------------------------------------------------------------------------
# Welcome view
# ---------------------------------------------------------------------------
if not books or view == "welcome":
    # Auto-load the synthetic demo dataset so the dashboard is immediately
    # populated.  User uploads and device loading always take priority.
    from services.demo_loader import demo_db_available, load_demo_dataset

    if not books and demo_db_available() and not st.session_state.get("using_demo"):
        demo_books = load_demo_dataset()
        if demo_books:
            _go_to("overview")
            st.rerun()

    st.markdown(
        '<div class="kn-hero">'
        '<h1>KoNotes</h1>'
        '<p>Turn your Kobo & Kindle highlights into structured, readable insight.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

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
            '<p>Annotations are extracted from Kobo SQLite, Kindle '
            'My Clippings.txt, or HTML/TXT/MD exports.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            '<div class="kn-step">'
            '<div class="kn-step-num">3</div>'
            '<h4>Explore</h4>'
            '<p>Browse your library, track reading activity, and export '
            'as Markdown, JSON, or plain text.</p>'
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
            "| Kindle My Clippings | `.txt` | **Primary** |\n"
            "| HTML export | `.html` | Secondary |\n"
            "| Plain-text export | `.txt` | Secondary |\n"
            "| Markdown export | `.md` | Secondary |"
        )
    with c2:
        st.markdown("##### How it works")
        st.markdown(
            "- **Fully local** -- nothing leaves your machine\n"
            "- **Read-only** -- your Kobo data is never modified\n"
            "- **Smart dedup** -- annotations merged across sources\n"
            "- **Chapter names** -- cleaned from raw Kobo IDs\n"
            "- **Rich telemetry** -- shelves, progress, sessions, activity"
        )

    st.markdown(
        '<div class="kn-footer">'
        'Connect your Kobo, upload a Kindle clippings file, or upload an export in the sidebar to get started.'
        '</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Overview dashboard
# ---------------------------------------------------------------------------
elif view == "overview":
    from app.views.overview import render_overview

    sessions: list[ReadingSession] = st.session_state.get("sessions", [])
    snapshots: list[ProgressSnapshot] = st.session_state.get("snapshots", [])
    word_lookups = st.session_state.get("word_lookups", [])
    render_overview(
        books,
        sessions,
        snapshots,
        navigate=_go_to,
        word_lookups=word_lookups,
        data_source=st.session_state.get("data_source", "kobo"),
        using_demo=st.session_state.get("using_demo", False),
    )

# ---------------------------------------------------------------------------
# Library view
# ---------------------------------------------------------------------------
elif view == "library":
    from app.views.library import render_library
    render_library(books, navigate=_go_to, data_source=st.session_state.get("data_source", "kobo"))

# ---------------------------------------------------------------------------
# Book detail view
# ---------------------------------------------------------------------------
elif view == "book_detail":
    from app.views.book_detail import render_book_detail

    selected_id = st.session_state.get("selected_book_id")
    selected_book = next((b for b in books if b.id == selected_id), None)
    if selected_book:
        render_book_detail(selected_book, navigate=_go_to)
    else:
        st.error("Book not found.")
        if st.button("Back to library"):
            _go_to("library")
            st.rerun()

# ---------------------------------------------------------------------------
# All-annotations view
# ---------------------------------------------------------------------------
elif view == "annotations":
    from app.views.annotations import render_annotations
    render_annotations(books)

# ---------------------------------------------------------------------------
# Activity / telemetry view
# ---------------------------------------------------------------------------
elif view == "activity":
    from app.views.activity import render_activity

    sessions_data: list[ReadingSession] = st.session_state.get("sessions", [])
    snapshots_data: list[ProgressSnapshot] = st.session_state.get("snapshots", [])
    render_activity(books, sessions_data, snapshots_data, data_source=st.session_state.get("data_source", "kobo"))

# ---------------------------------------------------------------------------
# Vocabulary view
# ---------------------------------------------------------------------------
elif view == "vocabulary":
    from app.views.vocabulary_view import render_vocabulary

    word_lookups_data = st.session_state.get("word_lookups", [])
    render_vocabulary(word_lookups_data, books, data_source=st.session_state.get("data_source", "kobo"))

# ---------------------------------------------------------------------------
# AI Insights view
# ---------------------------------------------------------------------------
elif view == "insights":
    from app.views.insights import render_insights
    render_insights(books)

# ---------------------------------------------------------------------------
# Chat view
# ---------------------------------------------------------------------------
elif view == "chat":
    from app.views.chat import render_chat

    sessions_chat: list[ReadingSession] = st.session_state.get("sessions", [])
    render_chat(books, sessions=sessions_chat)

# ---------------------------------------------------------------------------
# Star prompt — shown once per session after meaningful data is visible
# ---------------------------------------------------------------------------
if books and view not in ("welcome",):
    from services.star_prompt import maybe_show_streamlit_star_prompt
    maybe_show_streamlit_star_prompt()
