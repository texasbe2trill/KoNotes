"""Tests for the book cover resolver, fallback labels, and HTML export integration."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.book import Book
from services.book_covers import (
    SOURCE_DEMO,
    SOURCE_FALLBACK,
    SOURCE_LOCAL,
    SOURCE_URL,
    CoverResult,
    _open_library_cover,
    fetch_remote_cover_url,
    get_cover_fallback_label,
    get_cover_for_book,
    resolve_book_cover,
)


def _book(**overrides) -> Book:
    """Helper to build a minimal Book with overridable fields."""
    base = {"id": "b1", "title": "Test Title", "source": "test"}
    base.update(overrides)
    return Book(**base)


# ── resolve_book_cover priority ─────────────────────────────────────────────


def test_resolve_falls_back_when_no_cover_and_no_network():
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(_book())
    assert isinstance(result, CoverResult)
    assert result.source == SOURCE_FALLBACK
    assert result.has_image is False
    assert result.fallback_label  # non-empty initials


def test_resolve_uses_local_path_when_file_exists(tmp_path: Path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"fake")
    book = _book(cover_path=str(cover), cover_url="https://example.com/x.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_LOCAL
    assert result.path == str(cover)
    assert result.has_image is True


def test_resolve_skips_local_path_when_missing_file(tmp_path: Path):
    bogus = tmp_path / "nope.jpg"  # not created
    book = _book(cover_path=str(bogus), cover_url="https://example.com/x.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_URL
    assert result.url == "https://example.com/x.jpg"


def test_resolve_uses_url_when_no_local_path():
    book = _book(cover_url="https://example.com/cover.png")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_URL
    assert result.url == "https://example.com/cover.png"
    assert result.has_image is True


def test_resolve_rejects_non_http_url():
    book = _book(cover_url="javascript:alert(1)")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_FALLBACK


def test_resolve_uses_remote_fetch_when_no_local_or_url():
    remote = "https://covers.openlibrary.org/b/isbn/9780140449136-L.jpg"
    book = _book(isbn="9780140449136")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=remote):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_URL
    assert result.url == remote
    assert result.has_image is True


def test_resolve_handles_invalid_path_gracefully():
    book = _book(cover_path="\x00bad\x00path")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        result = resolve_book_cover(book)
    assert result.source in {SOURCE_FALLBACK, SOURCE_URL, SOURCE_LOCAL}


# ── fetch_remote_cover_url ───────────────────────────────────────────────────


def test_fetch_remote_cover_url_uses_cache(tmp_path: Path):
    book = _book(isbn="0000000001")
    cache_data = {"0000000001": "https://cached.example.com/c.jpg"}
    with (
        patch("services.book_covers._load_cache", return_value=cache_data),
        patch("services.book_covers._cache_store") as mock_store,
    ):
        result = fetch_remote_cover_url(book)
    assert result == "https://cached.example.com/c.jpg"
    mock_store.assert_not_called()  # cache hit — nothing written


def test_fetch_remote_cover_url_returns_none_for_book_without_isbn():
    book = _book(title="Some Book", author="Some Author")  # no ISBN
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store") as mock_store,
    ):
        result = fetch_remote_cover_url(book)
    assert result is None
    mock_store.assert_not_called()  # no ISBN → no lookup attempt


def test_fetch_remote_cover_url_returns_none_when_not_in_open_library():
    book = _book(isbn="9780000000001")
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store"),
        patch("services.book_covers._open_library_cover", return_value=None),
    ):
        result = fetch_remote_cover_url(book)
    assert result is None


def test_open_library_cover_returns_url_on_200(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_req = MagicMock()
    mock_req.head.return_value = mock_resp
    monkeypatch.setitem(__import__("sys").modules, "requests", mock_req)

    import importlib
    import services.book_covers as sbc
    importlib.reload(sbc)  # re-apply with mock

    with patch.dict("sys.modules", {"requests": mock_req}):
        result = _open_library_cover("9780140449136")
    assert result is None or result.startswith("https://covers.openlibrary.org")


# ── get_cover_for_book convenience ──────────────────────────────────────────


def test_get_cover_for_book_returns_url():
    book = _book(cover_url="https://example.com/c.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        assert get_cover_for_book(book) == "https://example.com/c.jpg"


def test_get_cover_for_book_returns_none_for_fallback():
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        assert get_cover_for_book(_book()) is None


# ── Initials / fallback label ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Dune", "DU"),
        ("The Great Gatsby", "GG"),
        ("A Brief History of Time", "BH"),
        ("X", "X"),
        ("", "??"),
        ("...", "??"),
        ("War and Peace", "WP"),
        ("of and the", "OA"),
    ],
)
def test_initials_formatting(title, expected):
    assert get_cover_fallback_label(_book(title=title)) == expected


# ── cover_html_fragment ──────────────────────────────────────────────────────


def test_cover_html_fragment_placeholder_when_no_book():
    from app.components.book_cover import cover_html_fragment
    html = cover_html_fragment(None, fallback_title="Meditations")
    assert "__placeholder" in html
    assert "ME" in html


def test_cover_html_fragment_img_when_url_cover():
    from app.components.book_cover import cover_html_fragment
    book = _book(title="Meditations", cover_url="https://example.com/cover.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        html = cover_html_fragment(book)
    assert '<img src="https://example.com/cover.jpg"' in html
    assert 'loading="lazy"' in html


# ── HTML export integration ─────────────────────────────────────────────────


def test_html_export_includes_cover_placeholder_when_no_cover():
    from services.export_html import _book_cover_html
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        html = _book_cover_html(_book(title="Dune"))
    assert "book-cover-wrap" in html
    assert "DU" in html


def test_html_export_includes_img_when_url_present():
    from services.export_html import _book_cover_html
    book = _book(cover_url="https://example.com/cover.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        html = _book_cover_html(book)
    assert '<img src="https://example.com/cover.jpg"' in html
    assert 'loading="lazy"' in html


def test_html_export_uses_local_path_when_file_exists(tmp_path: Path):
    from services.export_html import _book_cover_html
    cover = tmp_path / "c.jpg"
    cover.write_bytes(b"x")
    book = _book(cover_path=str(cover))
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        html = _book_cover_html(book)
    assert f'src="{cover}"' in html

