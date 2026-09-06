"""cadence.metrics.trip -- trip metrics over the outcome buckets of spec §3.1.

CONTRACT: ST-D27 -- a censored quantity is never averaged with an uncensored one. Every
metric here is scoped to exactly one of Population.COMPLETED_TRIPS or
Population.UNFINISHED_TRIPS, split at `arrival >= 0`, and never pooled across that boundary.
An unfinished trip's `duration` is not its travel time -- it is how long the clock ran before
the horizon -- so it is reported under its own name, `time_in_network_at_horizon`, never
`travel_time`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import cast

import polars as pl

from cadence.metrics.accounting import (
    EXCLUDES_NEVER_INSERTED_VEHICLES,
    completed_trips,
    unfinished_trips,
)
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import (
    MetricDefinition,
    Population,
    QuantityKind,
    register,
    scalar_frame,
)


def _mean_column(trips: pl.DataFrame, column: str) -> float | None:
    # `Series.mean()` on an empty series returns None rather than 0.0 (verified) -- an empty
    # population's mean is "no data", not "zero seconds". s0_turning has zero unfinished
    # trips (spec §5.1), so the unfinished metrics below exercise this path.
    # The cast pins the dtype to Float64, so mean() is float or, when empty, None.
    return cast(float | None, trips[column].cast(pl.Float64).mean())


# --- completed trips ------------------------------------------------------------------
# ST-D27: computed only over arrival >= 0. Never pooled with the unfinished metrics below.


@register(
    MetricDefinition(
        name="travel_time_mean_completed_s_v1",
        version=1,
        definition="mean of tripinfo `duration` over trips with arrival >= 0",
        unit="s",
        population=Population.COMPLETED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "duration"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_travel_time_mean_completed_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "travel_time_mean_completed_s_v1", _mean_column(completed_trips(run), "duration")
    )


@register(
    MetricDefinition(
        name="waiting_time_mean_completed_s_v1",
        version=1,
        definition="mean of tripinfo `waitingTime` over trips with arrival >= 0",
        unit="s",
        population=Population.COMPLETED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "waitingTime"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_waiting_time_mean_completed_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "waiting_time_mean_completed_s_v1", _mean_column(completed_trips(run), "waitingTime")
    )


@register(
    MetricDefinition(
        name="time_loss_mean_completed_s_v1",
        version=1,
        definition="mean of tripinfo `timeLoss` over trips with arrival >= 0",
        unit="s",
        population=Population.COMPLETED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "timeLoss"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_time_loss_mean_completed_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "time_loss_mean_completed_s_v1", _mean_column(completed_trips(run), "timeLoss")
    )


@register(
    MetricDefinition(
        name="depart_delay_mean_completed_s_v1",
        version=1,
        definition="mean of tripinfo `departDelay` over trips with arrival >= 0",
        unit="s",
        population=Population.COMPLETED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "departDelay"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_depart_delay_mean_completed_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "depart_delay_mean_completed_s_v1", _mean_column(completed_trips(run), "departDelay")
    )


# --- unfinished trips ------------------------------------------------------------------
# ST-D27: reported separately from the completed population above, never pooled with it.
# `duration` is renamed rather than reused: for arrival < 0 it is the time each vehicle had
# been in the network when the run ended -- right-censored at the horizon, not a travel time
# (spec §5.1 measured this on the oversaturated fixture: completed and unfinished mean
# durations agree to within 0.2% while the unfinished carry 59% more waiting, which a
# travel-time reading cannot explain).


@register(
    MetricDefinition(
        name="time_in_network_at_horizon_mean_unfinished_s_v1",
        version=1,
        definition=(
            "mean of tripinfo `duration` over trips with arrival < 0 -- the simulated time "
            "each was in the network when the run ended, right-censored at the horizon and "
            "never a travel time (ST-D27)"
        ),
        unit="s",
        population=Population.UNFINISHED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "duration"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_time_in_network_at_horizon_mean_unfinished_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "time_in_network_at_horizon_mean_unfinished_s_v1",
        _mean_column(unfinished_trips(run), "duration"),
    )


@register(
    MetricDefinition(
        name="waiting_time_mean_unfinished_s_v1",
        version=1,
        definition="mean of tripinfo `waitingTime` over trips with arrival < 0",
        unit="s",
        population=Population.UNFINISHED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "waitingTime"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_waiting_time_mean_unfinished_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "waiting_time_mean_unfinished_s_v1", _mean_column(unfinished_trips(run), "waitingTime")
    )


@register(
    MetricDefinition(
        name="time_loss_mean_unfinished_s_v1",
        version=1,
        definition="mean of tripinfo `timeLoss` over trips with arrival < 0",
        unit="s",
        population=Population.UNFINISHED_TRIPS,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("arrival", "timeLoss"),
        aggregation="mean",
        limitations=EXCLUDES_NEVER_INSERTED_VEHICLES,
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_time_loss_mean_unfinished_s_v1(run: RunDirectory) -> pl.DataFrame:
    return scalar_frame(
        "time_loss_mean_unfinished_s_v1", _mean_column(unfinished_trips(run), "timeLoss")
    )
