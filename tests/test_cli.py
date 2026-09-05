import json

import polars as pl
import pytest

from cadence.cli import DIRTY_TREE_WARNING, _warn_if_dirty, run_scenario
from cadence.simulation.artifacts import (
    EVALUATION_DIR,
    GROUND_TRUTH_DIR,
    STATE_DIR,
    TOPOLOGY_DIR,
)
from cadence.simulation.manifest import RunManifest
from cadence.simulation.state import SignalState
from cadence.simulation.sumo.binding import BindingKind

# s0_turning/v1's fleet vType, from build_s0_scenario.py CAR_MAX_SPEED_MPS. A vehicle's
# speed is bounded by its own vType maxSpeed as well as by the lane, and this fleet's
# 13.9 m/s sits 0.01 above the 13.89 m/s netgenerate posts, so a vehicle at its own limit
# reads as over the lane's. Named as the fleet's speed rather than as a tolerance: 0.01 is
# the consequence, not the rule, and a tolerance would keep passing if the fleet changed.
FLEET_MAX_SPEED_MPS = 13.9

MANIFEST_FIELDS = {
    "cadence_commit": "0" * 40,
    "cadence_dirty": False,
    "cadence_version": "0.0.0",
    "sumo_version": "1.27.1",
    "python_version": "3.12.0",
    "platform_tag": "Darwin-arm64",
    "binding": "traci",
    "controller_id": "none",
    "controller_version": "v1",
    "scenario_id": "s0_single_intersection",
    "scenario_version": 1,
    "network_sha256": "a" * 64,
    "demand_sha256": "b" * 64,
    "config_sha256": "c" * 64,
    "seed": 1,
    "begin_s": 0.0,
    "end_s": 600.0,
    "step_length_s": 1.0,
    "time_to_teleport_s": 300.0,
    "terminal_time_s": 558.0,
    "step_count": 558,
    "unmatched_traversal_count": 0,
    "termination_reason": "drained",
    "cadence_dirty_digest": None,
    "started_at_utc": "2026-08-23T00:00:00+00:00",
    "finished_at_utc": "2026-08-23T00:00:10+00:00",
}


def _write_manifest(tmp_path, *, dirty: bool):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fields = {**MANIFEST_FIELDS, "cadence_dirty": dirty}
    (run_dir / "manifest.json").write_text(json.dumps(fields))
    return run_dir


def test_warns_on_stderr_when_the_working_tree_is_dirty(tmp_path, capsys):
    run_dir = _write_manifest(tmp_path, dirty=True)
    _warn_if_dirty(run_dir)
    captured = capsys.readouterr()
    assert DIRTY_TREE_WARNING in captured.err
    assert captured.out == ""


def test_does_not_warn_when_the_working_tree_is_clean(tmp_path, capsys):
    run_dir = _write_manifest(tmp_path, dirty=False)
    _warn_if_dirty(run_dir)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


@pytest.mark.sumo
def test_a_turning_run_writes_every_artifact(tmp_path, repo_root, expected_movement_traversals):
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.LIBSUMO
    )

    manifest = RunManifest(**json.loads((run_dir / "manifest.json").read_text()))
    assert manifest.scenario_id == "s0_turning"
    assert manifest.termination_reason == "drained"
    assert manifest.terminal_time_s == 558.0
    assert manifest.step_count == 558
    assert manifest.unmatched_traversal_count == 0

    assert pl.read_parquet(run_dir / TOPOLOGY_DIR / "connection.parquet").height == 16
    assert pl.read_parquet(run_dir / TOPOLOGY_DIR / "lane.parquet").height == 16

    traversals = pl.read_parquet(run_dir / STATE_DIR / "traversal.parquet")
    assert traversals.height == 315, "ST-D16: 322 is the via lane, 306 is the lane pair"
    assert traversals["movement_id"].n_unique() == 12
    by_movement = dict(traversals["movement_id"].value_counts().rows())
    assert by_movement == expected_movement_traversals, (
        "the total of 315 is invariant under every movement-mapping error; these twelve "
        "are not, which is why the demand is asymmetric"
    )
    assert traversals["connection_id"].null_count() == 9, "mid-junction lane changes"
    # ST-D31: from_lane_id is observable on every traversal, unlike connection_id -- it is
    # what makes the ground-truth cross-tab's join exact for all 315, not only the 306.
    assert traversals["from_lane_id"].null_count() == 0

    connections = pl.read_parquet(run_dir / TOPOLOGY_DIR / "connection.parquet")
    # Spec §11 and §10.3: every controlled link carries traffic. s0_turning is worth having
    # over s0_single_intersection (8 of 16) precisely because this holds here and not there.
    assert traversals["connection_id"].drop_nulls().n_unique() == connections.height == 16

    lane_state = pl.read_parquet(run_dir / STATE_DIR / "lane.parquet")
    lane_topology = pl.read_parquet(run_dir / TOPOLOGY_DIR / "lane.parquet")
    speed_limit = lane_state.join(lane_topology.select("lane_id", "max_speed_mps"), on="lane_id")
    # Spec §11: 0.0 <= mean_speed_mps <= the lane's own speed limit. LaneState carries no
    # speed limit itself (that lives in LaneInfo), so this cannot be a constructor guard --
    # it is checked here, across the two tables, the same way the occupancy bound is a
    # constructor guard because LaneState carries everything it needs for that one.
    assert (speed_limit["mean_speed_mps"] >= 0.0).all()
    # Measured, not assumed: 1503 of 8928 rows (16.8%) sit above the posted limit. Far from
    # a fixture that never comes near it, the mean speed clears it on one row in six -- so
    # the bound has real bite, against the speed that actually binds.
    assert (
        speed_limit["mean_speed_mps"]
        <= speed_limit["max_speed_mps"].clip(lower_bound=FLEET_MAX_SPEED_MPS)
    ).all()

    # ST-D19: a phase that is never served leaves no row in state/signal.parquet, so the
    # program has to be recorded separately or the starvation case is unreconstructable.
    program = pl.read_parquet(run_dir / TOPOLOGY_DIR / "tls_program.parquet")
    assert program["phase_index"].n_unique() == 4, "S0's static program has four phases"
    assert program.height == 4 * 16, "one row per phase per controlled connection"
    assert set(program["signal"].unique()) <= {state.value for state in SignalState}

    # ST-D18: the tail the research question is about is the unfinished trips, so the run
    # asks SUMO for those too; a drained run simply has none.
    trips = pl.read_parquet(run_dir / EVALUATION_DIR / "tripinfo.parquet")
    assert trips.height == 315

    events = pl.read_parquet(run_dir / "events.parquet")
    kinds = events["kind"].value_counts().to_dict(as_series=False)
    counts = dict(zip(kinds["kind"], kinds["count"], strict=True))
    assert counts.get("departed") == 315
    assert counts.get("arrived") == 315
    assert counts.get("teleport_started", 0) == 0
    assert counts.get("collision", 0) == 0

    assert (run_dir / GROUND_TRUTH_DIR / "lane_turn.parquet").stat().st_size > 0

    # ST-D32: the fleet record, a writer change so M8 can compute jam spacing over every
    # run made between now and then without re-simulating. SUMO registers its own default
    # vTypes (DEFAULT_VEHTYPE, DEFAULT_BIKETYPE, ...) alongside demand.rou.xml's "car", so
    # this is the fixture's own vType rather than the whole table.
    vehicle_type = pl.read_parquet(run_dir / TOPOLOGY_DIR / "vehicle_type.parquet")
    by_id = dict(
        zip(
            vehicle_type["type_id"],
            vehicle_type.select("length_m", "min_gap_m", "max_speed_mps").rows(),
            strict=True,
        )
    )
    assert by_id["car"] == (5.0, 2.5, 13.9)

    # ST-D31: the whole-run distinct-vehicle cross-tab, written once rather than per step.
    lane_turn_vehicle = pl.read_parquet(run_dir / GROUND_TRUTH_DIR / "lane_turn_vehicle.parquet")
    assert lane_turn_vehicle.height > 0
    assert (lane_turn_vehicle["distinct_veh"] > 0).all()


@pytest.mark.sumo
def test_the_privileged_split_is_visible_on_disk(tmp_path, repo_root):
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.LIBSUMO
    )
    assert (run_dir / STATE_DIR).is_dir()
    assert (run_dir / GROUND_TRUTH_DIR).is_dir()
    # A dataset loader bounded by directory rather than by discipline needs the split to be
    # a real directory boundary, not a naming convention inside one table.
    state_columns = set(pl.read_parquet(run_dir / STATE_DIR / "lane.parquet").columns)
    assert "next_edge_id" not in state_columns
    # ST-D18: tripinfo is post-hoc, not privileged. If it sits under ground_truth/ then
    # every metrics module has to enter the privileged allowlist and the partition stops
    # meaning anything.
    assert not (run_dir / GROUND_TRUTH_DIR / "tripinfo.parquet").exists()
    assert (run_dir / EVALUATION_DIR / "tripinfo.parquet").is_file()
    # The XML SUMO wrote is converted and removed: two copies of one dataset, one of them in
    # a format nothing else in the run directory uses, is a format decision made by accident.
    assert not (run_dir / "tripinfo.xml").exists()


@pytest.mark.sumo
def test_the_cross_tab_attributes_vehicles_within_their_approach(tmp_path, repo_root):
    # ST-D20. Three checks, because no single one of them is enough on this network.
    #
    # Reachability is asserted at the edge, not the lane: a vehicle can legitimately stand
    # on a lane its route cannot use, because departure and lane changing put it there
    # before the stop line. On s0_turning every lane serves two of its approach's three
    # movements, so the union over sibling lanes is all three and this check alone cannot
    # tell one turn from another -- it catches an edge outside the approach entirely, and
    # nothing finer. The two checks under it are what recover the resolution.
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.LIBSUMO
    )
    connections = pl.read_parquet(run_dir / TOPOLOGY_DIR / "connection.parquet")
    lanes = pl.read_parquet(run_dir / TOPOLOGY_DIR / "lane.parquet")
    edge_of = dict(lanes.select("lane_id", "edge_id").rows())
    lane_serves: dict[str, set[str]] = {}
    edge_reaches: dict[str, set[str]] = {}
    for from_lane, to_edge in connections.select("from_lane_id", "to_edge_id").rows():
        lane_serves.setdefault(from_lane, set()).add(to_edge)
        edge_reaches.setdefault(edge_of[from_lane], set()).add(to_edge)

    turns = pl.read_parquet(run_dir / GROUND_TRUTH_DIR / "lane_turn.parquet")
    rows = turns.select("lane_id", "next_edge_id", "count_veh").rows()
    for lane_id, next_edge_id, _count_veh in rows:
        # The residual row (§6.1) is a null by design: it holds the vehicles on their final
        # edge, which have no successor to be legal or illegal. Skipping it here is not
        # loosening the check -- the assertions below are what keep the skip honest.
        if next_edge_id is None:
            continue
        assert next_edge_id in edge_reaches.get(edge_of[lane_id], set()), (
            f"{lane_id} is on an approach that cannot reach {next_edge_id}"
        )

    off_lane_veh_steps = sum(
        count_veh
        for lane_id, next_edge_id, count_veh in rows
        if next_edge_id is not None and next_edge_id not in lane_serves.get(lane_id, set())
    )
    attributed_veh_steps = sum(
        count_veh for _lane, next_edge_id, count_veh in rows if next_edge_id is not None
    )
    # Standing on a lane your route cannot use is transient -- one step, while the
    # lane-changer moves you across -- so it has to stay a small share of the time vehicles
    # spend on approach lanes. Measured 227 of 10351, 2.2%. A read that scattered next edges
    # across an approach's three movements would land near a third of them off-lane, so the
    # bound is two orders of magnitude away from the failure it is here to catch and is not
    # a number fitted to the observation.
    assert off_lane_veh_steps / attributed_veh_steps < 0.05

    # And the off-lane pairs are exactly the pre-positioning ones: each of the eight
    # approach lanes paired with the single movement its sibling lane serves, at the
    # measured volume. Identity and magnitude both, because a count of eight would survive
    # a bug that changed which eight.
    off_lane: dict[tuple[str, str], int] = {}
    for lane_id, next_edge_id, count_veh in rows:
        if next_edge_id is not None and next_edge_id not in lane_serves.get(lane_id, set()):
            key = (lane_id, next_edge_id)
            off_lane[key] = off_lane.get(key, 0) + count_veh
    assert off_lane == {
        ("bottom0A0_0", "A0left0"): 21,
        ("bottom0A0_1", "A0right0"): 33,
        ("left0A0_0", "A0top0"): 10,
        ("left0A0_1", "A0bottom0"): 71,
        ("right0A0_0", "A0bottom0"): 13,
        ("right0A0_1", "A0top0"): 21,
        ("top0A0_0", "A0right0"): 28,
        ("top0A0_1", "A0left0"): 30,
    }

    residual_lanes = {lane_id for lane_id, edge, _count in rows if edge is None}
    assert len(residual_lanes) == 16, "every lane carries a residual row, zero or not"
