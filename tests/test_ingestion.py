from pathlib import Path

import pytest

from finance_agent.ingestion import IngestionError, load_holdings_csv, load_latest_snapshot

VALID_CSV = """account_name,account_type,ticker,asset_class,shares,price,market_value,cost_basis
Brokerage,taxable,VTI,us_equity,10,250.00,2500.00,2000.00
"""


def test_load_holdings_csv_parses_valid_file(tmp_path: Path):
    path = tmp_path / "holdings_2026-06-30.csv"
    path.write_text(VALID_CSV, encoding="utf-8")

    rows = load_holdings_csv(path)

    assert len(rows) == 1
    assert rows[0].ticker == "VTI"
    assert rows[0].market_value == 2500.00
    assert rows[0].as_of_date.isoformat() == "2026-06-30"
    assert rows[0].source_file == "holdings_2026-06-30.csv"


def test_load_holdings_csv_rejects_missing_date_in_filename(tmp_path: Path):
    path = tmp_path / "holdings.csv"
    path.write_text(VALID_CSV, encoding="utf-8")

    with pytest.raises(IngestionError, match="must contain a date"):
        load_holdings_csv(path)


def test_load_holdings_csv_rejects_missing_column(tmp_path: Path):
    path = tmp_path / "holdings_2026-06-30.csv"
    path.write_text("account_name,ticker\nBrokerage,VTI\n", encoding="utf-8")

    with pytest.raises(IngestionError, match="missing required column"):
        load_holdings_csv(path)


def test_load_holdings_csv_rejects_non_numeric_value(tmp_path: Path):
    path = tmp_path / "holdings_2026-06-30.csv"
    bad_csv = VALID_CSV.replace("2500.00", "N/A")
    path.write_text(bad_csv, encoding="utf-8")

    with pytest.raises(IngestionError, match="row 2"):
        load_holdings_csv(path)


def test_load_latest_snapshot_keeps_only_most_recent_date(tmp_path: Path):
    (tmp_path / "holdings_2026-05-31.csv").write_text(VALID_CSV, encoding="utf-8")
    (tmp_path / "holdings_2026-06-30.csv").write_text(VALID_CSV, encoding="utf-8")

    rows = load_latest_snapshot(tmp_path)

    assert len(rows) == 1
    assert all(r.as_of_date.isoformat() == "2026-06-30" for r in rows)


def test_load_latest_snapshot_raises_on_empty_directory(tmp_path: Path):
    with pytest.raises(IngestionError, match="No CSV statement files"):
        load_latest_snapshot(tmp_path)
