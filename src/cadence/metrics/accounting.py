"""cadence.metrics.accounting — the vehicle accounting every population-scoped metric
selects from (spec §3.1).
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from cadence.metrics.loader import RunDirectory

# Five broken steps are enough to show a reader the pattern (e.g. "every
# teleport step") without printing a multi-thousand-float list on an M8 corridor hour.
_MAX_BROKEN_TIMES_SHOWN = 5


@dataclass(frozen=True, slots=True)
class VehicleAccounting:
    completed_veh: int
    unfinished_veh: int
    never_inserted_veh: int
    departed_veh: int
    due_veh: int


def _format_broken_times(broken_at_s: list[float]) -> str:
    shown = broken_at_s[:_MAX_BROKEN_TIMES_SHOWN]
    remaining = len(broken_at_s) - len(shown)
    if remaining:
        return f"{shown} and {remaining} more"
    return f"{shown}"


def _assert_per_step_identity_holds(run: RunDirectory, network: pl.DataFrame) -> None:
    # spec §3.1: holds only while no vehicle is removed rather than arriving. Collision
    # and teleport removal, and max-depart-delay, are pinned off elsewhere so it does; a
    # run made with any of them re-enabled fails this loudly rather than absorb it.
    identity_columns = ("departed_total_veh", "arrived_total_veh", "active_veh")
    null_counts = {column: network[column].null_count() for column in identity_columns}
    if any(null_counts.values()):
        # GOTCHA: polars compares a null through `!=` as null, not True, so `(residual !=
        # 0).any()` returns False on a row with any null in these columns -- the identity
        # check below would silently pass the exact row it exists to catch.
        raise ValueError(
            f"{run.root}: null values in {identity_columns} (spec §3.1): {null_counts}"
        )
    residual = network["departed_total_veh"] - network["arrived_total_veh"] - network["active_veh"]
    if (residual != 0).any():
        broken_at_s = network.filter(residual != 0)["time_s"].to_list()
        raise ValueError(
            f"{run.root}: departed_total_veh != arrived_total_veh + active_veh at time_s "
            f"{_format_broken_times(broken_at_s)} (spec §3.1)"
        )


def _assert_horizon_identity_holds(
    run: RunDirectory,
    horizon: dict[str, object],
    *,
    completed_veh: int,
    unfinished_veh: int,
    departed_veh: int,
) -> None:
    if completed_veh != horizon["arrived_total_veh"]:
        raise ValueError(
            f"{run.root}: completed_veh {completed_veh} != arrived_total_veh "
            f"{horizon['arrived_total_veh']} at the horizon (spec §3.1)"
        )
    if unfinished_veh != horizon["active_veh"]:
        raise ValueError(
            f"{run.root}: unfinished_veh {unfinished_veh} != active_veh {horizon['active_veh']} "
            "at the horizon (spec §3.1)"
        )
    if departed_veh != horizon["departed_total_veh"]:
        raise ValueError(
            f"{run.root}: departed_veh {departed_veh} != departed_total_veh "
            f"{horizon['departed_total_veh']} at the horizon (spec §3.1)"
        )


def account(run: RunDirectory) -> VehicleAccounting:
    network = run.state("network").sort("time_s")
    _assert_per_step_identity_holds(run, network)

    # The population filter is arrival >= 0, declared -- not vaporized == "end". Not every
    # unfinished row carries it, measured on both fixtures (spec §3.1).
    arrival = run.evaluation("tripinfo")["arrival"].cast(pl.Float64)
    completed_veh = int((arrival >= 0).sum())
    unfinished_veh = int((arrival < 0).sum())
    departed_veh = arrival.len()

    horizon = network.row(-1, named=True)
    _assert_horizon_identity_holds(
        run,
        horizon,
        completed_veh=completed_veh,
        unfinished_veh=unfinished_veh,
        departed_veh=departed_veh,
    )

    never_inserted_veh = int(horizon["pending_insertion_veh"])
    return VehicleAccounting(
        completed_veh=completed_veh,
        unfinished_veh=unfinished_veh,
        never_inserted_veh=never_inserted_veh,
        departed_veh=departed_veh,
        due_veh=departed_veh + never_inserted_veh,
    )
