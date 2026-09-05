import pytest

from cadence.simulation.ground_truth import SimulationGroundTruth
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

TURNING = "scenarios/s0_turning/v1"


@pytest.mark.sumo
def test_ground_truth_cross_tabs_lane_against_intended_next_edge(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        for _ in range(120):
            connection.step()
        truth = connection.read_ground_truth()

    assert isinstance(truth, SimulationGroundTruth)
    assert truth.lane_turns, "the fixture has traffic at t=120"
    turned = [row for row in truth.lane_turns if row.next_edge_id is not None]
    residual = [row for row in truth.lane_turns if row.next_edge_id is None]
    assert all(row.count_veh > 0 for row in turned), "only non-zero turn rows are kept"
    assert all(row.halting_count_veh <= row.count_veh for row in truth.lane_turns)
    by_lane = {row.lane_id for row in residual}
    assert len(residual) == len(by_lane), "exactly one residual row per lane"


@pytest.mark.sumo
def test_a_shared_lane_reports_more_than_one_intended_next_edge(repo_root):
    # The whole reason this stream exists: on a shared lane the split is not recoverable
    # from the lane count alone.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        shared_seen = False
        for _ in range(400):
            connection.step()
            truth = connection.read_ground_truth()
            by_lane: dict[str, set[str]] = {}
            for row in truth.lane_turns:
                if row.next_edge_id is None:
                    continue
                by_lane.setdefault(row.lane_id, set()).add(row.next_edge_id)
            if any(len(edges) > 1 for edges in by_lane.values()):
                shared_seen = True
                break

    assert shared_seen


@pytest.mark.sumo
def test_step_does_not_carry_ground_truth(repo_root):
    # ST-D09: reaching for privileged information must be visible in a diff.
    import dataclasses

    from cadence.simulation.events import StepResult

    names = {field.name for field in dataclasses.fields(StepResult)}
    assert "ground_truth" not in names
    assert "lane_turns" not in names


@pytest.mark.sumo
def test_distinct_vehicle_totals_is_read_once_after_the_run(repo_root):
    # ST-D31: unlike read_ground_truth(), which is called every step, this accumulates
    # across the whole run and is read once at the end.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            connection.step()
            connection.read_ground_truth()
        totals = connection.read_distinct_vehicle_totals()

    assert totals, "s0_turning has traffic over its whole run"
    keys = [(row.lane_id, row.next_edge_id) for row in totals]
    assert len(keys) == len(set(keys)), "one row per (lane, next edge) pair"
    assert all(row.distinct_veh > 0 for row in totals)


@pytest.mark.sumo
def test_the_cross_tab_conserves_the_lane_count(repo_root):
    # Spec 6.1: a vehicle on its final edge has no next edge and appears in no row, while
    # getLastStepHaltingNumber counts it. No threshold choice fixes that, so the residual
    # is recorded and M1b can tell an attribution error from a definitional artefact.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        for _ in range(200):
            result = connection.step()
            truth = connection.read_ground_truth()
            by_lane: dict[str, int] = {}
            nulls: dict[str, int] = {}
            for row in truth.lane_turns:
                by_lane[row.lane_id] = by_lane.get(row.lane_id, 0) + row.count_veh
                if row.next_edge_id is None:
                    nulls[row.lane_id] = nulls.get(row.lane_id, 0) + 1
            for lane_id, lane_state in result.state.lanes.items():
                assert nulls.get(lane_id) == 1, f"{lane_id} has no unattributed row"
                assert by_lane[lane_id] == lane_state.vehicle_count_veh
