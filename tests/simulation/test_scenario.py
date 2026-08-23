import pytest
from pydantic import ValidationError

from cadence.simulation.scenario import (
    ScenarioConfig,
    config_digest,
    load_scenario,
    sha256_file,
)

VALID_YAML = """
scenario_id: s0_single_intersection
scenario_version: 1
description: Deterministic four-approach synthetic intersection.
network_file: network.net.xml
demand_file: demand.rou.xml
begin_s: 0.0
end_s: 600.0
step_length_s: 1.0
time_to_teleport_s: 300.0
default_seed: 1
"""


def _write_scenario(root, yaml_text=VALID_YAML):
    root.mkdir(parents=True, exist_ok=True)
    (root / "scenario.yaml").write_text(yaml_text)
    (root / "network.net.xml").write_text("<net/>")
    (root / "demand.rou.xml").write_text("<routes/>")
    return root


def test_loads_a_valid_scenario(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1")
    config, paths = load_scenario(root)
    assert config.scenario_id == "s0_single_intersection"
    assert config.end_s == 600.0
    assert paths.network.name == "network.net.xml"
    assert paths.network.is_file()


def test_rejects_an_unknown_key(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1", VALID_YAML + "typo_key: 3\n")
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_a_non_positive_step_length(tmp_path):
    bad = VALID_YAML.replace("step_length_s: 1.0", "step_length_s: 0.0")
    root = _write_scenario(tmp_path / "s0" / "v1", bad)
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_an_end_time_before_the_begin_time(tmp_path):
    bad = VALID_YAML.replace("end_s: 600.0", "end_s: -1.0")
    root = _write_scenario(tmp_path / "s0" / "v1", bad)
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_a_missing_network_file(tmp_path):
    root = tmp_path / "s0" / "v1"
    root.mkdir(parents=True)
    (root / "scenario.yaml").write_text(VALID_YAML)
    (root / "demand.rou.xml").write_text("<routes/>")
    with pytest.raises(FileNotFoundError):
        load_scenario(root)


def test_the_config_is_frozen(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1")
    config, _ = load_scenario(root)
    with pytest.raises(ValidationError):
        config.end_s = 1.0


def test_file_hash_is_stable_and_content_sensitive(tmp_path):
    a = tmp_path / "a.xml"
    a.write_text("<net/>")
    first = sha256_file(a)
    assert first == sha256_file(a)
    a.write_text("<net />")
    assert sha256_file(a) != first


def test_config_digest_ignores_field_order_but_not_values():
    reordered = "\n".join(reversed(VALID_YAML.strip().splitlines()))
    import yaml

    base = ScenarioConfig(**yaml.safe_load(VALID_YAML))
    same = ScenarioConfig(**yaml.safe_load(reordered))
    assert config_digest(base) == config_digest(same)

    changed = base.model_copy(update={"default_seed": 2})
    assert config_digest(changed) != config_digest(base)
