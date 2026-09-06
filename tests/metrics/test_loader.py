import polars as pl
import pytest

from cadence.metrics.loader import RunDirectory
from cadence.simulation.manifest import RunManifest
from conftest import write_manifest_json


@pytest.mark.sumo
def test_manifest_reads_back_the_run_manifest(turning_run_dir):
    manifest = RunDirectory(turning_run_dir).manifest()
    assert isinstance(manifest, RunManifest)
    assert manifest.scenario_id == "s0_turning"
    assert manifest.termination_reason == "drained"


@pytest.mark.sumo
def test_topology_reads_a_topology_table(turning_run_dir):
    lanes = RunDirectory(turning_run_dir).topology("lane")
    # s0_turning's fixed lane count (M1a §10.3; also tests/test_cli.py).
    assert lanes.height == 16


@pytest.mark.sumo
def test_state_reads_a_state_table(turning_run_dir):
    network = RunDirectory(turning_run_dir).state("network")
    # s0_turning drains in exactly 558 steps at step_length_s=1.0 (M1a §10.3).
    assert network.height == 558


@pytest.mark.sumo
def test_evaluation_reads_an_evaluation_table(turning_run_dir):
    trips = RunDirectory(turning_run_dir).evaluation("tripinfo")
    # s0_turning's fixed traversal count -- one tripinfo row per departure (M1a §10.3).
    assert trips.height == 315


@pytest.mark.parametrize("accessor_name", ["topology", "state", "evaluation"])
def test_table_name_rejects_a_path_traversal(tmp_path, accessor_name):
    accessor = getattr(RunDirectory(tmp_path), accessor_name)
    with pytest.raises(ValueError, match="bare identifier"):
        accessor("../topology/lane")


def test_run_directory_has_no_accessor_for_the_fourth_partition():
    # ST-D30: spec §6.1 names three partitions this package may read. The fourth has no
    # method here, and no other module in cadence.metrics is allowed to name it either
    # (enforced by tests/test_architecture.py).
    public_methods = {name for name in vars(RunDirectory) if not name.startswith("_")}
    assert public_methods == {"manifest", "topology", "state", "evaluation", "root"}


def _write_table(root, partition: str, table: str, value: str) -> None:
    path = root / partition / f"{table}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"marker": [value]}, schema={"marker": pl.String}).write_parquet(path)


@pytest.mark.parametrize("accessor_name", ["topology", "state", "evaluation"])
def test_a_second_read_of_a_table_returns_the_cached_frame(tmp_path, accessor_name):
    # One `cadence metrics` run asks for evaluation/tripinfo once per metric that reads it.
    # Deleting the file between the two reads is what proves the second never reached disk.
    run = RunDirectory(tmp_path)
    _write_table(tmp_path, accessor_name, "example", "first")
    first = getattr(run, accessor_name)("example")
    (tmp_path / accessor_name / "example.parquet").unlink()
    second = getattr(run, accessor_name)("example")
    assert second is first


def test_the_table_cache_is_keyed_by_partition_and_table(tmp_path):
    run = RunDirectory(tmp_path)
    _write_table(tmp_path, "topology", "lane", "topology_lane")
    _write_table(tmp_path, "state", "lane", "state_lane")
    _write_table(tmp_path, "state", "network", "state_network")
    assert run.topology("lane")["marker"].to_list() == ["topology_lane"]
    assert run.state("lane")["marker"].to_list() == ["state_lane"]
    assert run.state("network")["marker"].to_list() == ["state_network"]


def test_the_table_cache_is_per_instance(tmp_path):
    # Two RunDirectory instances over the same root are two readers, not one shared cache:
    # a process that rescores a run after it changed on disk must not be served stale rows.
    _write_table(tmp_path, "state", "network", "first")
    first_frame = RunDirectory(tmp_path).state("network")
    _write_table(tmp_path, "state", "network", "second")
    assert RunDirectory(tmp_path).state("network")["marker"].to_list() == ["second"]
    assert first_frame["marker"].to_list() == ["first"]


def test_a_second_read_of_the_manifest_returns_the_cached_manifest(tmp_path):
    write_manifest_json(tmp_path)
    run = RunDirectory(tmp_path)
    first = run.manifest()
    (tmp_path / "manifest.json").unlink()
    assert run.manifest() is first


def test_the_table_name_is_validated_before_the_cache_is_consulted(tmp_path):
    # A traversal that landed in the cache under its raw key would be refused once and
    # served every time after.
    run = RunDirectory(tmp_path)
    with pytest.raises(ValueError, match="bare identifier"):
        run.state("../topology/lane")
    with pytest.raises(ValueError, match="bare identifier"):
        run.state("../topology/lane")
