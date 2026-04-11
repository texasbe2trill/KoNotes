"""Schema-aware helpers for safely querying KoboReader.sqlite.

The Kobo database schema varies across firmware versions. These helpers let
callers check for table/column existence before running queries, avoiding
crashes on older or newer devices.
"""
from __future__ import annotations

import sqlite3


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    )
    return cur.fetchone() is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
        columns = {row[1] for row in cur.fetchall()}
        return column in columns
    except sqlite3.OperationalError:
        return False


def safe_select(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    *,
    where: str = "",
    params: tuple = (),
    order_by: str = "",
) -> list[sqlite3.Row]:
    """Execute a SELECT only for columns that actually exist on *table*.

    Missing columns are silently dropped from the projection.
    Returns an empty list if the table itself does not exist.
    """
    if not table_exists(conn, table):
        return []

    available = [c for c in columns if column_exists(conn, table, c)]
    if not available:
        return []

    sql = f"SELECT {', '.join(available)} FROM {table}"  # noqa: S608
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"

    cur = conn.execute(sql, params)
    return cur.fetchall()
