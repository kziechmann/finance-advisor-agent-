"""Command-line entrypoint: `python -m finance_agent.cli run`.

Phase 0 pipeline: load latest holdings snapshot -> compute drift against
target allocation -> render Markdown report -> persist snapshot + report
record to the local SQLite database. No network access anywhere in this
path.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from finance_agent.config import load_target_allocation
from finance_agent.ingestion import load_latest_snapshot
from finance_agent.rebalance import compute_drift
from finance_agent.report import render_markdown_report
from finance_agent.storage import init_db, record_report, save_holdings_snapshot


def run(statements_dir: Path, config_path: Path, db_path: Path, reports_dir: Path) -> Path:
    targets, band = load_target_allocation(config_path)
    holdings = load_latest_snapshot(statements_dir)
    drift_results = compute_drift(holdings, targets, band)

    as_of_date = holdings[0].as_of_date
    generated_at = datetime.now()
    report_text = render_markdown_report(drift_results, as_of_date=as_of_date, generated_at=generated_at)

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"report_{as_of_date.isoformat()}.md"
    report_path.write_text(report_text, encoding="utf-8")

    conn = init_db(db_path)
    try:
        save_holdings_snapshot(conn, holdings)
        flagged_count = sum(1 for r in drift_results if r.exceeds_band)
        record_report(conn, file_path=report_path, as_of_date=as_of_date, flagged_count=flagged_count, generated_at=generated_at)
    finally:
        conn.close()

    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="finance-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Ingest latest statements and generate a rebalancing report")
    run_parser.add_argument("--statements-dir", type=Path, default=Path("statements"))
    run_parser.add_argument("--config", type=Path, default=Path("config/target_allocation.yaml"))
    run_parser.add_argument("--db", type=Path, default=Path("data/finance.db"))
    run_parser.add_argument("--reports-dir", type=Path, default=Path("reports"))

    args = parser.parse_args()

    if args.command == "run":
        report_path = run(args.statements_dir, args.config, args.db, args.reports_dir)
        print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
