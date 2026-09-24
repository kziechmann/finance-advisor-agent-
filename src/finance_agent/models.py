"""Core data types shared across the ingestion, analytics, and reporting modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HoldingRow:
    """A single ticker position from one statement, as of one date."""

    account_name: str
    account_type: str
    ticker: str
    asset_class: str
    shares: float
    price: float
    market_value: float
    cost_basis: float
    as_of_date: date
    source_file: str


@dataclass(frozen=True)
class AssetClassTarget:
    """Your configured target weight for one asset class."""

    asset_class: str
    target_pct: float


@dataclass(frozen=True)
class RebalanceBandConfig:
    """Parameters for the 5/25 rebalancing band rule (Bogleheads convention).

    An asset class is flagged when it drifts from its target by more than
    `absolute_pct` percentage points (for targets >= relative_threshold_pct),
    or by more than `relative_pct` percent of its own target (for smaller
    targets), whichever applies.
    """

    absolute_pct: float = 5.0
    relative_pct: float = 25.0
    relative_threshold_pct: float = 20.0


@dataclass(frozen=True)
class DriftResult:
    """Computed drift for one asset class as of one snapshot."""

    asset_class: str
    target_pct: float
    current_pct: float
    current_value: float
    diff_pct: float
    band_limit_pct: float
    exceeds_band: bool
    suggested_trade_amount: float
    """Positive = buy more of this asset class, negative = trim it."""
