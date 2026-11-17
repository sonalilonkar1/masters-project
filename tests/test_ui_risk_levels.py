import copy
import json

import pytest

from src.service.risk_levels import (
    DEFAULT_CONFIG_PATH,
    RiskLevelConfigError,
    load_risk_level_config,
    validate_risk_level_config,
)


@pytest.fixture
def raw_config():
    with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_committed_config_loads_with_agreed_mapping():
    config = load_risk_level_config()

    assert config.default_risk_level == "restrictive"
    assert [level.risk_level for level in config.risk_levels] == ["restrictive", "balanced", "efficient"]
    for dataset_id in ("google_clusterdata2019", "alibaba_gpu_v2020"):
        assert config.policy_for(dataset_id, "restrictive") == "Hybrid"
        assert config.policy_for(dataset_id, "balanced") == "P95"
        assert config.policy_for(dataset_id, "efficient") == "P90"


def test_risk_levels_for_policy():
    config = load_risk_level_config()

    assert config.risk_levels_for_policy("alibaba_gpu_v2020", "Hybrid") == ["restrictive"]
    assert config.risk_levels_for_policy("alibaba_gpu_v2020", "P99") == []


def test_unknown_dataset_or_level_raises_key_error():
    config = load_risk_level_config()

    with pytest.raises(KeyError):
        config.policy_for("azure_vm", "restrictive")
    with pytest.raises(KeyError):
        config.policy_for("alibaba_gpu_v2020", "aggressive")


@pytest.mark.parametrize("policy", ["Mean", "ML"])
def test_mean_and_ml_are_not_allowed(raw_config, policy):
    raw_config["datasets"]["alibaba_gpu_v2020"]["efficient"] = policy

    with pytest.raises(RiskLevelConfigError, match="may not be a risk level"):
        validate_risk_level_config(raw_config)


def test_unknown_policy_is_rejected(raw_config):
    raw_config["datasets"]["google_clusterdata2019"]["balanced"] = "P80"

    with pytest.raises(RiskLevelConfigError, match="not an evaluated policy"):
        validate_risk_level_config(raw_config)


def test_default_must_be_defined(raw_config):
    raw_config["default_risk_level"] = "efficientest"

    with pytest.raises(RiskLevelConfigError, match="default risk level"):
        validate_risk_level_config(raw_config)


def test_every_dataset_maps_every_level(raw_config):
    del raw_config["datasets"]["google_clusterdata2019"]["balanced"]

    with pytest.raises(RiskLevelConfigError, match="must map exactly"):
        validate_risk_level_config(raw_config)


def test_both_datasets_required(raw_config):
    del raw_config["datasets"]["alibaba_gpu_v2020"]

    with pytest.raises(RiskLevelConfigError, match="datasets must be exactly"):
        validate_risk_level_config(raw_config)


def test_duplicate_levels_rejected(raw_config):
    raw_config["risk_levels"].append(copy.deepcopy(raw_config["risk_levels"][0]))

    with pytest.raises(RiskLevelConfigError, match="duplicate"):
        validate_risk_level_config(raw_config)


def test_level_needs_description(raw_config):
    raw_config["risk_levels"][1]["description"] = " "

    with pytest.raises(RiskLevelConfigError, match="description"):
        validate_risk_level_config(raw_config)
