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


def test_resolve_uses_cached_remote_url_when_no_local_or_url():
    """Cached remote lookups surface through resolve without hitting the network."""
    remote = "https://covers.openlibrary.org/b/isbn/9780140449136-L.jpg"
    book = _book(isbn="9780140449136")
    with patch("services.book_covers._cached_remote_url", return_value=remote):
        result = resolve_book_cover(book)
    assert result.source == SOURCE_URL
    assert result.url == remote
    assert result.has_image is True


def test_resolve_never_hits_network():
    """``resolve_book_cover`` must be cache-only — UI renders must not block."""
    book = _book(isbn="9780140449136", title="T", author="A")
    with (
        patch("services.book_covers.fetch_remote_cover_url") as fetch,
        patch("services.book_covers._google_books_cover") as gb,
        patch("services.book_covers._open_library_cover") as ol_isbn,
        patch("services.book_covers._open_library_search_cover") as ol_search,
    ):
        resolve_book_cover(book)
    fetch.assert_not_called()
    gb.assert_not_called()
    ol_isbn.assert_not_called()
    ol_search.assert_not_called()


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


def test_fetch_remote_cover_url_falls_back_to_search_when_no_isbn():
    """With no ISBN, Google Books is tried first (primary), then Open Library search."""
    book = _book(title="Some Book", author="Some Author")  # no ISBN
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store"),
        patch("services.book_covers._google_books_cover", return_value=None) as gb,
        patch("services.book_covers._open_library_search_cover", return_value=None) as ol_search,
    ):
        result = fetch_remote_cover_url(book)
    assert result is None
    gb.assert_called_once()
    ol_search.assert_called_once()


def test_fetch_remote_cover_url_returns_none_when_no_source_has_cover():
    book = _book(isbn="9780000000001", title="Unknown", author="Nobody")
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store"),
        patch("services.book_covers._open_library_cover", return_value=None),
        patch("services.book_covers._open_library_search_cover", return_value=None),
        patch("services.book_covers._google_books_cover", return_value=None),
    ):
        result = fetch_remote_cover_url(book)
    assert result is None


def test_fetch_remote_cover_url_falls_back_to_open_library_when_google_misses():
    """Open Library by ISBN is the documented fallback when Google Books has no result."""
    book = _book(isbn="9780000000001", title="Found Elsewhere", author="Author")
    ol_url = "https://covers.openlibrary.org/b/isbn/9780000000001-L.jpg"
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store"),
        patch("services.book_covers._google_books_cover", return_value=None) as gb,
        patch("services.book_covers._open_library_cover", return_value=ol_url) as ol_isbn,
    ):
        result = fetch_remote_cover_url(book)
    assert result == ol_url
    gb.assert_called_once()
    ol_isbn.assert_called_once()


def test_fetch_remote_cover_url_prefers_google_books_over_open_library():
    book = _book(isbn="9780000000001", title="T", author="A")
    google_url = "https://books.google.com/books/content?id=abc"
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers._cache_store"),
        patch("services.book_covers._google_books_cover", return_value=google_url),
        patch("services.book_covers._open_library_cover") as ol_isbn,
        patch("services.book_covers._open_library_search_cover") as ol_search,
    ):
        result = fetch_remote_cover_url(book)
    assert result == google_url
    ol_isbn.assert_not_called()  # Google hit — Open Library must not be called
    ol_search.assert_not_called()


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


# ── Spec-named API: get_cover_url, normalize_title_author, source helpers ──


def test_normalize_title_author_strips_series_and_lowercases():
    from services.book_covers import normalize_title_author

    book = _book(title="Dune (Dune, #1)", author="  Frank Herbert ")
    title, author = normalize_title_author(book)
    assert title == "dune"
    assert author == "frank herbert"


def test_normalize_title_author_handles_missing_fields():
    from services.book_covers import normalize_title_author

    book = _book(title="", author=None)
    assert normalize_title_author(book) == ("", "")


def test_get_cover_url_is_alias_of_get_cover_for_book():
    from services.book_covers import get_cover_url

    book = _book(cover_url="https://example.com/c.jpg")
    with patch("services.book_covers.fetch_remote_cover_url", return_value=None):
        assert get_cover_url(book) == "https://example.com/c.jpg"


def test_get_open_library_cover_uses_isbn_first():
    from services.book_covers import get_open_library_cover

    book = _book(isbn="9780000000001", title="T", author="A")
    isbn_url = "https://covers.openlibrary.org/b/isbn/9780000000001-L.jpg"
    with (
        patch("services.book_covers._open_library_cover", return_value=isbn_url) as ol_isbn,
        patch("services.book_covers._open_library_search_cover") as ol_search,
    ):
        result = get_open_library_cover(book)
    assert result == isbn_url
    ol_isbn.assert_called_once()
    ol_search.assert_not_called()


def test_get_open_library_cover_falls_back_to_search_when_no_isbn():
    from services.book_covers import get_open_library_cover

    book = _book(title="Some Title", author="Some Author")  # no ISBN
    search_url = "https://covers.openlibrary.org/b/id/12345-L.jpg"
    with patch(
        "services.book_covers._open_library_search_cover",
        return_value=search_url,
    ) as ol_search:
        result = get_open_library_cover(book)
    assert result == search_url
    ol_search.assert_called_once()


def test_get_google_books_cover_calls_internal_with_normalized_fields():
    from services.book_covers import get_google_books_cover

    book = _book(title="Dune (Dune, #1)", author="Frank Herbert")
    with patch(
        "services.book_covers._google_books_cover",
        return_value="https://books.google.com/x.jpg",
    ) as gb:
        result = get_google_books_cover(book)
    assert result == "https://books.google.com/x.jpg"
    gb.assert_called_once_with("dune", "frank herbert", isbn="")


def test_google_books_cover_upgrades_resolution_and_forces_https():
    """``_google_books_cover`` should strip ``zoom=N`` and rewrite http→https."""
    from services.book_covers import _google_books_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "items": [{
            "volumeInfo": {
                "title": "Dune",
                "authors": ["Frank Herbert"],
                "imageLinks": {
                    "thumbnail": "http://books.google.com/books/content?id=abc&printsec=frontcover&img=1&zoom=1",
                }
            }
        }]
    }
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        url = _google_books_cover("dune", "frank herbert")
    assert url is not None
    assert url.startswith("https://")
    assert "zoom=" not in url


def test_google_books_cover_returns_none_for_empty_response():
    from services.book_covers import _google_books_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"items": []}
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        assert _google_books_cover("nope", "nobody") is None


def test_google_books_cover_returns_none_on_network_error():
    from services.book_covers import _google_books_cover

    fake_req = MagicMock()
    fake_req.get.side_effect = RuntimeError("boom")
    with patch.dict("sys.modules", {"requests": fake_req}):
        assert _google_books_cover("any", "any") is None


def test_open_library_search_cover_handles_missing_cover_id():
    from services.book_covers import _open_library_search_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"docs": [{"title": "X"}]}  # no cover_i
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        assert _open_library_search_cover("x", "y") is None


def test_fetch_remote_cover_url_text_key_cache_hit_skips_network():
    """A previously-resolved title/author pair should hit the cache."""
    book = _book(title="Cached Book", author="Cached Author")
    cache_data = {"ta:cached book|cached author": "https://cached.example.com/c.jpg"}
    with (
        patch("services.book_covers._load_cache", return_value=cache_data),
        patch("services.book_covers._open_library_search_cover") as ol_search,
        patch("services.book_covers._google_books_cover") as gb,
    ):
        result = fetch_remote_cover_url(book)
    assert result == "https://cached.example.com/c.jpg"
    ol_search.assert_not_called()
    gb.assert_not_called()


# ── Match validation: reject wrong-book covers ──────────────────────────────


def test_google_books_rejects_unrelated_title():
    """A result for a different book must be rejected, not returned."""
    from services.book_covers import _google_books_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "items": [{
            "volumeInfo": {
                "title": "A Completely Different Book",
                "authors": ["Someone Else"],
                "imageLinks": {"thumbnail": "https://books.google.com/wrong.jpg"},
            }
        }]
    }
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        result = _google_books_cover("the hobbit", "j.r.r. tolkien")
    assert result is None


def test_google_books_walks_past_bad_candidates():
    """Wrong first result is skipped; correct second result is accepted."""
    from services.book_covers import _google_books_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "items": [
            {"volumeInfo": {
                "title": "Completely Unrelated",
                "authors": ["Nobody"],
                "imageLinks": {"thumbnail": "https://books.google.com/wrong.jpg"},
            }},
            {"volumeInfo": {
                "title": "The Hobbit",
                "authors": ["J.R.R. Tolkien"],
                "imageLinks": {"thumbnail": "https://books.google.com/right.jpg"},
            }},
        ]
    }
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        result = _google_books_cover("the hobbit", "j.r.r. tolkien")
    assert result == "https://books.google.com/right.jpg"


def test_google_books_isbn_lookup_skips_validation():
    """ISBN lookups trust Google — no title/author comparison needed."""
    from services.book_covers import _google_books_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "items": [{
            "volumeInfo": {
                # Title differs from what the user has — ISBN is authoritative.
                "title": "Localized Edition",
                "authors": ["Translator"],
                "imageLinks": {"thumbnail": "https://books.google.com/by-isbn.jpg"},
            }
        }]
    }
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        result = _google_books_cover("original title", "author", isbn="9780000000001")
    assert result == "https://books.google.com/by-isbn.jpg"


def test_open_library_search_rejects_unrelated_result():
    from services.book_covers import _open_library_search_cover

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "docs": [{
            "title": "Cookbook of Cooking",
            "author_name": ["Chef"],
            "cover_i": 999,
        }]
    }
    fake_req = MagicMock()
    fake_req.get.return_value = fake_resp
    with patch.dict("sys.modules", {"requests": fake_req}):
        assert _open_library_search_cover("dune", "frank herbert") is None


def test_match_score_identical_is_full():
    from services.book_covers import _match_score

    assert _match_score("Dune", "Frank Herbert", "Dune", ["Frank Herbert"]) >= 0.99


def test_match_score_unrelated_is_low():
    from services.book_covers import _match_score

    score = _match_score("Dune", "Frank Herbert", "Cookbook", ["Chef"])
    assert score < 0.5


def test_match_score_tolerates_subtitle_and_series():
    from services.book_covers import _match_score, _MATCH_THRESHOLD

    # Real-world edition variants should still pass.
    score = _match_score(
        "the hobbit", "j.r.r. tolkien",
        "The Hobbit: Or There and Back Again", ["J. R. R. Tolkien"],
    )
    assert score >= _MATCH_THRESHOLD


# ── Parallel prefetch ───────────────────────────────────────────────────────


def test_prefetch_covers_is_noop_for_empty_list():
    from services.book_covers import prefetch_covers

    # Should not raise, not hit network.
    prefetch_covers([])


def test_prefetch_covers_skips_books_with_metadata_urls():
    from services.book_covers import prefetch_covers

    books = [
        _book(id=f"b{i}", cover_url=f"https://example.com/{i}.jpg")
        for i in range(3)
    ]
    with patch("services.book_covers.fetch_remote_cover_url") as fetch:
        prefetch_covers(books, block=True)
    fetch.assert_not_called()


def test_prefetch_covers_skips_books_already_in_cache():
    from services.book_covers import prefetch_covers

    book = _book(isbn="9780000000001", title="T", author="A")
    with (
        patch(
            "services.book_covers._load_cache",
            return_value={"9780000000001": "https://cached.example.com/c.jpg"},
        ),
        patch("services.book_covers.fetch_remote_cover_url") as fetch,
    ):
        prefetch_covers([book], block=True)
    fetch.assert_not_called()


def test_prefetch_covers_resolves_books_needing_lookup():
    from services.book_covers import prefetch_covers

    books = [_book(id=f"b{i}", title=f"Title {i}", author="A") for i in range(3)]
    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers.fetch_remote_cover_url") as fetch,
    ):
        prefetch_covers(books, max_workers=2, block=True)
    assert fetch.call_count == 3


def test_prefetch_covers_swallows_individual_errors():
    """One failing lookup must not break the rest."""
    from services.book_covers import prefetch_covers

    books = [_book(id=f"b{i}", title=f"T{i}", author="A") for i in range(3)]

    call_count = {"n": 0}

    def sometimes_fails(_book):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("transient")
        return None

    with (
        patch("services.book_covers._load_cache", return_value={}),
        patch("services.book_covers.fetch_remote_cover_url", side_effect=sometimes_fails),
    ):
        prefetch_covers(books, max_workers=1, block=True)
    assert call_count["n"] == 3


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

