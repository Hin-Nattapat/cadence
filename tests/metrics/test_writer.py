import hashlib
import json
from types import MappingProxyType

import polars as pl
import pytest

from cadence.metrics import writer
from cadence.metrics.loader import RunDirectory
from cadence.metrics.registry import (
    MetricDefinition,
    Population,
    QuantityKind,
    registered_metrics,
    scalar_frame,
)
from cadence.metrics.writer import (
    DEFINITIONS_FILE_NAME,
    LANE_TABLE_FILE_NAME,
    RUN_TABLE_FILE_NAME,
    write_metrics,
)
from conftest import write_manifest_json

_RUN_DIR_FIXTURES = ["turning_run_dir", "oversaturated_run_dir"]

# Spec §3.1: s0_turning drains, so its unfinished-trip population is empty and every mean
# over it is a null rather than a zero (trip.py's convention). Its teleport count is zero,
# so the completion rate of teleported vehicles has an empty denominator too. Every other
# run-grain metric has a non-empty population there, and the oversaturated fixture has a
# non-empty one for all nineteen.
_TURNING_NULL_METRIC_NAMES = frozenset(
    {
        "time_in_network_at_horizon_mean_unfinished_s_v1",
        "waiting_time_mean_unfinished_s_v1",
        "time_loss_mean_unfinished_s_v1",
        "completion_rate_teleported_ratio_v1",
    }
)


def _definition(name: str, **overrides: object) -> MetricDefinition:
    fields: dict[str, object] = {
        "name": name,
        "version": 1,
        "definition": f"{name}, declared by a test",
        "unit": "s",
        "population": Population.RUN,
        "quantity_kind": QuantityKind.STOCK,
        "input_fields": ("time_s",),
        "aggregation": "max",
        "limitations": (),
        "config_dependencies": MappingProxyType({}),
        "thresholds": None,
    }
    fields.update(overrides)
    return MetricDefinition(**fields)  # type: ignore[arg-type]


def _install_registry(monkeypatch, computations, definitions=None) -> None:
    # The writer reads the registry through two module-level names; a test that replaces
    # only the computations would have the definitions file describe metrics nobody wrote.
    declared = definitions or {name: _definition(name) for name in computations}
    monkeypatch.setattr(
        writer, "registered_computations", lambda: dict(sorted(computations.items()))
    )
    monkeypatch.setattr(writer, "registered_metrics", lambda: declared)


def _scratch_run(tmp_path) -> RunDirectory:
    # No table is read: every computation below is a fake that ignores the run directory.
    # The manifest is written because RunDirectory is constructed over a real root.
    write_manifest_json(tmp_path)
    return RunDirectory(tmp_path)


def _digests(metrics_dir, file_names) -> dict[str, str]:
    return {
        name: hashlib.sha256((metrics_dir / name).read_bytes()).hexdigest() for name in file_names
    }


def _lane_frame(name: str, lane_ids: list[str], values: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {"lane_id": lane_ids, name: values},
        schema={"lane_id": pl.String, name: pl.Float64},
    )


def test_run_grain_metrics_are_one_row_in_registry_name_order(tmp_path, monkeypatch):
    _install_registry(
        monkeypatch,
        {
            "zulu_s_v1": lambda run: scalar_frame("zulu_s_v1", 2.0),
            "alpha_s_v1": lambda run: scalar_frame("alpha_s_v1", 1.0),
        },
    )

    metrics_dir = write_metrics(_scratch_run(tmp_path))

    frame = pl.read_parquet(metrics_dir / RUN_TABLE_FILE_NAME)
    assert metrics_dir == tmp_path / "metrics"
    assert frame.height == 1
    # Sorted name order, not the order the fakes were declared in: the file must not depend
    # on which module imported which first.
    assert frame.columns == ["alpha_s_v1", "zulu_s_v1"]
    assert frame.row(0) == (1.0, 2.0)


def test_lane_grain_metrics_join_on_lane_id_and_sort_by_it(tmp_path, monkeypatch):
    _install_registry(
        monkeypatch,
        {
            "zulu_m_v1": lambda run: _lane_frame("zulu_m_v1", ["b_0", "a_0"], [4.0, 3.0]),
            "alpha_m_v1": lambda run: _lane_frame("alpha_m_v1", ["a_0", "b_0"], [1.0, 2.0]),
            "mike_s_v1": lambda run: scalar_frame("mike_s_v1", 5.0),
        },
    )

    metrics_dir = write_metrics(_scratch_run(tmp_path))

    frame = pl.read_parquet(metrics_dir / LANE_TABLE_FILE_NAME)
    assert frame.columns == ["lane_id", "alpha_m_v1", "zulu_m_v1"]
    # The two fakes disagree on row order, so a concatenation rather than a join would pair
    # a_0's value with b_0's.
    assert frame.rows() == [("a_0", 1.0, 3.0), ("b_0", 2.0, 4.0)]


def test_a_run_with_no_lane_grain_metric_still_writes_a_readable_lane_table(tmp_path, monkeypatch):
    _install_registry(monkeypatch, {"alpha_s_v1": lambda run: scalar_frame("alpha_s_v1", 1.0)})

    metrics_dir = write_metrics(_scratch_run(tmp_path))

    frame = pl.read_parquet(metrics_dir / LANE_TABLE_FILE_NAME)
    assert frame.columns == ["lane_id"]
    assert frame.height == 0


def test_a_frame_that_is_neither_grain_names_the_metric_and_what_it_returned(tmp_path, monkeypatch):
    _install_registry(
        monkeypatch,
        {
            "alpha_s_v1": lambda run: pl.DataFrame(
                {"time_s": [1.0], "alpha_s_v1": [2.0]},
            )
        },
    )

    with pytest.raises(ValueError, match="alpha_s_v1") as caught:
        write_metrics(_scratch_run(tmp_path))
    assert "time_s" in str(caught.value)


def test_a_frame_whose_value_column_is_misnamed_is_not_a_grain(tmp_path, monkeypatch):
    # The column carries the metric's identity in the output file, so a frame naming it
    # anything else is a metric that would be written under the wrong name.
    _install_registry(monkeypatch, {"alpha_s_v1": lambda run: scalar_frame("alpha_seconds", 1.0)})

    with pytest.raises(ValueError, match="alpha_s_v1"):
        write_metrics(_scratch_run(tmp_path))


def test_lane_grain_metrics_over_different_lane_sets_are_refused(tmp_path, monkeypatch):
    # Joining these would silently produce a null for the lane one metric never reported,
    # which is Task 7's "empty population" signal used for something it does not mean.
    _install_registry(
        monkeypatch,
        {
            "alpha_m_v1": lambda run: _lane_frame("alpha_m_v1", ["a_0", "b_0"], [1.0, 2.0]),
            "zulu_m_v1": lambda run: _lane_frame("zulu_m_v1", ["a_0"], [3.0]),
        },
    )

    with pytest.raises(ValueError, match="zulu_m_v1"):
        write_metrics(_scratch_run(tmp_path))


def test_a_run_grain_metric_returning_more_than_one_row_names_the_metric(tmp_path, monkeypatch):
    # Columns alone do not make a run score: a two-row frame passes the name check and then
    # either writes a two-row run.parquet or raises a polars ShapeError naming no metric.
    _install_registry(
        monkeypatch,
        {
            "alpha_s_v1": lambda run: pl.DataFrame(
                {"alpha_s_v1": [1.0, 2.0]}, schema={"alpha_s_v1": pl.Float64}
            )
        },
    )

    with pytest.raises(ValueError, match="alpha_s_v1") as caught:
        write_metrics(_scratch_run(tmp_path))
    assert "2 rows" in str(caught.value)


def test_a_lane_grain_metric_reporting_one_lane_twice_is_refused(tmp_path, monkeypatch):
    # The lane-set check compares sets, so a duplicate passes it and the inner join then
    # fans the repeated lane out against every other metric's single row for it.
    _install_registry(
        monkeypatch,
        {
            "alpha_m_v1": lambda run: _lane_frame(
                "alpha_m_v1", ["a_0", "a_0", "b_0"], [1.0, 2.0, 3.0]
            ),
            "zulu_m_v1": lambda run: _lane_frame("zulu_m_v1", ["a_0", "b_0"], [4.0, 5.0]),
        },
    )

    with pytest.raises(ValueError, match="alpha_m_v1"):
        write_metrics(_scratch_run(tmp_path))


def test_a_registry_with_no_run_grain_metric_is_refused_by_name(tmp_path, monkeypatch):
    # The lane side answers its empty case with a schema-only table; the run side cannot,
    # and without this the failure is `reduce() of empty iterable` from inside functools.
    _install_registry(
        monkeypatch, {"zulu_m_v1": lambda run: _lane_frame("zulu_m_v1", ["a_0"], [1.0])}
    )

    with pytest.raises(ValueError, match="no run-grain metric"):
        write_metrics(_scratch_run(tmp_path))


def test_definitions_json_carries_every_written_metric(tmp_path, monkeypatch):
    computations = {
        "alpha_s_v1": lambda run: scalar_frame("alpha_s_v1", 1.0),
        "zulu_m_v1": lambda run: _lane_frame("zulu_m_v1", ["a_0"], [3.0]),
    }
    _install_registry(
        monkeypatch,
        computations,
        definitions={
            "alpha_s_v1": _definition("alpha_s_v1"),
            "zulu_m_v1": _definition(
                "zulu_m_v1",
                unit="m",
                population=Population.LANE_STEPS,
                quantity_kind=QuantityKind.FLOW,
                limitations=("assumes a homogeneous fleet (spec §5.3)",),
            ),
        },
    )

    metrics_dir = write_metrics(_scratch_run(tmp_path))

    expected = {
        "alpha_s_v1": {
            "definition": "alpha_s_v1, declared by a test",
            "limitations": [],
            "name": "alpha_s_v1",
            "population": "run",
            "quantity_kind": "stock",
            "unit": "s",
            "version": 1,
        },
        "zulu_m_v1": {
            "definition": "zulu_m_v1, declared by a test",
            "limitations": ["assumes a homogeneous fleet (spec §5.3)"],
            "name": "zulu_m_v1",
            "population": "lane_steps",
            "quantity_kind": "flow",
            "unit": "m",
            "version": 1,
        },
    }
    text = (metrics_dir / DEFINITIONS_FILE_NAME).read_text()
    assert json.loads(text) == expected
    # ST-D29's limitations only reach a reader if the file is one a person can read in a
    # diff, so the formatting is part of the contract rather than json.dumps' default.
    # ensure_ascii would render the § of a limitation as \u00a7 in the one file whose
    # readability is the point of writing it.
    assert text == json.dumps(expected, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert "§5.3" in text


def test_a_second_write_replaces_the_first(tmp_path, monkeypatch):
    run = _scratch_run(tmp_path)
    _install_registry(monkeypatch, {"alpha_s_v1": lambda run: scalar_frame("alpha_s_v1", 1.0)})
    metrics_dir = write_metrics(run)
    # ST-D24 is a promise about re-scoring, so the output shape changing between two
    # scorings is the normal case, not the exotic one. A table the registry stopped
    # emitting has to leave with it: left beside the new three, nothing says it is stale.
    (metrics_dir / "movement.parquet").write_text("a table an older registry wrote")

    _install_registry(monkeypatch, {"zulu_s_v1": lambda run: scalar_frame("zulu_s_v1", 2.0)})
    metrics_dir = write_metrics(run)

    assert pl.read_parquet(metrics_dir / RUN_TABLE_FILE_NAME).columns == ["zulu_s_v1"]
    assert json.loads((metrics_dir / DEFINITIONS_FILE_NAME).read_text()).keys() == {"zulu_s_v1"}
    assert sorted(path.name for path in metrics_dir.iterdir()) == sorted(
        (RUN_TABLE_FILE_NAME, LANE_TABLE_FILE_NAME, DEFINITIONS_FILE_NAME)
    )


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_the_written_columns_are_exactly_the_registered_metrics(request, run_dir_fixture):
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))

    metrics_dir = write_metrics(run)

    run_frame = pl.read_parquet(metrics_dir / RUN_TABLE_FILE_NAME)
    lane_frame = pl.read_parquet(metrics_dir / LANE_TABLE_FILE_NAME)
    written = set(run_frame.columns) | (set(lane_frame.columns) - {"lane_id"})
    declared = set(registered_metrics())
    # Both directions (Task 5 Step 2): a subset check passes while a metric quietly stops
    # being emitted, and the other way while a column is written that nothing declares.
    assert written == declared
    assert set(json.loads((metrics_dir / DEFINITIONS_FILE_NAME).read_text())) == declared
    assert not set(run_frame.columns) & set(lane_frame.columns)
    assert run_frame.height == 1
    assert lane_frame.height == run.topology("lane").height


@pytest.mark.sumo
def test_a_draining_run_writes_a_null_only_where_the_population_is_empty(turning_run_dir):
    run = RunDirectory(turning_run_dir)

    metrics_dir = write_metrics(run)

    run_frame = pl.read_parquet(metrics_dir / RUN_TABLE_FILE_NAME)
    null_names = {name for name in run_frame.columns if run_frame[name].null_count() == 1}
    assert null_names == _TURNING_NULL_METRIC_NAMES
    lane_frame = pl.read_parquet(metrics_dir / LANE_TABLE_FILE_NAME)
    assert lane_frame.null_count().row(0) == (0,) * lane_frame.width


@pytest.mark.sumo
def test_an_oversaturated_run_writes_a_number_in_every_column(oversaturated_run_dir):
    run = RunDirectory(oversaturated_run_dir)

    metrics_dir = write_metrics(run)

    for file_name in (RUN_TABLE_FILE_NAME, LANE_TABLE_FILE_NAME):
        frame = pl.read_parquet(metrics_dir / file_name)
        assert frame.null_count().row(0) == (0,) * frame.width


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_writing_twice_produces_byte_identical_files(request, run_dir_fixture):
    # ST-D24: a metric re-scores historical runs, so a second scoring of the same run has
    # to be the same artifact. A writer that is not idempotent breaks that on the first
    # re-score, and the failure would surface as a diff nobody can attribute.
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    file_names = (RUN_TABLE_FILE_NAME, LANE_TABLE_FILE_NAME, DEFINITIONS_FILE_NAME)

    metrics_dir = write_metrics(run)
    first = _digests(metrics_dir, file_names)
    write_metrics(run)
    second = _digests(metrics_dir, file_names)

    assert first == second


@pytest.mark.sumo
def test_scoring_leaves_every_cached_table_as_it_was_read(turning_run_dir):
    # loader.py's CONTRACT says a caller must never mutate the shared frame it is handed.
    # That holds today by the shape of polars' API, which is a claim no test makes; a metric
    # written with an in-place idiom would break every metric scored after it in the walk.
    run = RunDirectory(turning_run_dir)

    write_metrics(run)

    cached = dict(run._tables)
    assert cached, "no table was read, so the contract was never exercised"
    for (partition, table), frame in cached.items():
        on_disk = pl.read_parquet(turning_run_dir / partition / f"{table}.parquet")
        assert frame.equals(on_disk), f"{partition}/{table} was mutated during scoring"
