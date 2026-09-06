from types import MappingProxyType

import polars as pl
import pytest

from cadence.metrics import registry
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import MetricDefinition, Population, QuantityKind
from cadence.metrics.trip import (
    compute_depart_delay_mean_completed_s_v1,
    compute_time_in_network_at_horizon_mean_unfinished_s_v1,
    compute_time_loss_mean_completed_s_v1,
    compute_time_loss_mean_unfinished_s_v1,
    compute_travel_time_mean_completed_s_v1,
    compute_waiting_time_mean_completed_s_v1,
    compute_waiting_time_mean_unfinished_s_v1,
)

# The literals pinned below are the measured means rounded to two decimals, so a correct
# computation can sit up to half of the last digit -- 0.005 s -- away from the literal on
# rounding alone. 0.01 s is that bound with room to spare, and still tight enough to catch a
# wrong column or an unfiltered population, which move these means by whole seconds.
_FIXTURE_MEAN_TOLERANCE_S = 0.01

_TRIPINFO_COLUMNS = ("arrival", "duration", "waitingTime", "timeLoss", "departDelay")


def _write_tripinfo(tmp_path, rows: list[dict[str, str]]) -> RunDirectory:
    path = tmp_path / "evaluation" / "tripinfo.parquet"
    path.parent.mkdir(parents=True)
    schema = dict.fromkeys(_TRIPINFO_COLUMNS, pl.String)
    pl.DataFrame(rows, schema=schema).write_parquet(path)
    return RunDirectory(tmp_path)


def _row(*, arrival: str, duration: str, waiting: str, loss: str, delay: str) -> dict[str, str]:
    return {
        "arrival": arrival,
        "duration": duration,
        "waitingTime": waiting,
        "timeLoss": loss,
        "departDelay": delay,
    }


def test_compute_travel_time_mean_completed_ignores_unfinished_rows(tmp_path):
    run = _write_tripinfo(
        tmp_path,
        [
            _row(arrival="10.00", duration="20.00", waiting="1.00", loss="2.00", delay="0.50"),
            _row(arrival="30.00", duration="40.00", waiting="3.00", loss="4.00", delay="1.50"),
            # Unfinished: duration is the clock, not a travel time -- must not enter this mean.
            _row(arrival="-1.00", duration="999.00", waiting="0.00", loss="0.00", delay="0.00"),
        ],
    )
    result = compute_travel_time_mean_completed_s_v1(run)
    assert result.columns == ["travel_time_mean_completed_s_v1"]
    assert result["travel_time_mean_completed_s_v1"][0] == pytest.approx(30.0)


def test_compute_waiting_and_time_loss_mean_completed(tmp_path):
    run = _write_tripinfo(
        tmp_path,
        [
            _row(arrival="10.00", duration="20.00", waiting="1.00", loss="2.00", delay="0.50"),
            _row(arrival="30.00", duration="40.00", waiting="3.00", loss="6.00", delay="1.50"),
            # Unfinished: every column below is far outside the completed pair's range, so
            # the completed filter is exercised on each of the three, not on duration alone.
            _row(arrival="-1.00", duration="999.00", waiting="99.00", loss="98.00", delay="97.00"),
        ],
    )
    assert compute_waiting_time_mean_completed_s_v1(run)["waiting_time_mean_completed_s_v1"][
        0
    ] == pytest.approx(2.0)
    assert compute_time_loss_mean_completed_s_v1(run)["time_loss_mean_completed_s_v1"][
        0
    ] == pytest.approx(4.0)
    assert compute_depart_delay_mean_completed_s_v1(run)["depart_delay_mean_completed_s_v1"][
        0
    ] == pytest.approx(1.0)


def test_compute_time_in_network_at_horizon_uses_only_unfinished_rows(tmp_path):
    run = _write_tripinfo(
        tmp_path,
        [
            _row(arrival="10.00", duration="20.00", waiting="1.00", loss="2.00", delay="0.50"),
            _row(arrival="-1.00", duration="50.00", waiting="30.00", loss="40.00", delay="0.00"),
            _row(arrival="-1.00", duration="70.00", waiting="50.00", loss="60.00", delay="0.00"),
        ],
    )
    result = compute_time_in_network_at_horizon_mean_unfinished_s_v1(run)
    assert result.columns == ["time_in_network_at_horizon_mean_unfinished_s_v1"]
    assert result["time_in_network_at_horizon_mean_unfinished_s_v1"][0] == pytest.approx(60.0)
    assert compute_waiting_time_mean_unfinished_s_v1(run)["waiting_time_mean_unfinished_s_v1"][
        0
    ] == pytest.approx(40.0)
    assert compute_time_loss_mean_unfinished_s_v1(run)["time_loss_mean_unfinished_s_v1"][
        0
    ] == pytest.approx(50.0)


def test_unfinished_metrics_return_null_rather_than_dividing_by_zero_on_an_empty_population(
    tmp_path,
):
    # s0_turning has zero unfinished trips (spec §5.1): this is not a hypothetical input.
    run = _write_tripinfo(
        tmp_path,
        [_row(arrival="10.00", duration="20.00", waiting="1.00", loss="2.00", delay="0.50")],
    )
    result = compute_time_in_network_at_horizon_mean_unfinished_s_v1(run)
    # trip.py's `_mean_column`: an empty population's mean is None -- "no data" -- never
    # 0.0, which would read as "every unfinished trip spent no time in the network".
    assert result["time_in_network_at_horizon_mean_unfinished_s_v1"][0] is None
    assert (
        compute_waiting_time_mean_unfinished_s_v1(run)["waiting_time_mean_unfinished_s_v1"][0]
        is None
    )
    assert compute_time_loss_mean_unfinished_s_v1(run)["time_loss_mean_unfinished_s_v1"][0] is None


@pytest.mark.sumo
def test_the_draining_fixture_has_no_unfinished_trips(turning_run_dir):
    # s0_turning: 315 completed, 0 unfinished (spec §5.1; also test_accounting.py).
    run = RunDirectory(turning_run_dir)
    assert (
        compute_time_in_network_at_horizon_mean_unfinished_s_v1(run)[
            "time_in_network_at_horizon_mean_unfinished_s_v1"
        ][0]
        is None
    )


@pytest.mark.sumo
def test_the_oversaturated_fixture_matches_the_measured_completed_means(oversaturated_run_dir):
    # Measured on the committed fixture (spec §5.1): 183 completed trips.
    run = RunDirectory(oversaturated_run_dir)
    travel_time = compute_travel_time_mean_completed_s_v1(run)["travel_time_mean_completed_s_v1"][0]
    waiting = compute_waiting_time_mean_completed_s_v1(run)["waiting_time_mean_completed_s_v1"][0]
    time_loss = compute_time_loss_mean_completed_s_v1(run)["time_loss_mean_completed_s_v1"][0]
    assert travel_time == pytest.approx(77.93, abs=_FIXTURE_MEAN_TOLERANCE_S), travel_time
    assert waiting == pytest.approx(34.94, abs=_FIXTURE_MEAN_TOLERANCE_S), waiting
    assert time_loss == pytest.approx(48.00, abs=_FIXTURE_MEAN_TOLERANCE_S), time_loss


@pytest.mark.sumo
def test_the_oversaturated_fixture_matches_the_measured_unfinished_means(oversaturated_run_dir):
    # Measured on the committed fixture (spec §5.1): 178 unfinished trips. The mean duration
    # (77.76 s) is within 0.2% of the completed mean (77.93 s) while waiting runs 59% higher
    # (55.44 s against 34.94 s) -- a clocked duration that barely moves despite outcomes that
    # much worse is ST-D27's argument that duration is censored, not a travel time, here.
    run = RunDirectory(oversaturated_run_dir)
    duration = compute_time_in_network_at_horizon_mean_unfinished_s_v1(run)[
        "time_in_network_at_horizon_mean_unfinished_s_v1"
    ][0]
    waiting = compute_waiting_time_mean_unfinished_s_v1(run)["waiting_time_mean_unfinished_s_v1"][0]
    time_loss = compute_time_loss_mean_unfinished_s_v1(run)["time_loss_mean_unfinished_s_v1"][0]
    assert duration == pytest.approx(77.76, abs=_FIXTURE_MEAN_TOLERANCE_S), duration
    assert waiting == pytest.approx(55.44, abs=_FIXTURE_MEAN_TOLERANCE_S), waiting
    assert time_loss == pytest.approx(67.68, abs=_FIXTURE_MEAN_TOLERANCE_S), time_loss


# ST-D27: quantities read from a per-trip clock that arrival >= 0 splits in two -- pooling
# either across the boundary reintroduces the §1.1 inversion through a different door.
# `departDelay` is absent deliberately: it is fixed at insertion and known in full for every
# departed vehicle, so the horizon censors nothing about it and a future
# depart_delay_mean_departed_s_v1 over DEPARTED_VEHICLES must not be refused here.
_CENSORED_TRIP_COLUMNS = frozenset({"duration", "waitingTime", "timeLoss"})
_POPULATIONS_ON_ONE_SIDE_OF_THE_BOUNDARY = frozenset(
    {Population.COMPLETED_TRIPS, Population.UNFINISHED_TRIPS}
)


def _boundary_offenders(metrics: dict[str, MetricDefinition]) -> list[str]:
    # The one copy of the detector: the violation test below calls this too, so flipping the
    # predicate here fails there as well rather than leaving a green duplicate behind.
    return [
        name
        for name, definition in metrics.items()
        if set(definition.input_fields) & _CENSORED_TRIP_COLUMNS
        and definition.population not in _POPULATIONS_ON_ONE_SIDE_OF_THE_BOUNDARY
    ]


def test_no_registered_metric_reading_a_censored_trip_column_spans_the_boundary():
    # Asserted from the declarations (population, input_fields), not from arithmetic on any
    # run -- so it stays true for metrics nobody has written yet (plan Task 7, Step 3).
    offenders = _boundary_offenders(dict(registry.registered_metrics()))
    assert not offenders, (
        f"{offenders}: reads a censored trip column but declares a population other than "
        "COMPLETED_TRIPS or UNFINISHED_TRIPS, which spans the censoring boundary (ST-D27)"
    )


def test_the_boundary_detector_catches_a_deliberate_violation(monkeypatch):
    # GOTCHA: a boundary test that cannot fail is worthless -- prove it actually distinguishes
    # a pooled declaration from the honest ones already registered.
    pooled = MetricDefinition(
        name="pooled_travel_time_mean_s_v1",
        version=1,
        definition="a deliberately wrong declaration for this test only",
        unit="s",
        population=Population.DEPARTED_VEHICLES,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "duration"),
        aggregation="mean",
        limitations=("test fixture",),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
    fake_registered = dict(registry.registered_metrics())
    fake_registered["pooled_travel_time_mean_s_v1"] = pooled
    monkeypatch.setattr(registry, "registered_metrics", lambda: fake_registered)
    assert _boundary_offenders(dict(registry.registered_metrics())) == [
        "pooled_travel_time_mean_s_v1"
    ]
