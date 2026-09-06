import polars as pl
import pytest

from cadence.metrics import registry
from cadence.metrics.loader import RunDirectory
from cadence.metrics.network import (
    compute_completion_rate_departed_ratio_v1,
    compute_completion_rate_due_ratio_v1,
    compute_pending_insertion_at_horizon_veh_v1,
    compute_still_in_network_at_horizon_veh_v1,
    compute_throughput_vehph_v1,
)
from cadence.metrics.registry import Population
from cadence.simulation.artifacts import _SCHEMAS
from conftest import write_manifest_json

_NETWORK_SCHEMA = _SCHEMAS["state/network"]

# ST-D25/ST-D26: which bucket each of these divides by is the claim it makes, so it is pinned
# from the declaration rather than left to whoever next edits the module.
_EXPECTED_POPULATIONS = {
    "throughput_vehph_v1": Population.RUN,
    "completion_rate_departed_ratio_v1": Population.DEPARTED_VEHICLES,
    "completion_rate_due_ratio_v1": Population.DUE_VEHICLES,
    "still_in_network_at_horizon_veh_v1": Population.UNFINISHED_TRIPS,
    "pending_insertion_at_horizon_veh_v1": Population.DUE_VEHICLES,
}


def _write_network_run(
    tmp_path,
    *,
    active: int,
    pending: int,
    departed: int,
    arrived: int,
    terminal_time_s: float,
    begin_s: float = 0.0,
) -> RunDirectory:
    network_path = tmp_path / "state" / "network.parquet"
    network_path.parent.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "time_s": terminal_time_s,
                "active_veh": active,
                "pending_insertion_veh": pending,
                "departed_total_veh": departed,
                "arrived_total_veh": arrived,
                "teleport_total_veh": 0,
            }
        ],
        schema=_NETWORK_SCHEMA,
    ).write_parquet(network_path)

    tripinfo_path = tmp_path / "evaluation" / "tripinfo.parquet"
    tripinfo_path.parent.mkdir(parents=True)
    arrivals = ["1.00"] * arrived + ["-1.00"] * active
    assert len(arrivals) == departed
    pl.DataFrame({"arrival": arrivals}, schema={"arrival": pl.String}).write_parquet(tripinfo_path)

    write_manifest_json(tmp_path, terminal_time_s=terminal_time_s, begin_s=begin_s)
    return RunDirectory(tmp_path)


def test_every_network_metric_declares_the_population_it_divides_by():
    declared = registry.registered_metrics()
    assert {
        name: declared[name].population for name in _EXPECTED_POPULATIONS
    } == _EXPECTED_POPULATIONS


def test_completion_rates_differ_across_the_two_denominators_under_oversaturation(tmp_path):
    # completed=6, departed=8 (2 still in network), pending=2 never inserted: departed and
    # due disagree by exactly the never-inserted bucket (spec §3.3).
    run = _write_network_run(
        tmp_path, active=2, pending=2, departed=8, arrived=6, terminal_time_s=100.0
    )
    departed_ratio = compute_completion_rate_departed_ratio_v1(run)[
        "completion_rate_departed_ratio_v1"
    ][0]
    due_ratio = compute_completion_rate_due_ratio_v1(run)["completion_rate_due_ratio_v1"][0]
    assert departed_ratio == pytest.approx(6 / 8)
    assert due_ratio == pytest.approx(6 / 10)
    assert due_ratio < departed_ratio


def test_completion_rates_return_null_rather_than_dividing_by_zero_on_an_empty_run(tmp_path):
    # queue.py already declares a run where nothing departs as a real input. Both denominators
    # are then zero, and the answer is "no data" -- the same convention trip.py's means use.
    run = _write_network_run(
        tmp_path, active=0, pending=0, departed=0, arrived=0, terminal_time_s=100.0
    )
    assert (
        compute_completion_rate_departed_ratio_v1(run)["completion_rate_departed_ratio_v1"][0]
        is None
    )
    assert compute_completion_rate_due_ratio_v1(run)["completion_rate_due_ratio_v1"][0] is None


def test_still_in_network_and_pending_insertion_come_through_from_the_accounting(tmp_path):
    # Horizon selection itself is proven in test_accounting.py; what this shows is that the
    # two counts reach the output frames unchanged and are not swapped for each other.
    run = _write_network_run(
        tmp_path, active=3, pending=5, departed=9, arrived=6, terminal_time_s=100.0
    )
    still_in_network = compute_still_in_network_at_horizon_veh_v1(run)[
        "still_in_network_at_horizon_veh_v1"
    ][0]
    pending_insertion = compute_pending_insertion_at_horizon_veh_v1(run)[
        "pending_insertion_at_horizon_veh_v1"
    ][0]
    assert still_in_network == pytest.approx(3.0)
    assert pending_insertion == pytest.approx(5.0)


def test_throughput_vehph_converts_completed_count_and_terminal_time_to_a_rate(tmp_path):
    # 180 completed in 180 s (terminal_time_s) -> exactly 3600 veh/h.
    run = _write_network_run(
        tmp_path, active=0, pending=0, departed=180, arrived=180, terminal_time_s=180.0
    )
    throughput = compute_throughput_vehph_v1(run)["throughput_vehph_v1"][0]
    assert throughput == pytest.approx(3600.0)


def test_throughput_vehph_divides_by_elapsed_time_not_absolute_time(tmp_path):
    # A warm-up offset: the run begins at 100 s and ends at 280 s, so 180 s elapsed and 180
    # completed trips are still 3600 veh/h. Dividing by the absolute horizon gives 2314.
    run = _write_network_run(
        tmp_path,
        active=0,
        pending=0,
        departed=180,
        arrived=180,
        terminal_time_s=280.0,
        begin_s=100.0,
    )
    throughput = compute_throughput_vehph_v1(run)["throughput_vehph_v1"][0]
    assert throughput == pytest.approx(3600.0), throughput


def test_throughput_vehph_returns_null_when_no_simulated_time_elapsed(tmp_path):
    # An aborted run can terminate at its own begin time; that is no data, not a crash.
    run = _write_network_run(
        tmp_path, active=0, pending=0, departed=0, arrived=0, terminal_time_s=0.0, begin_s=0.0
    )
    assert compute_throughput_vehph_v1(run)["throughput_vehph_v1"][0] is None


@pytest.mark.sumo
def test_completion_rates_on_the_oversaturated_fixture(oversaturated_run_dir):
    # Measured (spec §3.1, tests/metrics/test_accounting.py): completed=183, departed=361,
    # never_inserted=349, due=710.
    run = RunDirectory(oversaturated_run_dir)
    departed_ratio = compute_completion_rate_departed_ratio_v1(run)[
        "completion_rate_departed_ratio_v1"
    ][0]
    due_ratio = compute_completion_rate_due_ratio_v1(run)["completion_rate_due_ratio_v1"][0]
    assert departed_ratio == pytest.approx(183 / 361), departed_ratio
    assert due_ratio == pytest.approx(183 / 710), due_ratio
