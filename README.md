# Personal Finance Advisor Agent

A local-only tool that reads your investment statements, tracks asset
allocation over time, and produces a periodic Markdown report flagging when
you've drifted from your target allocation — using a rule-based rebalancing
method, not a black box.

**No cloud calls on your data. No automated trades, ever.** See
[`docs/spec.md`](docs/spec.md) for the full architecture, threat model, and
roadmap.

## Status: Phase 0 (deterministic core)

Ingestion, storage, and the rebalancing-band math are implemented and
tested. There is no LLM and no network access anywhere in the current code
— see `docs/spec.md` section 11 for what's next.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure your target allocation

```bash
cp config/target_allocation.example.yaml config/target_allocation.yaml
```

Edit `config/target_allocation.yaml` with your own asset classes and target
percentages. Asset class names must match the `asset_class` column you use
in your statement CSVs.

## Add your holdings

Export your holdings from each brokerage as CSV, or fill one in by hand,
into `statements/`. Required columns:

```
account_name, account_type, ticker, asset_class, shares, price, market_value, cost_basis
```

The filename must contain a date as `YYYY-MM-DD`, e.g.
`schwab_holdings_2026-06-30.csv`. See `statements/sample_holdings_2026-06-30.csv`
for a worked example. `statements/` is gitignored except for that sample —
your real holdings never get committed.

## Run

```bash
python -m finance_agent.cli run
```

This reads the latest snapshot in `statements/`, computes drift against
your target allocation using the 5/25 rebalancing-band rule, and writes a
report to `reports/report_<date>.md`. Holdings and report metadata are
recorded in `data/finance.db` (gitignored).

## Test

```bash
pytest
```

## Sensitive data

`statements/`, `data/`, and `reports/` are gitignored by default — do not
remove those entries. Assume full-disk encryption on the machine this runs
on; see `docs/spec.md` section 7 for the fuller security checklist as the
project grows past Phase 0.
