"""Tests for chat book-chip matcher."""
from __future__ import annotations

from app.components.chat_book_chips import find_referenced_books
from models.book import Book


def _book(book_id: str, title: str, author: str = "") -> Book:
    return Book(id=book_id, title=title, author=author, source="test")


def test_returns_empty_for_empty_text():
    assert find_referenced_books("", [_book("1", "Dune")]) == []


def test_returns_empty_when_no_books():
    assert find_referenced_books("I love Dune.", []) == []


def test_finds_single_book_by_title():
    books = [_book("1", "Dune"), _book("2", "Foundation")]
    result = find_referenced_books("You should revisit Dune next.", books)
    assert [b.id for b in result] == ["1"]


def test_case_insensitive_match():
    books = [_book("1", "The Hobbit")]
    result = find_referenced_books("the HOBBIT was your most highlighted.", books)
    assert [b.id for b in result] == ["1"]


def test_prefers_longer_title_when_overlapping():
    """A mention of "The Lord of the Rings" should not also match "The Lord"."""
    books = [
        _book("short", "The Lord"),
        _book("long", "The Lord of the Rings"),
    ]
    result = find_referenced_books(
        "Have you finished The Lord of the Rings yet?", books
    )
    assert [b.id for b in result] == ["long"]


def test_skips_short_titles():
    """Very short titles are ignored to prevent false positives."""
    books = [_book("1", "It"), _book("2", "Foundation")]
    result = find_referenced_books("It is a great book; Foundation too.", books)
    assert [b.id for b in result] == ["2"]


def test_returns_books_in_order_of_appearance():
    books = [_book("1", "Foundation"), _book("2", "Dune")]
    result = find_referenced_books("Try Dune before Foundation.", books)
    assert [b.id for b in result] == ["2", "1"]


def test_caps_results_at_max_chips():
    books = [_book(str(i), f"Title Number {i:02d}") for i in range(10)]
    text = " ".join(f"Title Number {i:02d}" for i in range(10))
    result = find_referenced_books(text, books)
    assert len(result) <= 4


def test_each_book_matched_only_once():
    books = [_book("1", "Dune")]
    result = find_referenced_books("Dune Dune Dune.", books)
    assert [b.id for b in result] == ["1"]


def test_no_crash_on_books_with_empty_title():
    books = [_book("1", ""), _book("2", "Dune")]
    result = find_referenced_books("Reading Dune.", books)
    assert [b.id for b in result] == ["2"]
