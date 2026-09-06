"""cadence.metrics.network -- throughput and completion, on both of spec §3.3's
denominators (`ST-D26`).

CONTRACT: under oversaturation, "completion rate over vehicles that departed" and
"completion rate over vehicles that were due to depart" are different claims -- the gap
between them is exactly the never-inserted bucket, which has no per-vehicle identity
(spec §3.3). Reporting only one denominator lets a controller that starves insertion look
identical to one that does not.
"""

from __future__ import annotations

from types import MappingProxyType

import polars as pl

from cadence.metrics.accounting import EXCLUDES_NEVER_INSERTED_VEHICLES, account
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import (
    MetricDefinition,
    Population,
    QuantityKind,
    register,
    scalar_frame,
)

# An hour has 3,600 s: the SI conversion `throughput_vehph_v1` needs to turn a per-run
# completion count into a rate comparable across runs of different lengths.
_SECONDS_PER_HOUR = 3600.0

# A count has no denominator to exclude anyone from; what it excludes is coverage.
_COUNTS_DEPARTED_VEHICLES_ONLY = (
    "counts departed vehicles only -- spec §3.3's never-inserted vehicles have no tripinfo "
    "row and are reported separately by pending_insertion_at_horizon_veh_v1",
)


def _ratio_or_none(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


@register(
    MetricDefinition(
        name="throughput_vehph_v1",
        version=1,
        definition="completed trips per hour of simulated time -- arrived_total_veh at the "
        "horizon divided by the elapsed simulated time, terminal_time_s - begin_s",
        unit="vehph",
        population=Population.RUN,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "terminal_time_s", "begin_s"),
        aggregation="rate",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_throughput_vehph_v1(run: RunDirectory) -> pl.DataFrame:
    accounting = account(run)
    manifest = run.manifest()
    # The rate is per hour of simulation that actually ran, so the warm-up offset comes off
    # the horizon; `build_sumo_command` does the same subtraction for --waiting-time-memory.
    # Every scenario today begins at 0.0, which is why absolute time was right by accident.
    elapsed_time_s = manifest.terminal_time_s - manifest.begin_s
    completed_per_s = _ratio_or_none(float(accounting.completed_veh), elapsed_time_s)
    throughput_vehph = None if completed_per_s is None else completed_per_s * _SECONDS_PER_HOUR
    return scalar_frame("throughput_vehph_v1", throughput_vehph)


@register(
    MetricDefinition(
        name="completion_rate_departed_ratio_v1",
        version=1,
        definition="completed_veh / departed_veh at the horizon (spec §3.1)",
        unit="ratio",
        population=Population.DEPARTED_VEHICLES,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival",),
        aggregation="ratio",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_completion_rate_departed_ratio_v1(run: RunDirectory) -> pl.DataFrame:
    accounting = account(run)
    ratio = _ratio_or_none(float(accounting.completed_veh), float(accounting.departed_veh))
    return scalar_frame("completion_rate_departed_ratio_v1", ratio)


@register(
    MetricDefinition(
        name="completion_rate_due_ratio_v1",
        version=1,
        definition=(
            "completed_veh / due_veh at the horizon, where due_veh = departed_veh + "
            "never_inserted_veh (spec §3.3) -- the claim completion_rate_departed_ratio_v1 "
            "cannot make, because it excludes the never-inserted bucket entirely"
        ),
        unit="ratio",
        population=Population.DUE_VEHICLES,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "pending_insertion_veh"),
        aggregation="ratio",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_completion_rate_due_ratio_v1(run: RunDirectory) -> pl.DataFrame:
    accounting = account(run)
    ratio = _ratio_or_none(float(accounting.completed_veh), float(accounting.due_veh))
    return scalar_frame("completion_rate_due_ratio_v1", ratio)


@register(
    MetricDefinition(
        name="still_in_network_at_horizon_veh_v1",
        version=1,
        definition="active_veh at the horizon -- vehicles that departed but had not "
        "arrived when the run ended (spec §3.1)",
        unit="veh",
        population=Population.UNFINISHED_TRIPS,
        quantity_kind=QuantityKind.STOCK,
        input_fields=("arrival",),
        aggregation="count",
        limitations=_COUNTS_DEPARTED_VEHICLES_ONLY,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_still_in_network_at_horizon_veh_v1(run: RunDirectory) -> pl.DataFrame:
    accounting = account(run)
    return scalar_frame("still_in_network_at_horizon_veh_v1", float(accounting.unfinished_veh))


@register(
    MetricDefinition(
        name="pending_insertion_at_horizon_veh_v1",
        version=1,
        definition=(
            "pending_insertion_veh at the horizon -- spec §3.3's never-inserted bucket, "
            "counted but with no per-vehicle identity"
        ),
        unit="veh",
        population=Population.DUE_VEHICLES,
        quantity_kind=QuantityKind.STOCK,
        input_fields=("pending_insertion_veh",),
        aggregation="count",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_pending_insertion_at_horizon_veh_v1(run: RunDirectory) -> pl.DataFrame:
    accounting = account(run)
    return scalar_frame("pending_insertion_at_horizon_veh_v1", float(accounting.never_inserted_veh))
