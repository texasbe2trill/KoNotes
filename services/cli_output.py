"""Rich console output helpers for the KoNotes CLI."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models.activity import ReadingSession
from models.book import Book
from models.shelf import Shelf
from services.stats import LibraryStats

console = Console()


def print_banner() -> None:
    console.print(
        Panel(
            "[bold]KoNotes[/bold]\n"
            "Turn your Kobo highlights and reading data into structured, readable insight.",
            border_style="blue",
            expand=False,
        )
    )


def print_stats(stats: LibraryStats) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column(justify="right")
    table.add_row("Books", str(stats.total_books))
    table.add_row("Annotations", str(stats.total_annotations))
    table.add_row("Highlights", str(stats.total_highlights))
    table.add_row("Notes", str(stats.total_notes))
    table.add_row("In Progress", str(stats.books_in_progress))
    table.add_row("Completed", str(stats.books_completed))
    table.add_row("Avg HL/Book", str(stats.avg_highlights_per_book))
    console.print(table)


def print_books(books: list[Book]) -> None:
    table = Table(title="Books", show_lines=True)
    table.add_column("Title", style="bold")
    table.add_column("Author")
    table.add_column("Highlights", justify="right")
    table.add_column("Notes", justify="right")
    table.add_column("Progress", justify="right")

    for book in books:
        h = sum(1 for a in book.annotations if a.kind == "highlight")
        n = sum(1 for a in book.annotations if a.kind == "note")
        progress = f"{book.read_percent:.0f}%" if book.read_percent is not None else "--"
        table.add_row(
            book.title,
            book.author or "--",
            str(h),
            str(n),
            progress,
        )

    console.print(table)


def print_book_detail(book: Book) -> None:
    """Print detailed info for a single book."""
    console.print()
    console.print(f"[bold]{book.title}[/bold]")
    if book.author:
        console.print(f"  Author: {book.author}")
    if book.series:
        console.print(f"  Series: {book.series}")
    if book.publisher:
        console.print(f"  Publisher: {book.publisher}")
    if book.isbn:
        console.print(f"  ISBN: {book.isbn}")
    if book.language:
        console.print(f"  Language: {book.language}")
    if book.read_percent is not None:
        console.print(f"  Progress: {book.read_percent:.0f}%")
    if book.shelves:
        console.print(f"  Shelves: {', '.join(book.shelves)}")
    if book.date_last_read:
        console.print(f"  Last Read: {book.date_last_read.strftime('%Y-%m-%d')}")

    h = sum(1 for a in book.annotations if a.kind == "highlight")
    n = sum(1 for a in book.annotations if a.kind == "note")
    console.print(f"  Highlights: {h}  Notes: {n}")

    if book.annotations:
        console.print()
        for ann in book.annotations[:10]:
            kind_label = "[yellow]HL[/yellow]" if ann.kind == "highlight" else "[blue]NT[/blue]"
            text_preview = ann.text[:120] + ("..." if len(ann.text) > 120 else "")
            console.print(f"  {kind_label} {text_preview}")
        if len(book.annotations) > 10:
            console.print(f"  ... and {len(book.annotations) - 10} more")


def print_top_authors(stats: LibraryStats) -> None:
    if not stats.top_authors:
        return
    console.print()
    console.print("[bold]Top Authors:[/bold]")
    for author, count in stats.top_authors[:5]:
        console.print(f"  {author} -- {count} book(s)")


def print_shelves(shelves: list[Shelf]) -> None:
    if not shelves:
        return
    console.print()
    console.print("[bold]Shelves:[/bold]")
    for shelf in shelves:
        console.print(f"  {shelf.name} ({shelf.book_count} book(s))")


def print_recent_activity(sessions: list[ReadingSession]) -> None:
    if not sessions:
        return
    console.print()
    console.print("[bold]Recent Reading Sessions:[/bold]")
    for s in sessions[:5]:
        console.print(
            f"  {s.book_title} -- {s.start_time.strftime('%Y-%m-%d')} "
            f"({s.duration_minutes:.0f} min)"
        )


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_error(message: str) -> None:
    console.print(f"[red]{message}[/red]")


def print_warning(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")
