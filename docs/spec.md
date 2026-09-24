# Personal Finance Advisor Agent — Technical Spec (v0.1)

**Scope:** local-only personal tool, no cloud calls on sensitive data, no trade execution.

## 1. Purpose

A locally-run system that ingests your investment account statements (manually exported, dropped into a folder), tracks holdings and asset allocation over time, and produces a **periodic report** — like a once-a-quarter meeting with an advisory team — covering:

- Current portfolio composition vs. your target allocation
- Drift/rebalancing signals using a rule-based band method
- Relevant market/macro context for the asset classes you hold
- Tax-awareness notes (loss-harvesting candidates, asset location)
- A plain-English narrative summary, written by a local LLM, grounded entirely in numbers computed by deterministic code

## 2. Non-Goals (hard boundaries)

- **No automated trade execution, ever.** No brokerage API integration for placing orders. It reads statements you export; it never writes to an account.
- **No cloud LLM calls on sensitive data.** Account numbers, balances, holdings never leave your machine.
- **Not a fiduciary / registered investment adviser.** Output is informational only, for your own decision-making — see §10.
- **Not a real-time system.** Periodic batch analysis (monthly/quarterly), not continuous monitoring — deliberately reduces both attack surface and the temptation to check/react too often (research consistently shows frequent rebalancing checks correlate with worse investor behavior, not better outcomes).
- No multi-user support, no web-exposed service (localhost only, if a UI is ever added).

## 3. Threat Model

**Assets to protect:** account numbers, balances, holdings, transaction history, your identity tied to net worth data.

**Adversaries / failure modes considered:**

1. A dependency or misconfigured component phones home with statement data (accidental telemetry, a library with a "call home" default, a misrouted API call).
2. Malicious or just-untrustworthy content in *ingested text* (news articles, RSS feeds) attempts indirect prompt injection to make an agent exfiltrate data or take an unintended action.
3. Local compromise (malware, another user on a shared machine, a stolen unlocked laptop) reads plaintext statement data at rest.
4. The LLM hallucinates numbers or reasoning and you act on bad information without realizing it's synthesized rather than computed.
5. Supply-chain risk from open-source packages (typosquatting, compromised releases).

**Core design response:** split the system into two trust zones with a hard network boundary between them, and never let the LLM do arithmetic on your actual money.

## 4. Architecture Overview

```
                    +-------------------------------------------+
                    |  ZONE A -- Sensitive, NO network egress    |
                    |                                             |
  statements/  ---> |  1. Ingestion & Parsing (deterministic)    |
  (manual drop)     |  2. Encrypted local storage (SQLite)       |
                    |  3. Deterministic analytics                 |
                    |     (allocation, drift, tax flags)          |
                    |  4. Local LLM: narrative/synthesis only     |
                    |     (reads numbers, never computes them)    |
                    +-----------------+---------------------------+
                                      |  structured, schema-validated
                                      |  request: tickers + asset classes only
                                      v
                    +-------------------------------------------+
                    |  ZONE B -- Public data, network allowlist   |
                    |                                             |
                    |  5. Market data fetch (prices, tickers)     |
                    |  6. News/macro fetch (headlines only)       |
                    |  7. Local LLM: summarizes market context     |
                    |     (treats fetched text as untrusted        |
                    |      DATA, never instructions)                |
                    +-----------------+---------------------------+
                                      |  structured summary back
                                      v
                    +-------------------------------------------+
                    |  Orchestrator (Zone A side)                 |
                    |  merges deterministic analysis + market      |
                    |  context -> final Markdown/HTML report         |
                    |  with disclaimers, written to disk              |
                    +-------------------------------------------+
```

Zone A never has a route to the internet — enforced at the OS/container level (not just "the app doesn't call fetch"), e.g. a Docker container run with `--network none`, or a dedicated network namespace / firewall rule set that drops all egress except loopback. Zone B runs in its own container with an explicit domain allowlist (market data provider + one news source), nothing else. The only channel between zones is a narrow, schema-validated function call — Zone A sends ticker symbols/asset classes, Zone B returns prices and headline text, no free-form back-channel.

## 5. Components

### 5.1 Ingestion & Parsing (Zone A, deterministic)

- Input: statements you manually export from your brokerage(s) into a `statements/` folder.
- **Phase 0 ships a CSV-based ingestion path, not a PDF parser.** Every brokerage lays out its statement PDFs differently, and a parser built without real sample statements to test against would silently misparse a holdings table rather than fail loudly — worse than not parsing at all for financial data. A CSV export (most brokerages offer one) or a hand-corrected CSV is the Phase 0 supported input; PDF table extraction is future work once real statement samples are available to build and test parsers against (see `src/finance_agent/ingestion.py` for the exact format).
- All extraction is deterministic code, not the LLM. The LLM never reads raw statement files directly for numbers.

### 5.2 Storage

- SQLite as the single-file store (holdings snapshots, transactions, report history). Phase 0 uses plain `sqlite3`; the spec's target is `SQLCipher` (transparent AES-256 encryption at the file level) as defense-in-depth alongside full-disk encryption, deferred until there's a concrete need to add the dependency.
- If RAG over past reports/commentary is added later, use `sqlite-vec` — an embedded vector index inside the same SQLite file, no separate DB server to run or secure.

### 5.3 Local LLM Runtime (not yet implemented — Phase 1)

- **Ollama** as the runtime — simplest operational model, doesn't log prompts by default, good structured-output support.
- For an 8–24GB VRAM GPU: **Qwen3-14B-Instruct** (Q4_K_M, ~9–10GB VRAM) for the narrative/synthesis agent; **DeepSeek-R1-Distill-Qwen-32B** or **Qwen3-32B** as an optional reasoning-heavy upgrade if VRAM allows.
- Structured output (JSON schema) enforced wherever an LLM response would feed back into code.

### 5.4 Agent Roles ("the advisor team", Phase 1+)

A small, fixed, auditable pipeline rather than an open-ended autonomous agent:

1. **Portfolio Analyst** — narrates the deterministic drift table (§5.5/9).
2. **Rebalancing/Risk Agent** — the deterministic band-rule computation itself (implemented now, in `rebalance.py`); no LLM in the math path.
3. **Tax-Awareness Agent** — flags loss-harvesting candidates and asset-location notes (Phase 3).
4. **Market/Macro Research Agent** (Zone B) — summarizes recent price/news context for held tickers; all fetched text treated as untrusted data (Phase 2).
5. **Orchestrator/Lead** — merges 1–4 into the final report with the standing disclaimer; has no tools beyond "assemble and write file".

### 5.5 Portfolio Analytics

- Default method: **rule-based rebalancing bands** (5/25 rule) against a target allocation you configure (`config/target_allocation.yaml`). Research is consistent that banded rebalancing performs comparably to more complex optimization methods for long-term buy-and-hold investors, with fewer taxable events than pure calendar rebalancing, and is far more transparent/auditable.
- Optional, later: `PyPortfolioOpt` or `Riskfolio-Lib` for efficient-frontier/risk-parity analysis as *supplementary* commentary, not the primary rebalancing trigger.
- All portfolio math is in `src/finance_agent/rebalance.py`, unit-tested, and is the only source of numbers that reach a report.

### 5.6 Market Data & News (Zone B, Phase 2)

- Prices/history: `yfinance` (free, ticker-based, no account data crosses this boundary).
- News: a single vetted source to start; explicit allowlist, not a discovered/dynamic source.

### 5.7 Report Output

- Markdown as the source of truth (`src/finance_agent/report.py`), optionally rendered to HTML/PDF later.
- No email/network delivery in Phase 0/1 — every extra egress point is a deliberate, scoped addition, not a default.

### 5.8 Scheduling

- OS-level `cron`/`systemd` timer, not an embedded scheduler daemon. Default cadence: monthly or quarterly.

## 6. Data Model

- `holdings_snapshots` — account_name, account_type, ticker, asset_class, shares, price, market_value, cost_basis, as_of_date, source_file
- `reports` — generated_at, as_of_date, file_path, flagged_count
- (Phase 3+) `transactions`, `target_allocation` history for tracking deferred rebalancing over time

## 7. Security Controls Checklist

- [ ] Zone A container/process has zero network egress, enforced at OS/container level (Phase 2, when Zone B is introduced).
- [ ] Zone B container/process has an explicit domain allowlist; default-deny everything else (Phase 2).
- [ ] SQLCipher (or equivalent) encryption at rest for the data file (deferred; full-disk encryption assumed as interim baseline).
- [ ] Raw statement files processed and not retained in plaintext long-term beyond what you keep in `statements/` yourself.
- [ ] Secrets (any Zone B API keys) in OS keychain or `chmod 600` file, excluded via `.gitignore`.
- [x] `.gitignore` excludes `statements/`, `data/`, `reports/`, and secret files by default.
- [ ] All LLM-facing retrieved content (news/RSS text) wrapped in explicit untrusted-data delimiters (Phase 2).
- [x] No agent has a tool that performs an irreversible or external action — Phase 0/1 has no network or trade-execution capability at all.
- [x] Deterministic module (`rebalance.py`) is the sole source of computed numbers; ingestion fails loudly on malformed/missing data rather than guessing.
- [ ] Audit log of each run (Phase 3+).

## 8. Tech Stack Summary

| Layer | Choice | Status |
|---|---|---|
| Language | Python 3.11+ | implemented |
| Statement parsing | CSV (deterministic) | implemented; PDF extraction deferred |
| Storage | SQLite (`sqlite3` stdlib) | implemented; SQLCipher deferred |
| Portfolio math | Hand-written module, 5/25 band rule | implemented |
| Report | Markdown | implemented |
| Scheduling | cron/systemd timer | not yet wired up |
| LLM runtime | Ollama + Qwen3-14B | Phase 1 |
| Orchestration | Hand-rolled pipeline (no framework) | Phase 1 |
| Market data | yfinance | Phase 2 |
| News | one vetted source | Phase 2 |
| Isolation | Docker/network namespaces, per-zone policy | Phase 2 |

## 9. Investment Methodology

- Target allocation defined by you, in config, not inferred by the LLM.
- Default rebalancing trigger: **5/25 rule** — rebalance an asset class when it's off target by an absolute 5 percentage points (for allocations ≥20%) or a relative 25% (for smaller allocations), whichever applies.
- Prefer directing new contributions toward underweight asset classes over selling overweight ones in taxable accounts, to minimize realized gains/taxable events.
- No market-timing or tactical asset-allocation logic — supports a long-term, strategic-allocation approach, not short-term prediction.

## 10. Legal & Disclaimer Posture

- Personal tool, not a product offered to others, receives no compensation for advice — key factors distinguishing it from a registered-investment-adviser context. It should nonetheless behave as if held to that standard:
  - Every generated report opens with a standing disclaimer (see `report.py::DISCLAIMER`).
  - No imperative "buy X / sell Y" language — framed as "target allocation suggests..." with the reasoning shown.
  - The LLM narrative (Phase 1+) never overrides or restates the deterministic numbers.
  - Because it never executes trades, the practical risk profile is far lower than an autonomous or customer-facing system.

## 11. Phased Roadmap

**Phase 0 — Deterministic core (this repo's initial state)**
Statement ingestion (CSV) → structured holdings DB → band-rebalancing check against a config file → plain Markdown report. No LLM, no network access anywhere.

**Phase 1 — Local LLM narrative layer**
Add Ollama + Qwen3-14B as the Portfolio Analyst / Tax-Awareness narrators, strictly downstream of Phase 0's numbers. Still zero network access anywhere in the system.

**Phase 2 — Market/news context (Zone B introduced)**
Add the sandboxed, network-allowlisted Zone B process for yfinance + one news source; wire the Orchestrator to merge Zone A + Zone B output.

**Phase 3 — Tax optimization & optional portfolio-theory extras**
Tax-loss harvesting detail, asset-location suggestions, optional PyPortfolioOpt/Riskfolio-Lib commentary as a supplementary section.

**Phase 4 (optional)**
Localhost-only web UI with the same Zone A/B split enforced; revisit orchestration framework choice once there's actual branching/multi-turn behavior to justify it.

## 12. Open Questions

- Exact accounts and target allocation to start with.
- Preferred news source/provider for Phase 2.
- Report format preference beyond Markdown (HTML/PDF rendering).
- Exact rebalancing band parameters if 5/25 isn't your preference.
- Whether to eventually fold the `bankstatement_script` checking/savings tracker into this system, or keep them separate (different, lower-stakes threat model).
