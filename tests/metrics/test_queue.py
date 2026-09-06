import polars as pl
import pytest

from cadence.metrics.loader import RunDirectory
from cadence.metrics.queue import (
    compute_halting_delay_total_veh_s_v1,
    compute_queue_length_peak_m_v1,
    compute_waiting_total_peak_s_v1,
)
from cadence.simulation.artifacts import _SCHEMAS
from conftest import write_manifest_json

_LANE_SCHEMA = _SCHEMAS["state/lane"]
_VEHICLE_TYPE_SCHEMA = _SCHEMAS["topology/vehicle_type"]

# SUMO's own default minGap for a passenger vType (spec §5.3): the demand's vType does not
# set it, so this is the value every fixture and hand-built frame here actually carries.
_DEFAULT_MIN_GAP_M = 2.5

_RUN_DIR_FIXTURES = ["turning_run_dir", "oversaturated_run_dir"]


def _write_queue_run(
    tmp_path,
    *,
    lane_rows: list[dict[str, object]],
    vehicle_type_rows: list[dict[str, object]],
    trip_vtypes: list[str],
    step_length_s: float = 1.0,
) -> RunDirectory:
    lane_path = tmp_path / "state" / "lane.parquet"
    lane_path.parent.mkdir(parents=True)
    pl.DataFrame(lane_rows, schema=_LANE_SCHEMA).write_parquet(lane_path)

    vehicle_type_path = tmp_path / "topology" / "vehicle_type.parquet"
    vehicle_type_path.parent.mkdir(parents=True)
    pl.DataFrame(vehicle_type_rows, schema=_VEHICLE_TYPE_SCHEMA).write_parquet(vehicle_type_path)

    tripinfo_path = tmp_path / "evaluation" / "tripinfo.parquet"
    tripinfo_path.parent.mkdir(parents=True)
    pl.DataFrame({"vType": trip_vtypes}, schema={"vType": pl.String}).write_parquet(tripinfo_path)

    write_manifest_json(tmp_path, step_length_s=step_length_s)
    return RunDirectory(tmp_path)


def _lane_row(
    *, time_s: float, lane_id: str, halting: int, vehicles: int, waiting_s: float
) -> dict[str, object]:
    # halting and vehicles are separate arguments because state/lane carries them separately:
    # a metric reading vehicle_count_veh where it means halting_count_veh must be able to
    # produce a different number on this frame than the right one does.
    return {
        "time_s": time_s,
        "lane_id": lane_id,
        "vehicle_count_veh": vehicles,
        "halting_count_veh": halting,
        "mean_speed_mps": 0.0,
        "occupancy_ratio": 0.0,
        "waiting_total_now_s": waiting_s,
    }


def _car_vehicle_type(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "type_id": "car",
        "length_m": 5.0,
        "min_gap_m": _DEFAULT_MIN_GAP_M,
        "max_speed_mps": 13.9,
    }
    row.update(overrides)
    return row


def test_queue_length_peak_m_picks_the_peak_halting_step_per_lane(tmp_path):
    run = _write_queue_run(
        tmp_path,
        lane_rows=[
            # Every step carries more resident vehicles than halting ones, so reading
            # vehicle_count_veh instead of halting_count_veh cannot produce these numbers.
            _lane_row(time_s=0.0, lane_id="A", halting=10, vehicles=14, waiting_s=0.0),
            _lane_row(time_s=1.0, lane_id="A", halting=25, vehicles=30, waiting_s=0.0),
            _lane_row(time_s=2.0, lane_id="A", halting=5, vehicles=28, waiting_s=0.0),
            _lane_row(time_s=0.0, lane_id="B", halting=1, vehicles=9, waiting_s=0.0),
        ],
        vehicle_type_rows=[_car_vehicle_type()],
        trip_vtypes=["car", "car"],
    )
    result = compute_queue_length_peak_m_v1(run)
    assert result.columns == ["lane_id", "queue_length_peak_m_v1"]
    # spec §5.3's own worked example: 25 halting * (5.0 + 2.5) = 187.5 m.
    values = dict(zip(result["lane_id"], result["queue_length_peak_m_v1"], strict=True))
    assert values["A"] == pytest.approx(187.5), values["A"]
    assert values["B"] == pytest.approx(7.5), values["B"]


def test_vehicle_span_selects_structurally_not_by_the_smallest_matching_row(tmp_path):
    # The trap (plan Task 8): SUMO registers DEFAULT_* types beside the demand's own, and
    # DEFAULT_VEHTYPE and DEFAULT_TAXITYPE share one footprint. Here `car` is given 4.5 m so
    # every wrong selection lands somewhere else: row 0 (DEFAULT_BIKETYPE) gives 2.6 m, "any
    # 5.0 m type" gives 7.5 m, "all types" raises on three distinct footprints, and only
    # selecting exactly the type tripinfo names yields 7.0 m.
    run = _write_queue_run(
        tmp_path,
        lane_rows=[_lane_row(time_s=0.0, lane_id="A", halting=1, vehicles=1, waiting_s=0.0)],
        vehicle_type_rows=[
            _car_vehicle_type(type_id="DEFAULT_BIKETYPE", length_m=2.1, min_gap_m=0.5),
            _car_vehicle_type(type_id="DEFAULT_VEHTYPE"),
            _car_vehicle_type(type_id="DEFAULT_TAXITYPE"),
            _car_vehicle_type(type_id="car", length_m=4.5),
        ],
        trip_vtypes=["car"],
    )
    result = compute_queue_length_peak_m_v1(run)
    assert result["queue_length_peak_m_v1"][0] == pytest.approx(7.0), result


def test_vehicle_span_raises_on_a_mixed_fleet_with_different_footprints(tmp_path):
    run = _write_queue_run(
        tmp_path,
        lane_rows=[_lane_row(time_s=0.0, lane_id="A", halting=1, vehicles=1, waiting_s=0.0)],
        vehicle_type_rows=[
            _car_vehicle_type(type_id="car"),
            _car_vehicle_type(type_id="truck", length_m=12.0, min_gap_m=2.5),
        ],
        trip_vtypes=["car", "truck"],
    )
    with pytest.raises(ValueError, match="distinct vehicle footprints"):
        compute_queue_length_peak_m_v1(run)


def test_vehicle_span_raises_when_a_used_type_is_missing_from_the_topology_table(tmp_path):
    run = _write_queue_run(
        tmp_path,
        lane_rows=[_lane_row(time_s=0.0, lane_id="A", halting=1, vehicles=1, waiting_s=0.0)],
        vehicle_type_rows=[_car_vehicle_type(type_id="car")],
        trip_vtypes=["car", "ghost"],
    )
    with pytest.raises(ValueError, match="do not match"):
        compute_queue_length_peak_m_v1(run)


def test_vehicle_span_raises_the_zero_departure_message_on_an_empty_tripinfo(tmp_path):
    # A run with zero departures names no vType at all -- the metric's own limitation. It
    # must say that, not report a fleet of "0 distinct vehicle footprints".
    run = _write_queue_run(
        tmp_path,
        lane_rows=[_lane_row(time_s=0.0, lane_id="A", halting=1, vehicles=1, waiting_s=0.0)],
        vehicle_type_rows=[_car_vehicle_type(type_id="car")],
        trip_vtypes=[],
    )
    with pytest.raises(ValueError, match="empty on a run with zero departures"):
        compute_queue_length_peak_m_v1(run)


def test_waiting_total_peak_s_is_a_peak_never_a_sum(tmp_path):
    run = _write_queue_run(
        tmp_path,
        lane_rows=[
            _lane_row(time_s=0.0, lane_id="A", halting=0, vehicles=1, waiting_s=10.0),
            _lane_row(time_s=1.0, lane_id="A", halting=0, vehicles=1, waiting_s=40.0),
            _lane_row(time_s=2.0, lane_id="A", halting=0, vehicles=1, waiting_s=15.0),
            # Lane B peaks higher than A: a derivation that collapses the group_by and takes
            # the whole frame's maximum reports 90.0 for A as well.
            _lane_row(time_s=0.0, lane_id="B", halting=0, vehicles=1, waiting_s=90.0),
            _lane_row(time_s=1.0, lane_id="B", halting=0, vehicles=1, waiting_s=20.0),
        ],
        vehicle_type_rows=[_car_vehicle_type()],
        trip_vtypes=["car"],
    )
    result = compute_waiting_total_peak_s_v1(run)
    assert result.columns == ["lane_id", "waiting_total_peak_s_v1"]
    peaks = dict(zip(result["lane_id"], result["waiting_total_peak_s_v1"], strict=True))
    # ST-D28: 40.0, the peak -- never 65.0, the sum across steps.
    assert peaks["A"] == pytest.approx(40.0), peaks
    assert peaks["B"] == pytest.approx(90.0), peaks


def test_halting_delay_total_veh_s_multiplies_by_step_length_from_the_manifest(tmp_path):
    run = _write_queue_run(
        tmp_path,
        lane_rows=[
            _lane_row(time_s=0.0, lane_id="A", halting=3, vehicles=7, waiting_s=0.0),
            _lane_row(time_s=1.0, lane_id="A", halting=2, vehicles=7, waiting_s=0.0),
            _lane_row(time_s=0.0, lane_id="B", halting=1, vehicles=7, waiting_s=0.0),
        ],
        vehicle_type_rows=[_car_vehicle_type()],
        trip_vtypes=["car"],
        step_length_s=5.0,
    )
    result = compute_halting_delay_total_veh_s_v1(run)
    assert result.columns == ["halting_delay_total_veh_s_v1"]
    # ST-D28: Σ halting_count_veh * Δt = (3 + 2 + 1) * 5.0 = 30.0 veh_s -- never Δt = 1
    # assumed, never a sum of a `_now_s` quantity, and never the resident-vehicle count.
    assert result["halting_delay_total_veh_s_v1"][0] == pytest.approx(30.0), result


@pytest.mark.sumo
def test_queue_length_peak_m_on_the_oversaturated_fixture(oversaturated_run_dir):
    run = RunDirectory(oversaturated_run_dir)
    result = compute_queue_length_peak_m_v1(run)
    peaks = dict(zip(result["lane_id"], result["queue_length_peak_m_v1"], strict=True))
    # spec §5.3's own worked example on the committed fixture: left0A0_0, length 189.6 m,
    # peak 25 halting -> 25 * 7.5 = 187.5 m.
    assert peaks["left0A0_0"] == pytest.approx(187.5), peaks["left0A0_0"]
    # Measured on the committed fixture: bottom0A0_0 peaks at 24 halting against 25 resident
    # vehicles -- the one lane where reading the wrong column of state/lane shows up, at
    # 187.5 m instead of 24 * 7.5 = 180.0 m.
    assert peaks["bottom0A0_0"] == pytest.approx(180.0), peaks["bottom0A0_0"]


@pytest.mark.sumo
def test_the_fixture_fleet_is_the_one_type_tripinfo_names(oversaturated_run_dir):
    # The plan's trap, stated as a fact about the fixture rather than as prose: the topology
    # table offers several types to pick wrongly from, and exactly one of them was driven.
    run = RunDirectory(oversaturated_run_dir)
    assert set(run.evaluation("tripinfo")["vType"].unique().to_list()) == {"car"}
    assert run.topology("vehicle_type").height > 1


@pytest.mark.sumo
@pytest.mark.parametrize("run_dir_fixture", _RUN_DIR_FIXTURES)
def test_queue_length_peak_never_exceeds_the_lane_it_is_measured_on(request, run_dir_fixture):
    # CLAUDE.md §7's named property: back-of-queue distance is a length along a lane, so a
    # peak longer than the lane means the formula, the fleet footprint or the halting count
    # is wrong. The tightest measured margin is 2.1 m, on the four lanes that fill completely.
    run = RunDirectory(request.getfixturevalue(run_dir_fixture))
    peaks = compute_queue_length_peak_m_v1(run)
    lanes = run.topology("lane").select("lane_id", "length_m")
    joined = peaks.join(lanes, on="lane_id", how="left")
    assert joined["length_m"].null_count() == 0, joined
    over = joined.filter(pl.col("queue_length_peak_m_v1") > pl.col("length_m"))
    assert over.height == 0, f"{run_dir_fixture}: {over}"
