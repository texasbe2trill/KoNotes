"""Tests for schema utility helpers."""
from __future__ import annotations

import sqlite3

import pytest

from utils.schema import column_exists, safe_select, table_exists


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE books (id INTEGER, title TEXT, author TEXT)")
    conn.execute("INSERT INTO books VALUES (1, 'Dune', 'Frank Herbert')")
    conn.execute("INSERT INTO books VALUES (2, 'Foundation', 'Isaac Asimov')")
    yield conn
    conn.close()


class TestTableExists:
    def test_existing_table(self, db):
        assert table_exists(db, "books") is True

    def test_missing_table(self, db):
        assert table_exists(db, "nonexistent") is False


class TestColumnExists:
    def test_existing_column(self, db):
        assert column_exists(db, "books", "title") is True

    def test_missing_column(self, db):
        assert column_exists(db, "books", "isbn") is False

    def test_missing_table(self, db):
        assert column_exists(db, "nonexistent", "id") is False


class TestSafeSelect:
    def test_all_columns_exist(self, db):
        rows = safe_select(db, "books", ["id", "title", "author"])
        assert len(rows) == 2

    def test_some_columns_missing(self, db):
        rows = safe_select(db, "books", ["id", "title", "isbn"])
        assert len(rows) == 2
        # isbn was dropped, so rows have id and title only

    def test_missing_table(self, db):
        rows = safe_select(db, "nonexistent", ["id"])
        assert rows == []

    def test_where_clause(self, db):
        rows = safe_select(db, "books", ["id", "title"], where="id = ?", params=(1,))
        assert len(rows) == 1

    def test_order_by(self, db):
        rows = safe_select(db, "books", ["title"], order_by="title ASC")
        assert rows[0]["title"] == "Dune"
