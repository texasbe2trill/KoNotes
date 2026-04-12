"""Schema-aware helpers for safely querying KoboReader.sqlite.

The Kobo database schema varies across device, firmware, and book/source type.
These helpers let callers inspect the schema at runtime and build queries from
only the columns that actually exist, avoiding crashes on any database variant.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Return *True* if *table* exists in the database."""
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    )
    return cur.fetchone() is not None


def get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names for *table*, or an empty set if missing."""
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
        return {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return *True* if *column* exists on *table*."""
    return column in get_table_columns(conn, table)


def select_existing_columns(
    conn: sqlite3.Connection,
    table: str,
    requested: list[str],
) -> list[str]:
    """Filter *requested* to only columns that actually exist on *table*.

    Preserves the order of *requested*.
    """
    available = get_table_columns(conn, table)
    return [c for c in requested if c in available]


def inspect_schema(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return a mapping of ``{table_name: [column, ...]}`` for every table."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    schema: dict[str, list[str]] = {}
    for (name,) in cur.fetchall():
        cols = conn.execute(f"PRAGMA table_info({name})")  # noqa: S608
        schema[name] = [row[1] for row in cols.fetchall()]
    return schema


# ---------------------------------------------------------------------------
# Safe query execution
# ---------------------------------------------------------------------------


def safe_execute(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    """Execute *query* and return rows, or an empty list on error.

    Logs a debug message when the query fails (e.g. missing column/table).
    """
    try:
        return conn.execute(query, params).fetchall()
    except sqlite3.OperationalError as exc:
        logger.debug("safe_execute failed: %s — %s", exc, query[:120])
        return []


def safe_select(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    *,
    where: str = "",
    params: tuple[Any, ...] = (),
    order_by: str = "",
) -> list[sqlite3.Row]:
    """Execute a SELECT only for columns that actually exist on *table*.

    Missing columns are silently dropped from the projection.
    Returns an empty list if the table itself does not exist.
    """
    if not table_exists(conn, table):
        return []

    available = select_existing_columns(conn, table, columns)
    if not available:
        return []

    sql = f"SELECT {', '.join(available)} FROM {table}"  # noqa: S608
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"

    return safe_execute(conn, sql, params)
