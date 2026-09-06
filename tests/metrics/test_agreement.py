"""spec §10.1 -- the agreement tests.

Every finding in spec §5 came from measuring one quantity two independent ways and looking
at the gap. A unit test against a hand-built frame is written by whoever wrote the metric,
so it separates "runs" from "crashes", never "runs" from "correct" -- these four separate
"runs" from "correct" by checking a metric against a source it was never built from.
"""

import polars as pl
import pytest

from cadence.metrics.loader import RunDirectory
from cadence.metrics.queue import compute_halting_delay_total_veh_s_v1
from cadence.simulation.topology import movement_id

# Measured on the committed fixtures (spec §5.2): the gap is always an undercount and is
# fixture-dependent -- s0_turning -3.63%, oversaturated -1.05%. Step-boundary sampling of
# halting_count_veh misses fractional halting steps tripinfo's continuous waitingTime does
# not, and the smaller s0_turning total makes the same absolute miss a larger fraction.
# 5% covers both measured gaps with margin, while still catching ST-D28's 10.9x error by
# two orders of magnitude.
_HALTING_DELAY_UNDERCOUNT_TOLERANCE_RATIO = 0.05

# The levels themselves, measured on the committed fixtures at seed 1: (Σ halting_count_veh·Δt,
# Σ tripinfo waitingTime). Without these the ratio above passes on a fixture regenerated at
# half the demand. Both runs are deterministic under a fixed seed, so the pinned values are
# exact today; 1% absorbs a SUMO patch release moving a vehicle between two steps and still
# catches any regeneration that changes the demand, which moves these by tens of percent.
_MEASURED_DELAY_LEVELS = {
    "turning_run_dir": (4778.0, 4958.0),
    "oversaturated_run_dir": (16093.0, 16263.0),
}
_MEASURED_LEVEL_TOLERANCE_RATIO = 0.01

# spec §10.3: the turning demand is built from twelve movement volumes, so twelve is the
# number of distinct movements a completed trip can be on.
_MOVEMENT_COUNT = 12

_RUN_DIR_FIXTURES = ["turning_run_dir", "oversaturated_run_dir"]


def _counts_by_movement(df: pl.DataFrame) -> dict[str, int]:
    grouped = df.group_by("movement_id").len()
    return dict(zip(grouped["movement_id"].to_list(), grouped["len"].to_list(), strict=True))


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_halting_delay_total_agrees_with_tripinfo_waiting_time(request, run_dir_fixture):
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    lane_side_veh_s = compute_halting_delay_total_veh_s_v1(run)["halting_delay_total_veh_s_v1"][0]
    trip_side_s = float(run.evaluation("tripinfo")["waitingTime"].cast(pl.Float64).sum())

    expected_lane_side_veh_s, expected_trip_side_s = _MEASURED_DELAY_LEVELS[run_dir_fixture]
    assert lane_side_veh_s == pytest.approx(
        expected_lane_side_veh_s, rel=_MEASURED_LEVEL_TOLERANCE_RATIO
    ), f"{run_dir_fixture}: Σ halting_count_veh·Δt {lane_side_veh_s}"
    assert trip_side_s == pytest.approx(
        expected_trip_side_s, rel=_MEASURED_LEVEL_TOLERANCE_RATIO
    ), f"{run_dir_fixture}: Σ tripinfo waitingTime {trip_side_s}"

    gap_ratio = (trip_side_s - lane_side_veh_s) / trip_side_s
    assert gap_ratio > 0, (
        f"{run_dir_fixture}: Σ halting_count_veh·Δt {lane_side_veh_s} is not an undercount "
        f"against Σ tripinfo waitingTime {trip_side_s} -- spec §5.2 measured it always "
        "undercounting; a sign flip here is a bigger finding than the tolerance below"
    )
    assert gap_ratio <= _HALTING_DELAY_UNDERCOUNT_TOLERANCE_RATIO, (
        f"{run_dir_fixture}: Σ halting_count_veh·Δt {lane_side_veh_s} vs Σ tripinfo "
        f"waitingTime {trip_side_s}, gap {gap_ratio:.4%} exceeds the "
        f"{_HALTING_DELAY_UNDERCOUNT_TOLERANCE_RATIO:.0%} tolerance"
    )


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_completed_trip_count_matches_arrived_total_at_the_horizon(request, run_dir_fixture):
    # `account()` asserts this same identity and raises before any metric can report, so what
    # this gates is the exporter: that the tripinfo and state/network writers agree on the run
    # they both describe. It is a regression test for the artifact layer, not for accounting.
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    trips = run.evaluation("tripinfo")
    horizon = run.state("network").sort("time_s").row(-1, named=True)
    completed_veh = int((trips["arrival"].cast(pl.Float64) >= 0).sum())
    assert completed_veh == horizon["arrived_total_veh"]


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_tripinfo_row_count_matches_departed_total_at_the_horizon(request, run_dir_fixture):
    # As above: `account()` raises on this first, so this test gates the exporter -- a
    # tripinfo file that lost or duplicated rows against state/network's departure count.
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    trips = run.evaluation("tripinfo")
    horizon = run.state("network").sort("time_s").row(-1, named=True)
    assert trips.height == horizon["departed_total_veh"]


def _completed_trip_movements(run: RunDirectory) -> pl.DataFrame:
    # spec §10.1: tripinfo has no route column. On a single-junction network, the edge a
    # trip departed on and the edge it arrived on already name the one movement it made --
    # stated as a limitation of this derivation, not asserted generally.
    lanes = run.topology("lane")
    lane_to_edge = dict(zip(lanes["lane_id"].to_list(), lanes["edge_id"].to_list(), strict=True))
    trips = run.evaluation("tripinfo")
    completed = trips.filter(pl.col("arrival").cast(pl.Float64) >= 0)
    movements = [
        movement_id(lane_to_edge[depart_lane], lane_to_edge[arrival_lane])
        for depart_lane, arrival_lane in zip(
            completed["departLane"].to_list(), completed["arrivalLane"].to_list(), strict=True
        )
    ]
    return completed.with_columns(pl.Series("movement_id", movements))


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_route_counts_per_movement_equal_traversals_plus_teleported_completions(
    request, run_dir_fixture
):
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    completed_movements = _completed_trip_movements(run)
    completed_ids = set(completed_movements["id"].to_list())
    routes_by_movement = _counts_by_movement(completed_movements)

    # Independent source: traversals(completed), from state/traversal -- a detector that
    # never reads tripinfo or topology/lane at all.
    traversal = run.state("traversal")
    completed_traversal = traversal.filter(pl.col("vehicle_id").is_in(completed_ids))
    # A teleported vehicle crosses the junction without a lane-to-edge transition, so the
    # detector records nothing for it (`forget()` in simulation/sumo/extract.py) -- every
    # completed, non-teleported vehicle crosses exactly once on this single-junction network.
    traversal_counts_per_vehicle = completed_traversal.group_by("vehicle_id").len()
    assert (traversal_counts_per_vehicle["len"] == 1).all(), (
        "a completed vehicle traversed the junction more than once -- the single-junction "
        "assumption behind this identity does not hold on this fixture"
    )
    traversals_by_movement = _counts_by_movement(completed_traversal)

    # Every traversal a completed vehicle makes lands on the movement its own route names --
    # a cross-check of the join itself, not implied by either count alone.
    joined = completed_traversal.join(
        completed_movements.select("id", "movement_id"),
        left_on="vehicle_id",
        right_on="id",
        suffix="_route",
    )
    assert (joined["movement_id"] == joined["movement_id_route"]).all(), (
        "a completed vehicle's recorded traversal lands on a movement other than its own "
        "route -- routes(completed) and traversals(completed) are not counting the same event"
    )

    # Independent source: teleport incidence, from state/teleport -- distinct vehicles
    # affected. A teleported-and-completed vehicle is exactly the case traversal cannot see.
    teleported_ids = set(run.state("teleport")["vehicle_id"].to_list())
    teleported_completed_movements = completed_movements.filter(
        pl.col("id").is_in(teleported_ids & completed_ids)
    )
    teleported_by_movement = _counts_by_movement(teleported_completed_movements)

    every_movement = sorted(set(routes_by_movement) | set(traversals_by_movement))
    reconstructed = {
        movement: traversals_by_movement.get(movement, 0) + teleported_by_movement.get(movement, 0)
        for movement in every_movement
    }
    routes = {movement: routes_by_movement.get(movement, 0) for movement in every_movement}
    # Without this the identity is satisfied by a derivation that collapses every trip onto
    # one movement key: {"X": 183} == {"X": 183} compares nothing about the mapping.
    assert len(routes) == _MOVEMENT_COUNT, f"{run_dir_fixture}: {sorted(routes)}"
    assert routes == reconstructed, (
        f"{run_dir_fixture}: routes(completed) {routes} != traversals(completed) + "
        f"|teleported ∩ completed| {reconstructed} per movement"
    )
