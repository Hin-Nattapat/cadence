"""cadence.metrics.writer — turns a scored run directory into its `metrics/` partition.

CONTRACT: a metric's grain is read from the frame it returns rather than declared a second
time in the registry, so the two can never disagree: one row with columns exactly `[<name>]`
is run grain, one row per distinct lane with columns exactly `[lane_id, <name>]` is lane
grain, and anything else is refused by name.

CONTRACT: the three files are rewritten whole on every call and their content depends only
on the run directory, so re-scoring a run reproduces it byte for byte (ST-D24). The
partition is emptied first, so a table the registry stopped emitting leaves with it rather
than staying behind with nothing marking it stale.

CONTRACT: a null cell is an empty population, never a missing metric. The two are told
apart by the columns being the registry's keys in both directions, checked on real output.
"""

from __future__ import annotations

import functools
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import polars as pl

from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import MetricDefinition, registered_computations, registered_metrics

METRICS_DIR = "metrics"
RUN_TABLE_FILE_NAME = "run.parquet"
LANE_TABLE_FILE_NAME = "lane.parquet"
DEFINITIONS_FILE_NAME = "definitions.json"
_LANE_KEY = "lane_id"
# The indentation manifest.json already uses (cli.py writes model_dump_json(indent=2)), so
# the two files in a run directory meant to be read by a person read the same way.
_JSON_INDENT_SPACES = 2
# Task 9's output shape: run.parquet is one row, so each run-grain frame contributes
# exactly that row and the frames are hstacked rather than stacked.
_RUN_GRAIN_ROW_COUNT = 1


def _lane_table(frames: list[pl.DataFrame]) -> pl.DataFrame:
    if not frames:
        # RunRecorder's convention: a table declares its schema even with no rows, so a run
        # whose registry holds no lane-grain metric still writes a lane.parquet a reader can
        # open rather than one they must first prove absent on purpose.
        return pl.DataFrame(schema={_LANE_KEY: pl.String})
    joined = frames[0]
    for frame in frames[1:]:
        name = frame.columns[1]
        missing = set(joined[_LANE_KEY]).symmetric_difference(frame[_LANE_KEY])
        if missing:
            raise ValueError(
                f"metric {name!r} reports a different lane set from the lane-grain metrics "
                f"before it; they disagree on {sorted(missing)}"
            )
        joined = joined.join(frame, on=_LANE_KEY, how="inner")
    return joined.sort(_LANE_KEY)


def _definitions_document(
    names: list[str], definitions: Mapping[str, MetricDefinition]
) -> dict[str, dict[str, object]]:
    return {
        name: {
            "name": definitions[name].name,
            "version": definitions[name].version,
            "unit": definitions[name].unit,
            "population": definitions[name].population.value,
            "quantity_kind": definitions[name].quantity_kind.value,
            # ST-D29: what the number cannot tell you travels with the number. A table of
            # bare floats reaches a reader who has no other way to learn it.
            "limitations": list(definitions[name].limitations),
            "definition": definitions[name].definition,
        }
        for name in names
    }


def _run_table(frames: list[pl.DataFrame]) -> pl.DataFrame:
    if not frames:
        # The lane side answers its empty case with a schema-only table; the run side has no
        # such answer, because a frame with no columns has no row to be the run's one row.
        # A registry declaring no run-grain metric is a broken registry, not an empty
        # population, so it is refused rather than written as an unreadable file.
        raise ValueError(
            "no run-grain metric is registered: run.parquet is one row of run-grain "
            "columns, and there is no such row to write"
        )
    return functools.reduce(pl.DataFrame.hstack, frames)


def write_metrics(run: RunDirectory) -> Path:
    definitions = registered_metrics()
    computations = registered_computations()
    run_frames: list[pl.DataFrame] = []
    lane_frames: list[pl.DataFrame] = []
    for name, compute in computations.items():
        frame = compute(run)
        if frame.columns == [name]:
            if frame.height != _RUN_GRAIN_ROW_COUNT:
                raise ValueError(
                    f"metric {name!r} returned {frame.height} rows at run grain: a "
                    f"run-grain metric returns exactly {_RUN_GRAIN_ROW_COUNT}, and "
                    "hstacking a taller frame beside its neighbours is not a run score"
                )
            run_frames.append(frame)
        elif frame.columns == [_LANE_KEY, name]:
            if frame[_LANE_KEY].n_unique() != frame.height:
                raise ValueError(
                    f"metric {name!r} reports a lane more than once: the lane set check "
                    "passes on a repeated lane and the join then fans it out against every "
                    "other metric's single row for it"
                )
            lane_frames.append(frame)
        else:
            raise ValueError(
                f"metric {name!r} returned columns {frame.columns}: a run-grain metric "
                f"returns exactly ['{name}'] and a lane-grain metric exactly "
                f"['{_LANE_KEY}', '{name}']"
            )

    # Every table is built before any of them is written, so a metric that disagrees with
    # its neighbours leaves the previous scoring of this run intact rather than half of it
    # overwritten by a scoring that raised.
    lane_table = _lane_table(lane_frames)
    run_table = _run_table(run_frames)
    document = _definitions_document(list(computations), definitions)

    # The one path this package builds to write rather than to read; the loader owns every
    # read path (see its CONTRACT). Nothing else writes here and nothing reads it (ST-D30),
    # so the partition is replaced whole rather than written over in place.
    metrics_dir = run.root / METRICS_DIR
    if metrics_dir.exists():
        shutil.rmtree(metrics_dir)
    metrics_dir.mkdir(parents=True)
    run_table.write_parquet(metrics_dir / RUN_TABLE_FILE_NAME)
    lane_table.write_parquet(metrics_dir / LANE_TABLE_FILE_NAME)
    (metrics_dir / DEFINITIONS_FILE_NAME).write_text(
        json.dumps(document, indent=_JSON_INDENT_SPACES, sort_keys=True, ensure_ascii=False) + "\n"
    )
    return metrics_dir
