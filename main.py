"""KoNotes CLI entry point.

Subcommands:
    parse          Parse an annotation file and show summary
    export         Export annotations to Markdown, JSON, or plain text
    summary        Show library statistics
    detect-device  Scan for connected Kobo devices

For the web UI, run:
    streamlit run app/app.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(args_list)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="konotes",
        description="KoNotes -- Turn your Kobo highlights into structured, readable insight.",
    )
    parser.add_argument(
        "--version", action="version", version="konotes 0.5.0"
    )
    sub = parser.add_subparsers(dest="command")

    # parse
    p_parse = sub.add_parser("parse", help="Parse an annotation file and show summary")
    p_parse.add_argument("file", type=Path, help="Path to annotation file or KoboReader.sqlite")
    p_parse.set_defaults(func=_cmd_parse)

    # export
    p_export = sub.add_parser("export", help="Export annotations to a file")
    p_export.add_argument("file", type=Path, help="Path to annotation file or KoboReader.sqlite")
    p_export.add_argument(
        "-f", "--format",
        choices=["markdown", "json", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    p_export.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory (default: current directory)",
    )
    p_export.set_defaults(func=_cmd_export)

    # summary
    p_summary = sub.add_parser("summary", help="Show library statistics from a file")
    p_summary.add_argument("file", type=Path, help="Path to annotation file or KoboReader.sqlite")
    p_summary.set_defaults(func=_cmd_summary)

    # book
    p_book = sub.add_parser("book", help="Show detail for a specific book")
    p_book.add_argument("file", type=Path, help="Path to annotation file or KoboReader.sqlite")
    p_book.add_argument("title", help="Book title (or partial match)")
    p_book.set_defaults(func=_cmd_book)

    # export-html
    p_html = sub.add_parser("export-html", help="Export a static HTML reading site")
    p_html.add_argument("file", type=Path, help="Path to annotation file or KoboReader.sqlite")
    p_html.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory (default: ./konotes-site)",
    )
    p_html.set_defaults(func=_cmd_export_html)

    # detect-device
    p_detect = sub.add_parser("detect-device", help="Scan for connected Kobo devices")
    p_detect.set_defaults(func=_cmd_detect_device)

    return parser


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _load_books(path: Path):
    from parser.export_parsers import get_parser_for_extension
    from parser.normalizer import normalize

    if path.suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        from parser.sqlite_parser import parse_sqlite
        raw = parse_sqlite(path)
        source = "kobo_sqlite"
    else:
        parser = get_parser_for_extension(path.suffix)
        if parser is None:
            return None, f"Unsupported file type: {path.suffix}"
        content = path.read_text(encoding="utf-8", errors="replace")
        raw = parser.parse(content)
        source = parser.source_name

    return normalize(raw, source), None


def _cmd_parse(args: argparse.Namespace) -> int:
    from services.cli_output import console, print_banner, print_books, print_error, print_stats

    print_banner()

    path: Path = args.file
    if not path.exists():
        print_error(f"File not found: {path}")
        return 1

    if not _confirm_device_access(path):
        console.print("Aborted.")
        return 0

    books, err = _load_books(path)
    if err:
        print_error(err)
        return 1

    from services.stats import compute_stats
    stats = compute_stats(books)

    console.print()
    console.print(f"[bold]Parsed:[/bold] {path.name}")
    print_stats(stats)
    console.print()
    print_books(books)
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    from services.cli_output import console, print_banner, print_error, print_success

    print_banner()

    path: Path = args.file
    if not path.exists():
        print_error(f"File not found: {path}")
        return 1

    if not _confirm_device_access(path):
        console.print("Aborted.")
        return 0

    books, err = _load_books(path)
    if err:
        print_error(err)
        return 1

    if not books:
        print_error("No annotations found.")
        return 1

    from services.export_json import export_book_json
    from services.export_markdown import export_book_markdown
    from services.export_text import export_book_text

    export_fn = {
        "markdown": (export_book_markdown, ".md"),
        "json": (export_book_json, ".json"),
        "text": (export_book_text, ".txt"),
    }
    fn, ext = export_fn[args.format]
    out_dir: Path = args.output or Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    import re
    for book in books:
        safe_name = re.sub(r"[^\w\s-]", "", book.title).strip().replace(" ", "_")[:60]
        out_path = out_dir / f"{safe_name}_konotes{ext}"
        out_path.write_text(fn(book), encoding="utf-8")
        print_success(f"Exported: {out_path}")

    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    from services.cli_output import (
        console,
        print_banner,
        print_error,
        print_recent_activity,
        print_shelves,
        print_stats,
        print_top_authors,
    )

    print_banner()

    path: Path = args.file
    if not path.exists():
        print_error(f"File not found: {path}")
        return 1

    if not _confirm_device_access(path):
        console.print("Aborted.")
        return 0

    books, err = _load_books(path)
    if err:
        print_error(err)
        return 1

    from services.stats import compute_stats
    stats = compute_stats(books)

    console.print()
    print_stats(stats)
    print_top_authors(stats)

    if stats.books_by_highlight_count:
        console.print()
        console.print("[bold]Most Highlighted:[/bold]")
        for title, count in stats.books_by_highlight_count[:5]:
            if count > 0:
                console.print(f"  {title} -- {count} highlight(s)")

    # Shelf summary (SQLite only)
    if path.suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        from parser.sqlite_parser import extract_reading_sessions, extract_shelves

        shelves = extract_shelves(path)
        print_shelves(shelves)

        sessions = extract_reading_sessions(path)
        print_recent_activity(sessions)

    return 0


def _cmd_book(args: argparse.Namespace) -> int:
    from services.cli_output import console, print_banner, print_book_detail, print_error

    print_banner()

    path: Path = args.file
    if not path.exists():
        print_error(f"File not found: {path}")
        return 1

    if not _confirm_device_access(path):
        console.print("Aborted.")
        return 0

    books, err = _load_books(path)
    if err:
        print_error(err)
        return 1

    query = args.title.lower()
    matches = [b for b in books if query in b.title.lower()]

    if not matches:
        print_error(f"No books matching '{args.title}'")
        return 1

    for book in matches:
        print_book_detail(book)

    return 0


def _cmd_export_html(args: argparse.Namespace) -> int:
    from services.cli_output import console, print_banner, print_error, print_success

    print_banner()

    path: Path = args.file
    if not path.exists():
        print_error(f"File not found: {path}")
        return 1

    if not _confirm_device_access(path):
        console.print("Aborted.")
        return 0

    books, err = _load_books(path)
    if err:
        print_error(err)
        return 1

    if not books:
        print_error("No annotations found.")
        return 1

    from services.export_html import export_static_site
    from services.insight_feed import build_feed

    out_dir: Path = args.output or Path("konotes-site")
    cards = build_feed(books)

    # Load activity data if source is SQLite
    sessions = None
    snapshots = None
    if path.suffix == ".sqlite" or path.name == "KoboReader.sqlite":
        from parser.sqlite_parser import (
            extract_progress_snapshots,
            extract_reading_sessions,
        )

        try:
            sessions = extract_reading_sessions(path)
        except Exception:
            sessions = []
        try:
            snapshots = extract_progress_snapshots(path)
        except Exception:
            snapshots = []

    export_static_site(
        books, out_dir, insight_cards=cards,
        sessions=sessions, snapshots=snapshots,
    )
    print_success(f"Static site exported to: {out_dir}/")
    console.print(f"  Open {out_dir / 'index.html'} in a browser to view.")
    return 0


def _cmd_detect_device(args: argparse.Namespace) -> int:
    from parser.device_detection import detect_devices
    from services.cli_output import console, print_banner, print_warning

    print_banner()
    console.print()

    devices = detect_devices()
    if not devices:
        print_warning("No Kobo devices detected. Make sure your device is connected via USB.")
        return 0

    for dev in devices:
        console.print(f"[bold]{dev.label}[/bold]")
        console.print(f"  Mount: {dev.mount_point}")
        console.print(f"  Database: {dev.db_path}")
        console.print()

    return 0


def _confirm_device_access(path: Path) -> bool:
    """Prompt the user for confirmation before reading data from a Kobo device."""
    # Only prompt for paths that look like a mounted Kobo device
    path_str = str(path.resolve())
    if "/Volumes/" not in path_str and "/media/" not in path_str and "/mnt/" not in path_str:
        return True

    from services.cli_output import console
    console.print()
    console.print("[bold]A Kobo device was detected.[/bold]")
    console.print(f"  Path: {path}")
    answer = console.input("\nDo you want to read local data from this device? (y/n) ")
    return answer.strip().lower() in ("y", "yes")


if __name__ == "__main__":
    raise SystemExit(main())
