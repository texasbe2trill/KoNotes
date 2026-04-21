"""Book cover resolution — local-first with Google Books + Open Library lookup.

Priority order for ``resolve_book_cover`` / ``get_cover_url``:

1. Local file path on disk (``book.cover_path``)
2. Cover URL already stored in parsed metadata (``book.cover_url``)
3. Google Books — by title+author (primary; one fast GET, broad catalogue)
4. Open Library — by ISBN when available, else by title+author search (backup)
5. Fallback: generated initials placeholder (rendered by the UI component)

All remote lookups (positive and negative) are cached on disk in
``~/.konotes/cover_cache.json`` so each (isbn / title|author) is only
looked up once. Network calls use a short timeout and never raise to the
caller — the UI always degrades to the initials placeholder on failure.
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
    """Return the best available cover for *book* without ever blocking.

    Checks local path, metadata URL, and the on-disk cache. Does **not**
    hit the network — network lookups are batched asynchronously by
    :func:`prefetch_covers`. When no cached cover is available this
    returns the fallback (initials placeholder) immediately.
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

    # 3. Cached remote result — never touches the network.
    cached = _cached_remote_url(book)
    if cached:
        return CoverResult(
            source=SOURCE_URL,
            url=cached,
            fallback_label=label,
            title=title,
        )

    # 4. No cover yet (may arrive on next render after prefetch completes).
    return CoverResult(
        source=SOURCE_FALLBACK,
        fallback_label=label,
        title=title,
    )


def _cached_remote_url(book: Book) -> str | None:
    """Return the cached cover URL for *book*, or None. No network access."""
    isbn = re.sub(r"[^0-9X]", "", (book.isbn or "").upper())
    title, author = normalize_title_author(book)
    text_key = f"ta:{title}|{author}" if title else None

    for key in (isbn or None, text_key):
        if not key:
            continue
        hit, cached = _cache_lookup(key)
        if hit and cached:
            return cached
    return None


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

_NETWORK_TIMEOUT = 2.5   # seconds — short enough not to block the UI
_CACHE_DIR = Path.home() / ".konotes"
_CACHE_FILE = _CACHE_DIR / "cover_cache.json"
_cache_lock = threading.Lock()
_mem_cache: dict[str, str | None] | None = None   # lazy-loaded

# Bump this string whenever the lookup strategy changes so that stale
# cache entries (e.g. from the previous Google Books implementation)
# are automatically discarded rather than served as wrong covers.
_CACHE_VERSION = "v6-isbn-required-async-prefetch"
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


def _open_library_search_cover(title: str, author: str) -> str | None:
    """Search Open Library by title (+ author) and return a large cover URL.

    Walks the top results until one passes :func:`_match_score`. Returns
    ``None`` when no candidate matches confidently — better an initials
    placeholder than the wrong cover.
    """
    if not title:
        return None
    try:
        import requests as _req
        params: dict[str, str] = {"title": title, "limit": "5"}
        if author:
            params["author"] = author
        r = _req.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=_NETWORK_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        docs = (r.json() or {}).get("docs") or []
        for doc in docs:
            cover_id = doc.get("cover_i")
            if not cover_id:
                continue
            cand_title = doc.get("title") or ""
            cand_authors = doc.get("author_name") or []
            if _match_score(title, author, cand_title, cand_authors) < _MATCH_THRESHOLD:
                continue
            return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        return None
    except Exception:
        return None


def _google_books_cover(title: str, author: str, isbn: str = "") -> str | None:
    """Search Google Books and return a validated, high-res thumbnail URL.

    Search strategy:

    1. If *isbn* is provided, query ``q=isbn:{isbn}`` first — exact match.
    2. Otherwise query ``intitle:{title}+inauthor:{author}`` and validate
       each candidate's title/author against the request, returning the
       first that passes :func:`_match_score`.

    Returns the upgraded https URL (no ``zoom=`` param) or ``None``.
    """
    if not title and not isbn:
        return None
    try:
        import requests as _req
        # 1. ISBN lookup first when available — Google indexes most editions.
        if isbn:
            r = _req.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{isbn}", "maxResults": "1"},
                timeout=_NETWORK_TIMEOUT,
            )
            if r.status_code == 200:
                url = _extract_google_image(r.json(), title, author, validate=False)
                if url:
                    return url

        if not title:
            return None

        # 2. Title + author search with validation across top 5 candidates.
        q_parts = [f"intitle:{title}"]
        if author:
            q_parts.append(f"inauthor:{author}")
        r = _req.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": "+".join(q_parts), "maxResults": "5"},
            timeout=_NETWORK_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        return _extract_google_image(r.json(), title, author, validate=True)
    except Exception:
        return None


def _extract_google_image(
    payload: dict, title: str, author: str, *, validate: bool
) -> str | None:
    """Pick the first Google Books volume with a usable, validated cover.

    When ``validate=True``, candidates must pass title/author matching.
    Placeholder URLs are filtered by :func:`_looks_like_real_google_cover`.
    """
    items = (payload or {}).get("items") or []
    for item in items:
        info = item.get("volumeInfo") or {}
        if validate:
            cand_title = info.get("title") or ""
            cand_authors = info.get("authors") or []
            if _match_score(title, author, cand_title, cand_authors) < _MATCH_THRESHOLD:
                continue
        links = info.get("imageLinks") or {}
        url = links.get("thumbnail") or links.get("smallThumbnail")
        if not url or not _looks_like_real_google_cover(url):
            continue
        url = re.sub(r"&zoom=\d+", "", url)
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        return url
    return None


def _looks_like_real_google_cover(url: str) -> bool:
    """Reject obvious Google Books "no image available" URLs.

    The placeholder image is served from paths/ids that never include the
    standard ``id=`` query param, or that embed known marker tokens.
    """
    low = url.lower()
    if "no_cover" in low or "no-cover" in low or "nocover" in low:
        return False
    return True


# ---------------------------------------------------------------------------
# Match scoring — prevents wrong-book covers
# ---------------------------------------------------------------------------

# Minimum combined title+author similarity (0.0–1.0) for a candidate to be
# accepted. Tuned so that close edition variants pass ("Dune" vs "Dune:
# Book One") while different books fail.
_MATCH_THRESHOLD = 0.72


def _normalize_for_match(s: str) -> str:
    """Lowercase, strip punctuation, drop articles/subtitle suffixes."""
    s = s.lower()
    # Drop subtitle after first colon (common in editions).
    s = s.split(":", 1)[0]
    # Drop trailing parenthetical (series, volume).
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Drop leading articles.
    for art in ("the ", "a ", "an "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def _similarity(a: str, b: str) -> float:
    """Cheap token-set Jaccard similarity in [0, 1]."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _author_similarity(want: str, candidates: list[str]) -> float:
    """Best similarity across any candidate author. ``1.0`` when no want."""
    if not want:
        return 1.0  # caller didn't constrain — don't penalize
    if not candidates:
        return 0.0
    want_n = _normalize_for_match(want)
    # Compare against last-name tokens too — Google often returns "Frank
    # Herbert" while the user has "Herbert, Frank".
    want_tokens = set(want_n.split())
    best = 0.0
    for cand in candidates:
        cand_n = _normalize_for_match(cand)
        score = _similarity(want_n, cand_n)
        # Bonus: any shared surname-length token counts as partial match.
        if want_tokens & set(cand_n.split()):
            score = max(score, 0.6)
        if score > best:
            best = score
    return best


def _match_score(
    want_title: str,
    want_author: str,
    cand_title: str,
    cand_authors: list[str],
) -> float:
    """Combined title/author confidence in [0, 1].

    Title is weighted more heavily than author because users may have
    "Last, First" while APIs return "First Last", and pseudonyms differ.
    """
    t = _similarity(_normalize_for_match(want_title), _normalize_for_match(cand_title))
    a = _author_similarity(want_author, cand_authors)
    return 0.7 * t + 0.3 * a


# ---------------------------------------------------------------------------
# Spec-named public API (services.book_covers acts as the cover service).
# These thin wrappers expose the names requested by the cover-service spec
# while reusing the cached resolver implementation above.
# ---------------------------------------------------------------------------


def normalize_title_author(book: Book) -> tuple[str, str]:
    """Return a ``(title, author)`` tuple suitable for cache keys / search.

    - Strips whitespace
    - Lowercases
    - Collapses internal whitespace
    - Drops a trailing parenthetical (e.g. ``"Dune (Dune, #1)"`` → ``"dune"``)
    """
    title = re.sub(r"\s*\([^)]*\)\s*$", "", (book.title or "")).strip().lower()
    title = re.sub(r"\s+", " ", title)
    author = re.sub(r"\s+", " ", (book.author or "").strip().lower())
    return title, author


def get_open_library_cover(book: Book) -> str | None:
    """ISBN-first, then title+author search against Open Library."""
    isbn = re.sub(r"[^0-9X]", "", (book.isbn or "").upper())
    if isbn:
        url = _open_library_cover(isbn)
        if url:
            return url
    title, author = normalize_title_author(book)
    return _open_library_search_cover(title, author)


def get_google_books_cover(book: Book) -> str | None:
    """Google Books cover lookup, ISBN-first when available."""
    title, author = normalize_title_author(book)
    isbn = re.sub(r"[^0-9X]", "", (book.isbn or "").upper())
    return _google_books_cover(title, author, isbn=isbn)


def get_cover_url(book: Book) -> str | None:
    """Return a renderable cover URL/path for *book*, or ``None``.

    Implements the full priority chain (local → metadata URL → Open Library
    → Google Books). Results from remote sources are cached on disk.
    """
    return get_cover_for_book(book)


def fetch_remote_cover_url(book: Book) -> str | None:
    """Resolve a remote cover URL for *book*.

    Tries Google Books first (single fast GET, broad catalogue), then falls
    back to Open Library by ISBN and title+author search. Lookups are keyed
    by ISBN (when present) and by normalized ``"title|author"`` and stored
    in ``~/.konotes/cover_cache.json``. Negative results are cached too so
    repeated UI renders don't re-hit the network.
    """
    isbn = re.sub(r"[^0-9X]", "", (book.isbn or "").upper())
    title, author = normalize_title_author(book)
    text_key = f"ta:{title}|{author}" if title else None

    # Use the most specific cache key available first.
    for key in (isbn or None, text_key):
        if not key:
            continue
        hit, cached = _cache_lookup(key)
        if hit:
            return cached

    # 1. Google Books — primary source: fast, broad catalogue, validated.
    if title or isbn:
        url = _google_books_cover(title, author, isbn=isbn)
        if url:
            if isbn:
                _cache_store(isbn, url)
            if text_key:
                _cache_store(text_key, url)
            return url

    # 2. Open Library by ISBN — backup when Google misses.
    if isbn:
        url = _open_library_cover(isbn)
        if url:
            _cache_store(isbn, url)
            if text_key:
                _cache_store(text_key, url)
            return url

    # 3. Open Library by title+author — last network attempt.
    if title:
        url = _open_library_search_cover(title, author)
        if url:
            if isbn:
                _cache_store(isbn, url)
            _cache_store(text_key, url)  # type: ignore[arg-type]
            return url

    # 4. Confirmed miss — cache None so we don't retry.
    if isbn:
        _cache_store(isbn, None)
    if text_key:
        _cache_store(text_key, None)
    return None


# ---------------------------------------------------------------------------
# Parallel prefetch — warms the on-disk cache so the UI never blocks on
# first render. Safe to call repeatedly; already-cached books are skipped.
# ---------------------------------------------------------------------------


def prefetch_covers(
    books: list[Book],
    *,
    max_workers: int = 8,
    block: bool = False,
) -> bool:
    """Resolve covers for *books* concurrently, populating the disk cache.

    By default this is **fire-and-forget**: a daemon thread runs the
    lookups and the call returns immediately so the UI never blocks. Pass
    ``block=True`` (used by tests) to wait for completion.

    Returns ``True`` when at least one book was enqueued for resolution.
    Any book whose cover is already known (local path, metadata URL, or
    cached lookup) is skipped. Exceptions from individual lookups are
    swallowed — the UI always degrades to the initials placeholder.
    """
    if not books:
        return False

    targets: list[Book] = []
    cache = _load_cache()
    for b in books:
        # Skip books we can resolve without any network.
        if b.cover_path or (b.cover_url and _looks_like_url(b.cover_url)):
            continue
        isbn = re.sub(r"[^0-9X]", "", (b.isbn or "").upper())
        title, author = normalize_title_author(b)
        text_key = f"ta:{title}|{author}" if title else None
        if isbn and isbn in cache:
            continue
        if text_key and text_key in cache:
            continue
        targets.append(b)

    if not targets:
        return False

    workers = max(1, min(max_workers, len(targets)))

    def _run() -> None:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in pool.map(_safe_fetch, targets):
                pass

    if block:
        _run()
        return True

    # Fire-and-forget: daemon thread so it won't prevent interpreter exit.
    thread = threading.Thread(target=_run, name="konotes-cover-prefetch", daemon=True)
    thread.start()
    return True


def _safe_fetch(book: Book) -> None:
    try:
        fetch_remote_cover_url(book)
    except Exception:
        pass
