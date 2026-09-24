"""Deterministic CSV statement ingestion.

Phase 0 supports a hand-exported/hand-corrected CSV holdings format rather
than parsing brokerage PDFs directly: every brokerage lays out its PDF
tables differently, and a parser built without real sample statements to
test against would silently misparse rather than fail loudly — worse than
not parsing at all for financial data. See docs/spec.md section 5.1.

Expected CSV columns (header required, any order):
    account_name, account_type, ticker, asset_class, shares, price,
    market_value, cost_basis

The as-of date is taken from the filename, following the same convention
as the bankstatement_script project: the file must contain a YYYY-MM-DD
date, e.g. `schwab-brokerage_holdings_2026-06-30.csv`.
"""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from finance_agent.models import HoldingRow

REQUIRED_COLUMNS = (
    "account_name",
    "account_type",
    "ticker",
    "asset_class",
    "shares",
    "price",
    "market_value",
    "cost_basis",
)

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


class IngestionError(ValueError):
    """A statement file could not be parsed; never silently drop or guess."""


def parse_date_from_filename(path: Path) -> date:
    match = _DATE_RE.search(path.name)
    if not match:
        raise IngestionError(
            f"{path.name}: filename must contain a date as YYYY-MM-DD "
            "(e.g. 'schwab_holdings_2026-06-30.csv')"
        )
    return date.fromisoformat(match.group(1))


def _parse_float(raw: str, *, field: str, row_num: int, path: Path) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise IngestionError(
            f"{path.name}, row {row_num}: '{field}' is not a number: {raw!r}"
        ) from exc


def load_holdings_csv(path: Path) -> list[HoldingRow]:
    as_of_date = parse_date_from_filename(path)

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise IngestionError(
                f"{path.name}: missing required column(s): {', '.join(missing)}"
            )

        rows: list[HoldingRow] = []
        for row_num, raw_row in enumerate(reader, start=2):  # header is line 1
            rows.append(
                HoldingRow(
                    account_name=raw_row["account_name"].strip(),
                    account_type=raw_row["account_type"].strip(),
                    ticker=raw_row["ticker"].strip(),
                    asset_class=raw_row["asset_class"].strip(),
                    shares=_parse_float(raw_row["shares"], field="shares", row_num=row_num, path=path),
                    price=_parse_float(raw_row["price"], field="price", row_num=row_num, path=path),
                    market_value=_parse_float(
                        raw_row["market_value"], field="market_value", row_num=row_num, path=path
                    ),
                    cost_basis=_parse_float(
                        raw_row["cost_basis"], field="cost_basis", row_num=row_num, path=path
                    ),
                    as_of_date=as_of_date,
                    source_file=path.name,
                )
            )
    return rows


def load_latest_snapshot(statements_dir: Path) -> list[HoldingRow]:
    """Load every CSV in `statements_dir` and keep only the most recent date's rows.

    A directory of monthly exports accumulates history; a rebalancing report
    should always act on the latest snapshot, not a mix of dates.
    """
    csv_paths = sorted(statements_dir.glob("*.csv"))
    if not csv_paths:
        raise IngestionError(f"No CSV statement files found in {statements_dir}")

    all_rows: list[HoldingRow] = []
    for path in csv_paths:
        all_rows.extend(load_holdings_csv(path))

    latest_date = max(row.as_of_date for row in all_rows)
    return [row for row in all_rows if row.as_of_date == latest_date]
