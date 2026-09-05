import pytest

from cadence.metrics.loader import RunDirectory
from cadence.simulation.manifest import RunManifest


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
