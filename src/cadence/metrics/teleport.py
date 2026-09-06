"""cadence.metrics.teleport -- teleport as incidence, not an outcome bucket (spec §3.2).

CONTRACT: `state/teleport.parquet` counts `TELEPORT_STARTED` events. A vehicle that
teleports twice contributes two rows, so a metric that treats a row count as a vehicle
count overstates the fleet it affected. Every metric here either counts incidences or
counts distinct `vehicle_id`s, never conflates the two. The two counts are scoped to
`Population.RUN` -- they have no vehicle denominator at all -- while the two completion
rates divide a subset of departed vehicles by another, so they declare
`Population.DEPARTED_VEHICLES` and carry ST-D29's limitation with it. Teleport itself
remains orthogonal to spec §3.1's outcome buckets, never a replacement for one.
"""

from __future__ import annotations

from types import MappingProxyType

import polars as pl

from cadence.metrics.accounting import EXCLUDES_NEVER_INSERTED_VEHICLES, completed_trips
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import (
    MetricDefinition,
    Population,
    QuantityKind,
    register,
    scalar_frame,
)


def _completed_vehicle_ids(run: RunDirectory) -> set[str]:
    return set(completed_trips(run)["id"].to_list())


def _teleported_vehicle_ids(run: RunDirectory) -> set[str]:
    return set(run.state("teleport")["vehicle_id"].to_list())


def _completion_rate(completed_ids: set[str], population_ids: set[str]) -> float | None:
    # An empty population's completion rate is "no data", the same answer trip.py's means
    # give: a run with zero teleports would otherwise divide by zero, and s0_turning is one.
    if not population_ids:
        return None
    return len(population_ids & completed_ids) / len(population_ids)


@register(
    MetricDefinition(
        name="teleport_incidence_count_v1",
        version=1,
        definition="number of TELEPORT_STARTED rows in state/teleport.parquet -- one "
        "vehicle teleporting twice counts twice (spec §3.2)",
        unit="count",
        population=Population.RUN,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("vehicle_id",),
        aggregation="count",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_teleport_incidence_count_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame("teleport_incidence_count_v1", float(run.state("teleport").height))


@register(
    MetricDefinition(
        name="teleport_affected_veh_v1",
        version=1,
        definition="distinct vehicle_id count in state/teleport.parquet (spec §3.2)",
        unit="veh",
        population=Population.RUN,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("vehicle_id",),
        aggregation="count_distinct",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_teleport_affected_veh_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame("teleport_affected_veh_v1", float(len(_teleported_vehicle_ids(run))))


@register(
    MetricDefinition(
        name="completion_rate_teleported_ratio_v1",
        version=1,
        definition=(
            "among departed vehicles with at least one teleport incidence, the fraction "
            "whose tripinfo row has arrival >= 0 (spec §3.2)"
        ),
        unit="ratio",
        population=Population.DEPARTED_VEHICLES,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("vehicle_id", "arrival"),
        aggregation="ratio",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_completion_rate_teleported_ratio_v1(run: RunDirectory) -> pl.DataFrame:
    ratio = _completion_rate(_completed_vehicle_ids(run), _teleported_vehicle_ids(run))
    return scalar_frame("completion_rate_teleported_ratio_v1", ratio)


@register(
    MetricDefinition(
        name="completion_rate_unaffected_ratio_v1",
        version=1,
        definition=(
            "among departed vehicles with zero teleport incidences, the fraction whose "
            "tripinfo row has arrival >= 0 (spec §3.2)"
        ),
        unit="ratio",
        population=Population.DEPARTED_VEHICLES,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("id", "vehicle_id", "arrival"),
        aggregation="ratio",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_completion_rate_unaffected_ratio_v1(run: RunDirectory) -> pl.DataFrame:
    departed_ids = set(run.evaluation("tripinfo")["id"].to_list())
    unaffected_ids = departed_ids - _teleported_vehicle_ids(run)
    ratio = _completion_rate(_completed_vehicle_ids(run), unaffected_ids)
    return scalar_frame("completion_rate_unaffected_ratio_v1", ratio)
