"""ST-D31's reconciliation test: the ground-truth cross-tab against the privileged truth
stream it is meant to explain.

CONTRACT: distinct_veh(L, E) >= traversals(L->E) for every (lane, edge) pair. Every vehicle
that crossed from lane L to edge E must have stood on L intending E at some point; the
excess over the traversal count is vehicles that changed lane before the stop line. Run on
s0_turning, not the oversaturated fixture (docs/specs/2026-08-27-m1b-metrics.md §8): the
mutation this test exists to catch is caught on 7 of 16 traversed pairs here against 3 of 16
there -- saturation, not symmetry, is what separates them: congestion inflates distinct_veh
relative to traversals, and slack is what the one-sided inequality spends before it can fail,
because detection needs demand asymmetry that a flattened, saturating fixture does not have.
"""

import polars as pl
import pytest

from cadence.cli import run_scenario
from cadence.simulation.artifacts import GROUND_TRUTH_DIR, STATE_DIR, TOPOLOGY_DIR
from cadence.simulation.sumo.binding import BindingKind

TURNING = "scenarios/s0_turning/v1"


@pytest.mark.sumo
def test_every_traversal_was_declared_by_a_vehicle_standing_on_its_lane(tmp_path, repo_root):
    run_dir = run_scenario(repo_root / TURNING, tmp_path, seed=1, binding=BindingKind.LIBSUMO)

    connections = pl.read_parquet(run_dir / TOPOLOGY_DIR / "connection.parquet")
    to_edge_of_movement = dict(connections.select("movement_id", "to_edge_id").unique().rows())

    traversals = pl.read_parquet(run_dir / STATE_DIR / "traversal.parquet")
    traversal_counts: dict[tuple[str, str], int] = {}
    for from_lane_id, movement_id in traversals.select("from_lane_id", "movement_id").rows():
        key = (from_lane_id, to_edge_of_movement[movement_id])
        traversal_counts[key] = traversal_counts.get(key, 0) + 1

    lane_turn_vehicle = pl.read_parquet(run_dir / GROUND_TRUTH_DIR / "lane_turn_vehicle.parquet")
    distinct_veh = {
        (lane_id, next_edge_id): count
        for lane_id, next_edge_id, count in lane_turn_vehicle.drop_nulls("next_edge_id")
        .select("lane_id", "next_edge_id", "distinct_veh")
        .rows()
    }

    assert len(traversal_counts) == 16, "measured on s0_turning: 315 traversals over 16 pairs"
    # The inequality is one-sided, so nothing bounds distinct_veh from above and a reader
    # that credited every vehicle to every edge its lane serves would pass it untouched --
    # collapsing 24 attributed pairs to the 16 legal ones. Pinning the count closes that.
    assert lane_turn_vehicle.drop_nulls("next_edge_id").height == 24
    violations = {
        pair: (distinct_veh.get(pair, 0), count)
        for pair, count in traversal_counts.items()
        if distinct_veh.get(pair, 0) < count
    }
    assert not violations, f"distinct_veh fell below traversals on {violations}"
