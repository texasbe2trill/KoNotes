"""KoNotes CLI / programmatic entry point.

For the web UI, run:
    streamlit run app/app.py

This module provides a simple command-line interface for quick inspection
without the Streamlit UI.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print("KoNotes — Kobo annotation parser")
        print()
        print("Usage:")
        print("  python main.py <file>          Parse and display a summary")
        print("  streamlit run app/app.py   Launch the web UI")
        return 0

    from parser.export_parsers import get_parser_for_extension
    from parser.normalizer import normalize
    from services.stats import compute_stats

    path = Path(args[0])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    if path.suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        from parser.sqlite_parser import parse_sqlite
        raw = parse_sqlite(path)
        source = "kobo_sqlite"
    else:
        parser = get_parser_for_extension(path.suffix)
        if parser is None:
            print(f"Error: unsupported file type: {path.suffix}", file=sys.stderr)
            return 1
        content = path.read_text(encoding="utf-8", errors="replace")
        raw = parser.parse(content)
        source = parser.source_name

    books = normalize(raw, source)
    stats = compute_stats(books)

    print(f"\nKoNotes — parsed {path.name}")
    print(f"  Books:             {stats.total_books}")
    print(f"  Total annotations: {stats.total_annotations}")
    print(f"  Highlights:        {stats.total_highlights}")
    print(f"  Notes:             {stats.total_notes}")
    print()

    for book in books:
        h = sum(1 for a in book.annotations if a.kind == "highlight")
        n = sum(1 for a in book.annotations if a.kind == "note")
        author_str = f" by {book.author}" if book.author else ""
        print(f"  [{book.title}{author_str}]  {h} highlight(s), {n} note(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
