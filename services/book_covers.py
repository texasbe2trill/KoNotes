"""Book cover resolution — local-first with Open Library lookup by ISBN.

Priority order for ``resolve_book_cover``:

1. Local file path on disk (``book.cover_path``)
2. Cover URL already stored in parsed metadata (``book.cover_url``)
3. Open Library by ISBN — the same source Calibre uses. Only tried when
   the book has an ISBN; no title/author guessing to avoid wrong covers.
   Results are cached in ``~/.konotes/cover_cache.json``.
4. Fallback: generated initials placeholder (rendered by the UI component)

Only one remote source is used (Open Library) because ISBN lookups are
exact — a cover is either found or not. Fuzzy title/author searches from
other APIs too frequently return covers for the wrong edition or book.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from models.book import Book


# Public source labels — kept stable for tests & exports.
SOURCE_LOCAL = "local"
SOURCE_URL = "url"
SOURCE_DEMO = "demo"
SOURCE_FALLBACK = "fallback"


@dataclass(frozen=True)
class CoverResult:
    """Resolved cover information for a single book.

    Exactly one of ``path`` or ``url`` is populated for real covers.
    For ``SOURCE_FALLBACK``, both are None and the UI should render
    the initials placeholder.
    """

    source: str                      # one of SOURCE_*
    url: str | None = None           # populated for SOURCE_URL
    path: str | None = None          # populated for SOURCE_LOCAL or SOURCE_DEMO
    fallback_label: str = ""         # initials, always populated
    title: str = ""                  # convenience, always populated

    @property
    def has_image(self) -> bool:
        """True when the result points at a real image (not the fallback)."""
        return self.source != SOURCE_FALLBACK and bool(self.url or self.path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_book_cover(book: Book) -> CoverResult:
    """Return the best available cover for *book*.

    Always returns a :class:`CoverResult`. When no real cover exists,
    ``source`` will be :data:`SOURCE_FALLBACK` and the caller should
    render the initials placeholder.
    """
    label = get_cover_fallback_label(book)
    title = book.title or ""

    # 1. Local path takes precedence — confirmed to exist on disk.
    if book.cover_path:
        try:
            p = Path(book.cover_path)
            if p.is_file():
                return CoverResult(
                    source=SOURCE_LOCAL,
                    path=str(p),
                    fallback_label=label,
                    title=title,
                )
        except (OSError, ValueError):
            # Bad path string — fall through to next option.
            pass

    # 2. URL provided by parser metadata.
    if book.cover_url and _looks_like_url(book.cover_url):
        return CoverResult(
            source=SOURCE_URL,
            url=book.cover_url.strip(),
            fallback_label=label,
            title=title,
        )

    # 3. Remote fetch (Open Library → Google Books, cached on disk).
    remote = fetch_remote_cover_url(book)
    if remote:
        return CoverResult(
            source=SOURCE_URL,
            url=remote,
            fallback_label=label,
            title=title,
        )

    # 4. Explicit demo source marker or no cover found → fallback.
    return CoverResult(
        source=SOURCE_FALLBACK,
        fallback_label=label,
        title=title,
    )


def get_cover_for_book(book: Book) -> str | None:
    """Return a directly renderable cover reference (path or URL), or None.

    Convenience wrapper over :func:`resolve_book_cover` for callers that
    only need a single string to feed into ``st.image`` / ``<img src=>``.
    """
    result = resolve_book_cover(book)
    return result.path or result.url


def get_cover_fallback_label(book: Book) -> str:
    """Return the initials/short label used by the placeholder.

    - One-word titles → first 2 letters uppercased.
    - Multi-word titles → first letter of first 2 significant words.
    - Empty / unknown → "??".
    """
    return _initials(book.title or "")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_SKIP_WORDS = {"the", "a", "an", "of", "and", "or"}
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def _looks_like_url(value: str) -> bool:
    return bool(_URL_PATTERN.match(value.strip()))


@lru_cache(maxsize=512)
def _initials(title: str) -> str:
    """Compute up to 2 initial characters from a title."""
    cleaned = re.sub(r"[^\w\s]", " ", title).strip()
    if not cleaned:
        return "??"
    words = [w for w in cleaned.split() if w.lower() not in _SKIP_WORDS] or cleaned.split()
    if len(words) == 1:
        word = words[0]
        return word[:2].upper() if len(word) >= 2 else word.upper()
    return (words[0][0] + words[1][0]).upper()


# ---------------------------------------------------------------------------
# Remote cover fetching (Open Library + Google Books, persistent cache)
# ---------------------------------------------------------------------------

_NETWORK_TIMEOUT = 4   # seconds — short enough not to block the UI
_CACHE_DIR = Path.home() / ".konotes"
_CACHE_FILE = _CACHE_DIR / "cover_cache.json"
_cache_lock = threading.Lock()
_mem_cache: dict[str, str | None] | None = None   # lazy-loaded

# Bump this string whenever the lookup strategy changes so that stale
# cache entries (e.g. from the previous Google Books implementation)
# are automatically discarded rather than served as wrong covers.
_CACHE_VERSION = "v2-openlibrary-isbn-only"
_CACHE_VERSION_KEY = "__version__"


def _load_cache() -> dict[str, str | None]:
    """Load the on-disk cover cache, discarding it when the version key
    doesn't match _CACHE_VERSION.
    """
    global _mem_cache
    if _mem_cache is not None:
        return _mem_cache
    with _cache_lock:
        if _mem_cache is not None:
            return _mem_cache
        try:
            data: dict[str, str | None] = json.loads(
                _CACHE_FILE.read_text(encoding="utf-8")
            )
            # Version mismatch → stale strategy; discard everything.
            if data.get(_CACHE_VERSION_KEY) != _CACHE_VERSION:
                data = {}
        except Exception:
            data = {}
        _mem_cache = data
    return _mem_cache


def _write_cache(cache: dict[str, str | None]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Always stamp the version so future loads can validate it.
        to_write = {_CACHE_VERSION_KEY: _CACHE_VERSION, **cache}
        _CACHE_FILE.write_text(json.dumps(to_write, indent=2), encoding="utf-8")
    except Exception:
        pass


def _cache_lookup(key: str) -> tuple[bool, str | None]:
    """Return (hit, value). hit=True means the key exists (value may be None = known miss)."""
    cache = _load_cache()
    if key in cache:
        return True, cache[key]
    return False, None


def _cache_store(key: str, value: str | None) -> None:
    cache = _load_cache()
    with _cache_lock:
        cache[key] = value
        _write_cache(cache)


def _open_library_cover(isbn: str) -> str | None:
    """Try Open Library covers API by ISBN.

    Uses ``?default=false`` so the endpoint returns 404 (not a stub
    placeholder image) when no cover is found.
    """
    try:
        import requests as _req
        url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
        r = _req.head(url, timeout=_NETWORK_TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    except Exception:
        pass
    return None


def fetch_remote_cover_url(book: Book) -> str | None:
    """Attempt to retrieve a cover URL for *book* from Open Library.

    Only tried when the book has an ISBN — no title/author guessing, which
    avoids matching the wrong edition. Returns ``None`` when no ISBN is
    present, the ISBN is not in the Open Library catalogue, or the network
    is unavailable.

    Results (including confirmed misses) are stored in
    ``~/.konotes/cover_cache.json`` so each ISBN is only looked up once.
    """
    isbn = re.sub(r"[^0-9X]", "", (book.isbn or "").upper())
    if not isbn:
        return None

    hit, cached = _cache_lookup(isbn)
    if hit:
        return cached

    result = _open_library_cover(isbn)
    _cache_store(isbn, result)
    return result
