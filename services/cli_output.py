"""Rich console output helpers for the KoNotes CLI."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models.book import Book
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


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_error(message: str) -> None:
    console.print(f"[red]{message}[/red]")


def print_warning(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")
