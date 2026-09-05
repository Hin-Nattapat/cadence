import polars as pl
import pytest

from cadence.metrics.accounting import VehicleAccounting, account
from cadence.metrics.loader import RunDirectory
from cadence.simulation.artifacts import _SCHEMAS

_NETWORK_SCHEMA = _SCHEMAS["state/network"]


def _write_run(tmp_path, *, network_rows, arrivals):
    network_path = tmp_path / "state" / "network.parquet"
    network_path.parent.mkdir(parents=True)
    pl.DataFrame(network_rows, schema=_NETWORK_SCHEMA).write_parquet(network_path)

    tripinfo_path = tmp_path / "evaluation" / "tripinfo.parquet"
    tripinfo_path.parent.mkdir(parents=True)
    pl.DataFrame({"arrival": arrivals}, schema={"arrival": pl.String}).write_parquet(tripinfo_path)
    return RunDirectory(tmp_path)


def test_account_on_a_hand_built_run_with_a_known_answer(tmp_path):
    # Rows are given out of time_s order -- `.sort("time_s")` in account() must not be a
    # no-op left over from a fixture that happened to already be sorted.
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 1.0,
                "active_veh": 1,
                "pending_insertion_veh": 1,
                "departed_total_veh": 2,
                "arrived_total_veh": 1,
                "teleport_total_veh": 0,
            },
            {
                "time_s": 0.0,
                "active_veh": 0,
                "pending_insertion_veh": 2,
                "departed_total_veh": 0,
                "arrived_total_veh": 0,
                "teleport_total_veh": 0,
            },
        ],
        arrivals=["5.00", "-1.00"],
    )
    assert account(run) == VehicleAccounting(
        completed_veh=1, unfinished_veh=1, never_inserted_veh=1, departed_veh=2, due_veh=3
    )


def test_account_fails_loudly_when_the_per_step_identity_is_broken(tmp_path):
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 0.0,
                "active_veh": 0,
                "pending_insertion_veh": 0,
                "departed_total_veh": 1,
                "arrived_total_veh": 0,
                "teleport_total_veh": 0,
            }
        ],
        arrivals=["5.00"],
    )
    with pytest.raises(ValueError, match="departed_total_veh"):
        account(run)


def test_account_fails_loudly_when_a_null_breaks_the_per_step_identity_check(tmp_path):
    # GOTCHA: polars compares a null through `!=` as null, not True, so `(residual != 0).any()`
    # alone would return False here and let the null row pass as if the identity held.
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 0.0,
                "active_veh": None,
                "pending_insertion_veh": 0,
                "departed_total_veh": 1,
                "arrived_total_veh": 1,
                "teleport_total_veh": 0,
            }
        ],
        arrivals=["5.00"],
    )
    with pytest.raises(ValueError, match="null"):
        account(run)


def test_account_fails_loudly_when_the_horizon_identity_is_broken(tmp_path):
    # completed_veh and unfinished_veh agree with the horizon, but a null arrival -- a row
    # tripinfo carries with no verdict either way -- makes the row count outrun the two of
    # them combined, which is exactly what the third identity (rows == departed_total_veh)
    # is there to catch and the first two cannot.
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 0.0,
                "active_veh": 1,
                "pending_insertion_veh": 0,
                "departed_total_veh": 2,
                "arrived_total_veh": 1,
                "teleport_total_veh": 0,
            }
        ],
        arrivals=["5.00", "-1.00", None],
    )
    with pytest.raises(ValueError, match="departed_veh"):
        account(run)


def test_account_fails_loudly_when_completed_disagrees_with_the_horizon_at_arrival(tmp_path):
    # Breaks only the completed_veh == arrived_total_veh horizon guard: the per-step identity
    # holds, and both unfinished_veh and departed_veh agree with their own horizon counterparts.
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 0.0,
                "active_veh": 1,
                "pending_insertion_veh": 0,
                "departed_total_veh": 3,
                "arrived_total_veh": 2,
                "teleport_total_veh": 0,
            }
        ],
        arrivals=["5.00", "-1.00", None],
    )
    with pytest.raises(ValueError, match="completed_veh"):
        account(run)


def test_account_fails_loudly_when_unfinished_disagrees_with_the_horizon_at_active(tmp_path):
    # Breaks only the unfinished_veh == active_veh horizon guard: the per-step identity holds,
    # and both completed_veh and departed_veh agree with their own horizon counterparts.
    run = _write_run(
        tmp_path,
        network_rows=[
            {
                "time_s": 0.0,
                "active_veh": 2,
                "pending_insertion_veh": 0,
                "departed_total_veh": 4,
                "arrived_total_veh": 2,
                "teleport_total_veh": 0,
            }
        ],
        arrivals=["5.00", "6.00", "-1.00", None],
    )
    with pytest.raises(ValueError, match="unfinished_veh"):
        account(run)


@pytest.mark.sumo
def test_the_draining_fixture_has_no_unfinished_or_never_inserted_vehicles(turning_run_dir):
    assert account(RunDirectory(turning_run_dir)) == VehicleAccounting(
        completed_veh=315, unfinished_veh=0, never_inserted_veh=0, departed_veh=315, due_veh=315
    )


@pytest.mark.sumo
def test_the_oversaturated_fixture_exercises_every_bucket(oversaturated_run_dir):
    # Measured on the committed fixture (spec §3.1): 361 departed = 183 completed + 178
    # still in network; 349 never inserted; 710 departures due in [0, 180).
    assert account(RunDirectory(oversaturated_run_dir)) == VehicleAccounting(
        completed_veh=183, unfinished_veh=178, never_inserted_veh=349, departed_veh=361, due_veh=710
    )


@pytest.mark.sumo
def test_the_per_step_identity_holds_at_every_one_of_the_180_steps(oversaturated_run_dir):
    network = RunDirectory(oversaturated_run_dir).state("network")
    # end_s / step_length_s from scenarios/s0_turning_oversaturated/v1/scenario.yaml
    # (180.0 / 1.0): one state/network row per simulated step across the full horizon.
    assert network.height == 180
    # Restates spec §3.1's identity as the spec states it (departed = arrived + active)
    # rather than accounting.py's own subtraction form, so this does not inherit a sign
    # error from the source it is meant to check.
    assert (
        network["departed_total_veh"] == network["arrived_total_veh"] + network["active_veh"]
    ).all()
