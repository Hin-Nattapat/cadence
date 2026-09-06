import polars as pl
import pytest

from cadence.metrics import registry
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import Population
from cadence.metrics.teleport import (
    compute_completion_rate_teleported_ratio_v1,
    compute_completion_rate_unaffected_ratio_v1,
    compute_teleport_affected_veh_v1,
    compute_teleport_incidence_count_v1,
)
from cadence.simulation.artifacts import _SCHEMAS

_TELEPORT_SCHEMA = _SCHEMAS["state/teleport"]

# spec §3.2: the two counts have no vehicle denominator, so RUN is the honest population.
# The two rates divide one subset of departed vehicles by another, which is what makes
# ST-D29's never-inserted limitation binding on them (round 1, item 2).
_EXPECTED_POPULATIONS = {
    "teleport_incidence_count_v1": Population.RUN,
    "teleport_affected_veh_v1": Population.RUN,
    "completion_rate_teleported_ratio_v1": Population.DEPARTED_VEHICLES,
    "completion_rate_unaffected_ratio_v1": Population.DEPARTED_VEHICLES,
}

_RUN_DIR_FIXTURES = ["turning_run_dir", "oversaturated_run_dir"]


def _write_teleport_run(
    tmp_path, *, teleport_rows: list[dict[str, object]], trip_rows: list[dict[str, str]]
) -> RunDirectory:
    teleport_path = tmp_path / "state" / "teleport.parquet"
    teleport_path.parent.mkdir(parents=True)
    pl.DataFrame(teleport_rows, schema=_TELEPORT_SCHEMA).write_parquet(teleport_path)

    tripinfo_path = tmp_path / "evaluation" / "tripinfo.parquet"
    tripinfo_path.parent.mkdir(parents=True)
    schema = {"id": pl.String, "arrival": pl.String}
    pl.DataFrame(trip_rows, schema=schema).write_parquet(tripinfo_path)
    return RunDirectory(tmp_path)


def _teleport(*, time_s: float, vehicle_id: str, kind: str = "jam") -> dict[str, object]:
    return {"time_s": time_s, "vehicle_id": vehicle_id, "from_lane_id": "A_0", "kind": kind}


def _trip(*, id: str, arrival: str) -> dict[str, str]:
    return {"id": id, "arrival": arrival}


def test_every_teleport_metric_declares_the_population_it_is_scoped_to():
    declared = registry.registered_metrics()
    assert {
        name: declared[name].population for name in _EXPECTED_POPULATIONS
    } == _EXPECTED_POPULATIONS


def test_teleport_incidence_count_counts_rows_not_distinct_vehicles(tmp_path):
    # v1 teleports twice: the incidence count is 3, not 2 -- one row per TELEPORT_STARTED
    # event (spec §3.2).
    run = _write_teleport_run(
        tmp_path,
        teleport_rows=[
            _teleport(time_s=10.0, vehicle_id="v1"),
            _teleport(time_s=20.0, vehicle_id="v1"),
            _teleport(time_s=30.0, vehicle_id="v2"),
        ],
        trip_rows=[_trip(id="v1", arrival="40.00"), _trip(id="v2", arrival="-1.00")],
    )
    incidence_count = compute_teleport_incidence_count_v1(run)["teleport_incidence_count_v1"][0]
    affected_veh = compute_teleport_affected_veh_v1(run)["teleport_affected_veh_v1"][0]
    assert incidence_count == pytest.approx(3.0)
    assert affected_veh == pytest.approx(2.0)


def test_completion_rate_direction_matches_the_measured_fixture(tmp_path):
    # Reproduces spec §3.2's direction, not its exact counts: 2 of 2 teleported vehicles
    # complete (100%) against 1 of 3 unaffected (33%) -- teleported vehicles complete at
    # a *higher* rate, because being teleported is what released them.
    run = _write_teleport_run(
        tmp_path,
        teleport_rows=[
            _teleport(time_s=1.0, vehicle_id="t1"),
            _teleport(time_s=2.0, vehicle_id="t2"),
        ],
        trip_rows=[
            _trip(id="t1", arrival="5.00"),
            _trip(id="t2", arrival="6.00"),
            _trip(id="u1", arrival="7.00"),
            _trip(id="u2", arrival="-1.00"),
            _trip(id="u3", arrival="-1.00"),
        ],
    )
    teleported_rate = compute_completion_rate_teleported_ratio_v1(run)[
        "completion_rate_teleported_ratio_v1"
    ][0]
    unaffected_rate = compute_completion_rate_unaffected_ratio_v1(run)[
        "completion_rate_unaffected_ratio_v1"
    ][0]
    assert teleported_rate == pytest.approx(1.0)
    assert unaffected_rate == pytest.approx(1 / 3)
    assert teleported_rate > unaffected_rate


def test_the_teleported_rate_is_null_rather_than_a_crash_on_a_run_with_no_teleports(tmp_path):
    # s0_turning teleports zero times, so an empty state/teleport frame is a real input, not
    # a hypothetical one. The empty denominator answers "no data", the trip.py convention.
    run = _write_teleport_run(
        tmp_path,
        teleport_rows=[],
        trip_rows=[_trip(id="u1", arrival="7.00"), _trip(id="u2", arrival="-1.00")],
    )
    assert (
        compute_completion_rate_teleported_ratio_v1(run)["completion_rate_teleported_ratio_v1"][0]
        is None
    )
    # The unaffected population is every departed vehicle here, so it still has an answer.
    unaffected_rate = compute_completion_rate_unaffected_ratio_v1(run)[
        "completion_rate_unaffected_ratio_v1"
    ][0]
    assert unaffected_rate == pytest.approx(0.5), unaffected_rate


def test_the_unaffected_rate_is_null_when_every_departed_vehicle_teleported(tmp_path):
    run = _write_teleport_run(
        tmp_path,
        teleport_rows=[
            _teleport(time_s=1.0, vehicle_id="t1"),
            _teleport(time_s=2.0, vehicle_id="t2"),
        ],
        trip_rows=[_trip(id="t1", arrival="5.00"), _trip(id="t2", arrival="-1.00")],
    )
    assert (
        compute_completion_rate_unaffected_ratio_v1(run)["completion_rate_unaffected_ratio_v1"][0]
        is None
    )
    teleported_rate = compute_completion_rate_teleported_ratio_v1(run)[
        "completion_rate_teleported_ratio_v1"
    ][0]
    assert teleported_rate == pytest.approx(0.5), teleported_rate


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_teleport_metrics_on_the_committed_fixtures(request, run_dir_fixture):
    # Measured on the committed fixtures (spec §3.2, plan Task 8). s0_turning_oversaturated:
    # 13 teleports across 13 distinct vehicles, of which 11 completed (85%) against 172 of
    # 348 unaffected (49%). s0_turning drains, teleports zero times and completes all 315 --
    # the zero-teleport denominator the ratio must answer None on.
    expected = {
        "turning_run_dir": (0.0, 0.0, None, 1.0),
        "oversaturated_run_dir": (13.0, 13.0, 11 / 13, 172 / 348),
    }
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    incidence_count = compute_teleport_incidence_count_v1(run)["teleport_incidence_count_v1"][0]
    affected_veh = compute_teleport_affected_veh_v1(run)["teleport_affected_veh_v1"][0]
    teleported_rate = compute_completion_rate_teleported_ratio_v1(run)[
        "completion_rate_teleported_ratio_v1"
    ][0]
    unaffected_rate = compute_completion_rate_unaffected_ratio_v1(run)[
        "completion_rate_unaffected_ratio_v1"
    ][0]

    expected_incidence, expected_affected, expected_teleported, expected_unaffected = expected[
        run_dir_fixture
    ]
    assert incidence_count == pytest.approx(expected_incidence), incidence_count
    assert affected_veh == pytest.approx(expected_affected), affected_veh
    assert unaffected_rate == pytest.approx(expected_unaffected), unaffected_rate
    if expected_teleported is None:
        assert teleported_rate is None, teleported_rate
    else:
        assert teleported_rate == pytest.approx(expected_teleported), teleported_rate
        assert teleported_rate > unaffected_rate
