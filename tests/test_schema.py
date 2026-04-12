"""Tests for schema utility helpers."""
from __future__ import annotations

import sqlite3

import pytest

from utils.schema import (
    column_exists,
    get_table_columns,
    inspect_schema,
    safe_execute,
    safe_select,
    select_existing_columns,
    table_exists,
)


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


class TestGetTableColumns:
    def test_returns_column_set(self, db):
        cols = get_table_columns(db, "books")
        assert cols == {"id", "title", "author"}

    def test_missing_table(self, db):
        assert get_table_columns(db, "nonexistent") == set()


class TestColumnExists:
    def test_existing_column(self, db):
        assert column_exists(db, "books", "title") is True

    def test_missing_column(self, db):
        assert column_exists(db, "books", "isbn") is False

    def test_missing_table(self, db):
        assert column_exists(db, "nonexistent", "id") is False


class TestSelectExistingColumns:
    def test_all_present(self, db):
        result = select_existing_columns(db, "books", ["id", "title", "author"])
        assert result == ["id", "title", "author"]

    def test_some_missing(self, db):
        result = select_existing_columns(db, "books", ["id", "title", "isbn", "publisher"])
        assert result == ["id", "title"]

    def test_preserves_order(self, db):
        result = select_existing_columns(db, "books", ["author", "id"])
        assert result == ["author", "id"]

    def test_all_missing(self, db):
        result = select_existing_columns(db, "books", ["isbn", "publisher"])
        assert result == []

    def test_missing_table(self, db):
        result = select_existing_columns(db, "nonexistent", ["id"])
        assert result == []


class TestInspectSchema:
    def test_returns_schema(self, db):
        schema = inspect_schema(db)
        assert "books" in schema
        assert "id" in schema["books"]
        assert "title" in schema["books"]

    def test_empty_db(self):
        conn = sqlite3.connect(":memory:")
        schema = inspect_schema(conn)
        assert schema == {}
        conn.close()

    def test_multiple_tables(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE a (x INTEGER)")
        conn.execute("CREATE TABLE b (y TEXT, z REAL)")
        schema = inspect_schema(conn)
        assert set(schema.keys()) == {"a", "b"}
        assert schema["a"] == ["x"]
        assert schema["b"] == ["y", "z"]
        conn.close()


class TestSafeExecute:
    def test_valid_query(self, db):
        rows = safe_execute(db, "SELECT * FROM books")
        assert len(rows) == 2

    def test_bad_query_returns_empty(self, db):
        rows = safe_execute(db, "SELECT * FROM nonexistent")
        assert rows == []

    def test_bad_column_returns_empty(self, db):
        rows = safe_execute(db, "SELECT isbn FROM books")
        assert rows == []

    def test_with_params(self, db):
        rows = safe_execute(db, "SELECT * FROM books WHERE id = ?", (1,))
        assert len(rows) == 1


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
        assert rows[0]["title"] == "Dune"
