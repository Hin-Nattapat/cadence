import itertools
import json

import polars as pl
import pytest

from cadence.cli import ScheduledRequest, run_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.types import IntersectionId, PhaseId

pytestmark = pytest.mark.sumo

A0 = IntersectionId("A0")
TURNING = "scenarios/s0_turning/v1"
# s0_turning's signal_plan.yaml.
MAX_GREEN_S = 60.0
# s0_turning's scenario.yaml.
STEP_LENGTH_S = 1.0
# s0_turning's A0 program: phases 1 and 3 are its yellows, 0 and 2 its stages.
TRANSITION_PHASES = (1, 3)
STAGE_PHASES = (0, 2)
# One request at 20 s, then max-green holds of 61 s over a 600 s run, gives about nine
# transitions; five keeps the check meaningful without pinning the exact count.
MIN_COMPLETE_TRANSITIONS = 5


@pytest.fixture(
    scope="module",
    params=[BindingKind.TRACI, BindingKind.LIBSUMO],
    ids=["traci", "libsumo"],
)
def scheduled_run(request, repo_root, tmp_path_factory):
    return run_scenario(
        repo_root / TURNING,
        tmp_path_factory.mktemp("scheduled"),
        seed=1,
        binding=request.param,
        request_schedule=(ScheduledRequest(20.0, A0, PhaseId(2)),),
    )


def _intersection_rows(run_dir) -> pl.DataFrame:
    return (
        pl.read_parquet(run_dir / "state/intersection.parquet")
        .filter(pl.col("intersection_id") == str(A0))
        .sort("time_s")
    )


def test_a_requested_stage_follows_its_full_yellow(scheduled_run):
    rows = _intersection_rows(scheduled_run).filter(pl.col("time_s").is_between(20.0, 24.0))
    assert rows["time_s"].to_list() == [20.0, 21.0, 22.0, 23.0, 24.0]
    assert rows["phase_index"].to_list() == [0, 1, 1, 1, 2]


def test_the_transition_is_recorded_as_three_events(scheduled_run):
    events = pl.read_parquet(scheduled_run / "state/signal_event.parquet")
    first_three = events.select("time_s", "kind", "from_phase_id", "to_phase_id").head(3).rows()
    assert first_three == [
        (20.0, "stage_requested", 0, 2),
        (20.0, "transition_started", 0, 2),
        (23.0, "stage_entered", 1, 2),
    ]


def test_a_scheduled_run_names_its_controller(scheduled_run):
    manifest = json.loads((scheduled_run / "manifest.json").read_text())
    assert manifest["controller_id"] == "request_schedule"
    assert manifest["controller_version"] == "v1"
    assert "__request_schedule-v1__" in scheduled_run.name


def test_every_complete_transition_phase_lasts_its_program_duration(scheduled_run):
    # Pins SIM-D04: if SUMO's own switch fired first, a transition would read one step
    # short, or reconciliation would raise.
    program = pl.read_parquet(scheduled_run / "topology/tls_program.parquet")
    duration_by_phase = dict(program.select("phase_index", "duration_s").unique().rows())
    phase_indices = _intersection_rows(scheduled_run)["phase_index"].to_list()
    runs = [(phase, len(list(rows))) for phase, rows in itertools.groupby(phase_indices)]
    complete = [(phase, steps) for phase, steps in runs[1:-1] if phase in TRANSITION_PHASES]
    assert len(complete) >= MIN_COMPLETE_TRANSITIONS
    for phase, steps in complete:
        assert steps * STEP_LENGTH_S == duration_by_phase[phase]


def test_phase_elapsed_stays_within_its_envelope(scheduled_run):
    rows = _intersection_rows(scheduled_run)
    stage = rows.filter(pl.col("phase_index").is_in(STAGE_PHASES))
    transition = rows.filter(pl.col("phase_index").is_in(TRANSITION_PHASES))
    program = pl.read_parquet(scheduled_run / "topology/tls_program.parquet")
    duration_by_phase = dict(program.select("phase_index", "duration_s").unique().rows())
    assert (stage["phase_elapsed_s"] <= MAX_GREEN_S + STEP_LENGTH_S).all()
    for phase, elapsed_s in transition.select("phase_index", "phase_elapsed_s").rows():
        assert elapsed_s <= duration_by_phase[phase]
    assert stage["phase_elapsed_s"].max() >= MAX_GREEN_S


def test_two_requests_due_together_are_passed_on_consecutive_steps(repo_root, tmp_path):
    run_dir = run_scenario(
        repo_root / TURNING,
        tmp_path,
        seed=1,
        binding=BindingKind.LIBSUMO,
        request_schedule=(
            ScheduledRequest(20.0, A0, PhaseId(2)),
            ScheduledRequest(20.0, A0, PhaseId(0)),
        ),
    )
    events = pl.read_parquet(run_dir / "state/signal_event.parquet")
    rows = (
        events.filter(pl.col("time_s") <= 21.0)
        .select("time_s", "kind", "from_phase_id", "to_phase_id", "reason")
        .rows()
    )
    assert rows == [
        (20.0, "stage_requested", 0, 2, None),
        (20.0, "transition_started", 0, 2, None),
        (21.0, "request_deferred", 2, 0, "in_transition"),
    ]
