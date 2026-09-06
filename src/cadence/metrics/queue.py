"""cadence.metrics.queue -- queue metrics per lane, and the network's total halting delay
(spec §5.2, §5.3, `ST-D28`, `ST-D29`).

CONTRACT: every stock read from `state/lane.parquet` -- `waiting_total_now_s`, and
`halting_count_veh` on its own -- is reported instantaneously or as a peak, never summed
across steps. `Σ halting_count_veh · Δt` is the one exception: `halting_count_veh` is a
count, not a quantity already in seconds, so multiplying it by the step length is the
correct way to turn it into vehicle-seconds (`ST-D28`).
"""

from __future__ import annotations

from types import MappingProxyType

import polars as pl

from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import (
    MetricDefinition,
    Population,
    QuantityKind,
    register,
    scalar_frame,
)

# spec §5.3: the back-of-queue formula assumes every halting vehicle on a lane has the same
# footprint. A mixed fleet needs a per-vehicle attribution that state/lane.parquet's
# aggregate counts cannot supply -- declared here until a mixed-fleet scenario exists to
# measure the gap against.
_ASSUMES_HOMOGENEOUS_FLEET = (
    "assumes every halting vehicle shares one footprint -- a mixed fleet needs per-vehicle "
    "attribution that state/lane.parquet's aggregate counts cannot supply (spec §5.3)",
)
# tripinfo covers only vehicles that departed, so a run where nothing departs has no vType
# to select from -- the metric cannot be computed at all, let alone accurately.
_REQUIRES_A_DEPARTED_VEHICLE = (
    "the vehicle footprint is selected from tripinfo's vType column, which is empty on a "
    "run with zero departures",
)
# spec §5.2: this integral samples a decaying level at step boundaries, so it misses the
# fractional halting time tripinfo's continuous waitingTime records. Measured against
# Σ tripinfo waitingTime the miss is always an undercount and is fixture-dependent:
# 4,778 against 4,958 veh_s on s0_turning, 16,093 against 16,263 on the oversaturated fixture.
_UNDERCOUNTS_TRIPINFO_WAITING_TIME = (
    "undercounts Σ tripinfo waitingTime by a fixture-dependent margin -- step-boundary "
    "sampling misses fractional halting time; measured 3.63% low on s0_turning and 1.05% "
    "low on s0_turning_oversaturated (spec §5.2)",
)


def _vehicle_span_m(run: RunDirectory) -> float:
    """The fleet's footprint for the back-of-queue formula: length_m + min_gap_m.

    Selected from the vehicle types tripinfo's `vType` column actually names, not from
    `topology/vehicle_type.parquet` directly -- that table also carries the six `DEFAULT_*`
    types SUMO registers on its own, three of which share `car`'s 5.0 m / 2.5 m exactly
    (plan Task 8). Picking by structure rather than by the resulting metres is what a wrong
    selection cannot pass silently.
    """
    used_type_ids = set(run.evaluation("tripinfo")["vType"].unique().to_list())
    if not used_type_ids:
        raise ValueError(
            f"{_REQUIRES_A_DEPARTED_VEHICLE[0]}: queue_length_m cannot be computed on this "
            "run (spec §5.3, ST-D29)"
        )
    vehicle_types = run.topology("vehicle_type")
    selected = vehicle_types.filter(pl.col("type_id").is_in(used_type_ids))
    selected_type_ids = set(selected["type_id"].to_list())
    if selected_type_ids != used_type_ids:
        raise ValueError(
            f"vehicle types used in tripinfo {sorted(used_type_ids)} do not match rows "
            f"selected from topology/vehicle_type.parquet {sorted(selected_type_ids)}"
        )
    spans_m = sorted((selected["length_m"] + selected["min_gap_m"]).unique().to_list())
    if len(spans_m) != 1:
        raise ValueError(
            f"fleet uses {len(spans_m)} distinct vehicle footprints {spans_m} m: "
            "queue_length_m assumes a homogeneous fleet (spec §5.3, ST-D29)"
        )
    return float(spans_m[0])


def _queue_length_m(run: RunDirectory) -> pl.DataFrame:
    span_m = _vehicle_span_m(run)
    return run.state("lane").with_columns(
        (pl.col("halting_count_veh") * span_m).alias("queue_length_m")
    )


@register(
    MetricDefinition(
        name="queue_length_peak_m_v1",
        version=1,
        definition=(
            "per lane, the maximum over the run of halting_count_veh * (length_m + "
            "min_gap_m) -- back-of-queue distance, spec §5.3"
        ),
        unit="m",
        population=Population.LANE_STEPS,
        quantity_kind=QuantityKind.STOCK,
        input_fields=("halting_count_veh", "vType", "type_id", "length_m", "min_gap_m"),
        aggregation="max",
        limitations=_ASSUMES_HOMOGENEOUS_FLEET + _REQUIRES_A_DEPARTED_VEHICLE,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_queue_length_peak_m_v1(run: RunDirectory) -> pl.DataFrame:
    return (
        _queue_length_m(run)
        .group_by("lane_id")
        .agg(pl.col("queue_length_m").max().alias("queue_length_peak_m_v1"))
        .sort("lane_id")
    )


@register(
    MetricDefinition(
        name="waiting_total_peak_s_v1",
        version=1,
        definition="per lane, the maximum over the run of state/lane's waiting_total_now_s",
        unit="s",
        population=Population.LANE_STEPS,
        quantity_kind=QuantityKind.STOCK,
        input_fields=("waiting_total_now_s",),
        aggregation="max",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_waiting_total_peak_s_v1(run: RunDirectory) -> pl.DataFrame:
    return (
        run.state("lane")
        .group_by("lane_id")
        .agg(pl.col("waiting_total_now_s").max().alias("waiting_total_peak_s_v1"))
        .sort("lane_id")
    )


@register(
    MetricDefinition(
        name="halting_delay_total_veh_s_v1",
        version=1,
        definition=(
            "Σ over every lane and step of halting_count_veh * step_length_s -- total "
            "network delay in vehicle-seconds, the sound way to integrate a per-step "
            "halting count (spec §5.2, ST-D28)"
        ),
        unit="veh_s",
        population=Population.LANE_STEPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("halting_count_veh", "step_length_s"),
        aggregation="sum",
        limitations=_UNDERCOUNTS_TRIPINFO_WAITING_TIME,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_halting_delay_total_veh_s_v1(run: RunDirectory) -> pl.DataFrame:
    step_length_s = run.manifest().step_length_s
    total_veh_s = float(run.state("lane")["halting_count_veh"].sum()) * step_length_s
    return scalar_frame("halting_delay_total_veh_s_v1", total_veh_s)
