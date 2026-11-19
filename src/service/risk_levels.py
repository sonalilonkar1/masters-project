"""Load and validate the UI risk-level configuration (Task 15 Part A).

A risk level is a name for one of the evaluated policies. The mapping lives in
``config/ui_risk_levels.json`` so it can change without code changes; this
module only checks that the file is consistent before the export or the API
uses it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.service.contract import DATASET_IDS, POLICY_NAMES

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "ui_risk_levels.json"

# Mean has no safety margin and ML alone under-provisions too often (report
# Section 7), so neither may be offered as a risk level.
EXCLUDED_POLICIES = frozenset({"Mean", "ML"})


class RiskLevelConfigError(ValueError):
    """Raised when the risk-level configuration is invalid."""


@dataclass(frozen=True)
class RiskLevel:
    risk_level: str
    label: str
    description: str


@dataclass(frozen=True)
class RiskLevelConfig:
    default_risk_level: str
    risk_levels: tuple[RiskLevel, ...]
    # dataset_id -> risk_level -> policy name
    datasets: dict[str, dict[str, str]]

    def policy_for(self, dataset_id: str, risk_level: str) -> str:
        if dataset_id not in self.datasets:
            raise KeyError(f"unknown dataset: {dataset_id}")
        mapping = self.datasets[dataset_id]
        if risk_level not in mapping:
            raise KeyError(f"unknown risk level: {risk_level}")
        return mapping[risk_level]

    def risk_levels_for_policy(self, dataset_id: str, policy: str) -> list[str]:
        """Risk levels that map to ``policy`` on ``dataset_id``, in display order."""
        mapping = self.datasets[dataset_id]
        return [level.risk_level for level in self.risk_levels if mapping[level.risk_level] == policy]


def validate_risk_level_config(raw: dict) -> RiskLevelConfig:
    """Check a parsed configuration and return it as a ``RiskLevelConfig``."""
    if not isinstance(raw, dict):
        raise RiskLevelConfigError("configuration must be a JSON object")
    for key in ("default_risk_level", "risk_levels", "datasets"):
        if key not in raw:
            raise RiskLevelConfigError(f"missing key: {key}")

    levels = []
    for entry in raw["risk_levels"]:
        for key in ("risk_level", "label", "description"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise RiskLevelConfigError(f"risk level entry needs a non-empty {key!r}: {entry}")
        levels.append(RiskLevel(entry["risk_level"], entry["label"], entry["description"]))
    if not levels:
        raise RiskLevelConfigError("at least one risk level is required")
    level_ids = [level.risk_level for level in levels]
    if len(set(level_ids)) != len(level_ids):
        raise RiskLevelConfigError(f"duplicate risk levels: {level_ids}")

    default = raw["default_risk_level"]
    if default not in level_ids:
        raise RiskLevelConfigError(f"default risk level {default!r} is not defined")

    datasets = raw["datasets"]
    if not isinstance(datasets, dict) or set(datasets) != set(DATASET_IDS):
        found = sorted(datasets) if isinstance(datasets, dict) else datasets
        raise RiskLevelConfigError(f"datasets must be exactly {list(DATASET_IDS)}, got {found}")
    for dataset_id, mapping in datasets.items():
        if not isinstance(mapping, dict) or set(mapping) != set(level_ids):
            raise RiskLevelConfigError(f"{dataset_id}: must map exactly the risk levels {level_ids}")
        for level_id, policy in mapping.items():
            if policy not in POLICY_NAMES:
                raise RiskLevelConfigError(f"{dataset_id}.{level_id}: {policy!r} is not an evaluated policy")
            if policy in EXCLUDED_POLICIES:
                raise RiskLevelConfigError(f"{dataset_id}.{level_id}: {policy} may not be a risk level")

    return RiskLevelConfig(
        default_risk_level=default,
        risk_levels=tuple(levels),
        datasets={dataset_id: dict(mapping) for dataset_id, mapping in datasets.items()},
    )


def load_risk_level_config(path: Path | str = DEFAULT_CONFIG_PATH) -> RiskLevelConfig:
    with open(path, encoding="utf-8") as handle:
        return validate_risk_level_config(json.load(handle))
