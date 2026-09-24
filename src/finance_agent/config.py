"""Loads the target-allocation config file (config/target_allocation.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

from finance_agent.models import AssetClassTarget, RebalanceBandConfig


class ConfigError(ValueError):
    pass


def load_target_allocation(path: Path) -> tuple[list[AssetClassTarget], RebalanceBandConfig]:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "asset_classes" not in raw:
        raise ConfigError(f"{path}: missing top-level 'asset_classes' key")

    targets = [
        AssetClassTarget(asset_class=name, target_pct=float(values["target_pct"]))
        for name, values in raw["asset_classes"].items()
    ]

    band_raw = raw.get("band", {})
    band = RebalanceBandConfig(
        absolute_pct=float(band_raw.get("absolute_pct", 5.0)),
        relative_pct=float(band_raw.get("relative_pct", 25.0)),
        relative_threshold_pct=float(band_raw.get("relative_threshold_pct", 20.0)),
    )

    return targets, band
