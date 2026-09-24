"""SQLite storage for holdings snapshots and report history.

Phase 0 uses plain `sqlite3` from the standard library. The spec (docs/spec.md
section 5.2) calls for SQLCipher-encrypted-at-rest storage; that's deferred
until the project has a real dependency on it, on the assumption that
full-disk encryption is your baseline in the meantime. Do not put this
database anywhere synced to a consumer cloud drive unencrypted.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from finance_agent.models import HoldingRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    shares REAL NOT NULL,
    price REAL NOT NULL,
    market_value REAL NOT NULL,
    cost_basis REAL NOT NULL,
    as_of_date TEXT NOT NULL,
    source_file TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    file_path TEXT NOT NULL,
    flagged_count INTEGER NOT NULL
);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def save_holdings_snapshot(conn: sqlite3.Connection, holdings: list[HoldingRow]) -> None:
    conn.executemany(
        """
        INSERT INTO holdings_snapshots
            (account_name, account_type, ticker, asset_class, shares, price,
             market_value, cost_basis, as_of_date, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                h.account_name,
                h.account_type,
                h.ticker,
                h.asset_class,
                h.shares,
                h.price,
                h.market_value,
                h.cost_basis,
                h.as_of_date.isoformat(),
                h.source_file,
            )
            for h in holdings
        ],
    )
    conn.commit()


def record_report(
    conn: sqlite3.Connection,
    *,
    file_path: Path,
    as_of_date: date,
    flagged_count: int,
    generated_at: datetime | None = None,
) -> None:
    generated_at = generated_at or datetime.now()
    conn.execute(
        "INSERT INTO reports (generated_at, as_of_date, file_path, flagged_count) VALUES (?, ?, ?, ?)",
        (generated_at.isoformat(timespec="seconds"), as_of_date.isoformat(), str(file_path), flagged_count),
    )
    conn.commit()
