"""CADENCE command line interface."""

from __future__ import annotations

import json
import shutil
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError

from cadence.control.events import SignalEvent
from cadence.control.executor import SignalExecutor
from cadence.control.plan import SignalPlan, build_signal_plans
from cadence.metrics.loader import RunDirectory
from cadence.metrics.writer import write_metrics
from cadence.simulation.artifacts import RunRecorder
from cadence.simulation.events import EventLog
from cadence.simulation.manifest import (
    RunManifest,
    TerminationReason,
    build_manifest,
    compare_manifests,
)
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths, load_scenario
from cadence.simulation.signal_plan_file import SignalPlanFile, load_signal_plan_file
from cadence.simulation.state import CanonicalTrafficState
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.validation import validate_network
from cadence.simulation.topology import NetworkTopology
from cadence.types import IntersectionId, PhaseId

app = typer.Typer(help="CADENCE traffic control experimentation platform.")
REPO_ROOT = Path(__file__).resolve().parents[2]

# No controller exists before M2 (ARCH-D01); "none" is the harness running the scenario
# with no control logic applied, versioned like any other controller identity (`AP-06`).
NO_CONTROLLER_ID = "none"
NO_CONTROLLER_VERSION = "v1"

# Until P2-04's `--controller` exists, a request schedule stands in for one, and the manifest
# must not claim there was none.
REQUEST_SCHEDULE_CONTROLLER_ID = "request_schedule"
REQUEST_SCHEDULE_CONTROLLER_VERSION = "v1"

# Same float-noise tolerance as _CLOCK_TOLERANCE_S in control/executor.py: simulated time is
# a running sum of the step length, so "due" must not turn on the last bit.
_REQUEST_DUE_TOLERANCE_S = 1e-9

# A manifest can carry cadence_dirty without a digest (an older writer, a hand-edited
# manifest); the refusal still has to name what it saw rather than print an empty field.
NO_DIGEST = "not recorded"

DIRTY_TREE_WARNING = (
    "WARNING: this run was made from a dirty working tree, so cadence_commit does not\n"
    "         identify the code that produced it. The result is not reproducible."
)


@dataclass(frozen=True, slots=True)
class ScheduledRequest:
    time_s: float
    intersection_id: IntersectionId
    phase_id: PhaseId


def run_scenario(
    scenario_root: Path,
    output_root: Path,
    *,
    seed: int,
    binding: BindingKind,
    request_schedule: Sequence[ScheduledRequest] | None = None,
) -> Path:
    config, paths = load_scenario(scenario_root)
    controller_id = NO_CONTROLLER_ID
    controller_version = NO_CONTROLLER_VERSION
    envelope = None
    if request_schedule is not None:
        controller_id = REQUEST_SCHEDULE_CONTROLLER_ID
        controller_version = REQUEST_SCHEDULE_CONTROLLER_VERSION
        if paths.signal_plan is None:
            raise ValueError(
                "a request schedule needs a signal_plan.yaml; "
                f"scenario {config.scenario_id} has none"
            )
        envelope = load_signal_plan_file(paths.signal_plan, step_length_s=config.step_length_s)
    started = datetime.now(UTC).isoformat()

    stamp = started.replace(":", "").replace("-", "")[:15]
    run_dir = output_root / (
        f"{stamp}__{config.scenario_id}-v{config.scenario_version}"
        f"__{controller_id}-{controller_version}__seed{seed}"
    )
    # exist_ok=False on purpose: the stamp is second-resolution, so two runs of the same
    # scenario and seed starting in the same second would otherwise clobber the first's
    # manifest and events. Losing an artifact silently is worse than failing loudly.
    run_dir.mkdir(parents=True, exist_ok=False)

    log = EventLog()
    steps = 0
    tripinfo_xml = run_dir / "tripinfo.xml"
    ticking = False
    try:
        with SumoConnection(
            config, paths, seed=seed, binding=binding, tripinfo_path=tripinfo_xml
        ) as connection:
            plans: Mapping[IntersectionId, SignalPlan] = {}
            pending: _PendingRequests | None = None
            if request_schedule is not None and envelope is not None:
                plans = _plans_for_schedule(connection.topology, envelope, request_schedule)
                pending = _PendingRequests(request_schedule)
            ticking = True
            executors: Mapping[IntersectionId, SignalExecutor] | None = None
            recorder = RunRecorder(run_dir, connection.topology)
            while not connection.is_finished():
                result = connection.step()
                if pending is not None:
                    if executors is None:
                        executors = start_executors(
                            plans, result.state, step_length_s=config.step_length_s
                        )
                    recorder.record_signal_events(
                        tick_executors(
                            connection,
                            executors,
                            state=result.state,
                            requests=pending.due(result.time_s),
                        )
                    )
                log.append(result.events)
                recorder.record(result.state, result.teleports, connection.read_ground_truth())
                steps += 1
            terminal_time_s = connection.time_s()
            unmatched_traversal_count = connection.unmatched_traversals()
            termination_reason = connection.termination_reason()
            # Read before the connection closes, unlike record(): this cross-tab accumulates
            # over the whole run and is emitted once rather than once per step (ST-D31).
            distinct_vehicle_totals = connection.read_distinct_vehicle_totals()
    except ValueError:
        # A run refused before its first step never ran, so it leaves no run directory
        # behind; with exist_ok=False a leftover would also fail a retry in the same second.
        # A run that fails after it started keeps its directory, as above.
        if not ticking:
            shutil.rmtree(run_dir)
        raise

    if termination_reason is None:
        # The loop only exits when is_finished() is true, so neither condition holding means
        # something stopped it that nobody modelled. Record that honestly rather than
        # refusing to write a manifest for a run that did happen.
        termination_reason = TerminationReason.ABORTED

    finished = datetime.now(UTC).isoformat()
    manifest = build_manifest(
        REPO_ROOT,
        config,
        paths,
        seed=seed,
        binding=binding,
        controller_id=controller_id,
        controller_version=controller_version,
        terminal_time_s=terminal_time_s,
        step_count=steps,
        unmatched_traversal_count=unmatched_traversal_count,
        termination_reason=termination_reason,
        started_at_utc=started,
        finished_at_utc=finished,
    )

    log.to_parquet(run_dir / "events.parquet")
    recorder.record_distinct_vehicle_totals(distinct_vehicle_totals)
    recorder.write()
    recorder.write_tripinfo(tripinfo_xml)
    tripinfo_xml.unlink()
    # Last, so that the manifest's presence means the run finished. run_dir is created
    # before SUMO starts, so a run that dies mid-loop leaves a directory behind; without
    # this ordering it would leave one carrying a complete-looking manifest over a partial
    # or absent set of artifacts, which is the one state a reader cannot detect.
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    return run_dir


def start_executors(
    plans: Mapping[IntersectionId, SignalPlan],
    first: CanonicalTrafficState,
    *,
    step_length_s: float,
) -> Mapping[IntersectionId, SignalExecutor]:
    return {
        intersection_id: SignalExecutor(
            plan, first.intersections[intersection_id], first.time_s, step_length_s
        )
        for intersection_id, plan in plans.items()
    }


def tick_executors(
    connection: SumoConnection,
    executors: Mapping[IntersectionId, SignalExecutor],
    *,
    state: CanonicalTrafficState,
    requests: Mapping[IntersectionId, PhaseId],
) -> tuple[SignalEvent, ...]:
    events: list[SignalEvent] = []
    # Sorted order, so nothing depends on dict iteration (AP-06).
    for intersection_id in sorted(executors):
        commands, tick_events = executors[intersection_id].tick(
            state.intersections[intersection_id], state.time_s, requests.get(intersection_id)
        )
        connection.apply_signal_commands(commands)
        events.extend(tick_events)
    return tuple(events)


def _plans_for_schedule(
    topology: NetworkTopology,
    envelope: SignalPlanFile,
    schedule: Sequence[ScheduledRequest],
) -> Mapping[IntersectionId, SignalPlan]:
    try:
        plans = build_signal_plans(topology, envelope)
    except ValueError as error:
        raise ValueError(f"the request schedule is refused: {error}") from error
    for request in schedule:
        if request.intersection_id not in plans:
            raise ValueError(
                f"a request names intersection {request.intersection_id}, which has "
                f"no signal plan; planned intersections: {sorted(plans)}"
            )
    return plans


class _PendingRequests:
    def __init__(self, schedule: Sequence[ScheduledRequest]) -> None:
        self._queues: dict[IntersectionId, deque[ScheduledRequest]] = {}
        # sorted is stable, so ties keep their schedule position.
        for request in sorted(schedule, key=lambda request: request.time_s):
            self._queues.setdefault(request.intersection_id, deque()).append(request)

    def due(self, now_s: float) -> dict[IntersectionId, PhaseId]:
        # A request is deferred, never dropped, as SIG-D05 treats a pending one: at most one
        # request per intersection is passed per step, and the rest wait their turn.
        due: dict[IntersectionId, PhaseId] = {}
        for intersection_id in sorted(self._queues):
            queue = self._queues[intersection_id]
            if queue and queue[0].time_s <= now_s + _REQUEST_DUE_TOLERANCE_S:
                due[intersection_id] = queue.popleft().phase_id
        return due


def _warn_if_dirty(run_dir: Path) -> None:
    # R-15: the warning, not the fail/warn/hash-the-diff decision, which is deferred to M1.
    # It only helps if it reaches the person running the simulation, at the moment they can
    # still act — so stderr, right after the run, not buried in the manifest alone.
    if _read_manifest(run_dir).cadence_dirty:
        typer.echo(DIRTY_TREE_WARNING, err=True)


def _read_manifest(run_dir: Path) -> RunManifest:
    return RunManifest(**json.loads((run_dir / "manifest.json").read_text()))


@app.command()
def run(
    scenario: Path = typer.Option(..., help="Path to a scenario version directory."),
    output: Path = typer.Option(Path("studies/00-harness/runs"), help="Run output root."),
    seed: int = typer.Option(1, min=0),
    binding: BindingKind = typer.Option(BindingKind.LIBSUMO),
) -> None:
    run_dir = run_scenario(scenario, output, seed=seed, binding=binding)
    typer.echo(f"Run written to {run_dir}")
    _warn_if_dirty(run_dir)


def _build_plans_for_validation(
    config: ScenarioConfig, paths: ScenarioPaths, *, against_the_network: bool
) -> tuple[list[str], Mapping[IntersectionId, SignalPlan]]:
    if paths.signal_plan is None:
        return [], {}
    try:
        envelope = load_signal_plan_file(paths.signal_plan, step_length_s=config.step_length_s)
        if not against_the_network:
            return [], {}
        # Spec §5.2 puts the plan's structural refusals here too, and they can only be
        # decided against the program the network carries. The connection is opened for the
        # topology alone and closed before the plan is built.
        with SumoConnection(
            config, paths, seed=config.default_seed, binding=BindingKind.LIBSUMO
        ) as connection:
            topology = connection.topology
        return [], build_signal_plans(topology, envelope)
    except (ValueError, ValidationError, yaml.YAMLError) as error:
        return [f"signal plan: {error}"], {}


@app.command("validate-scenario")
def validate_scenario(
    scenario: Path = typer.Option(..., help="Path to a scenario version directory."),
) -> None:
    config, paths = load_scenario(scenario)
    problems = validate_network(paths)
    # A network that already failed is not worth starting SUMO on: the plan build would
    # fail for reasons the network problems above already explain.
    signal_plan_problems, plans = _build_plans_for_validation(
        config, paths, against_the_network=not problems
    )
    problems.extend(signal_plan_problems)
    for problem in problems:
        typer.echo(f"FAIL  {problem}")
    if problems:
        raise typer.Exit(code=1)
    typer.echo(f"{config.scenario_id} v{config.scenario_version}: OK")
    typer.echo(f"  network: {paths.network}")
    typer.echo(f"  demand:  {paths.demand}")
    envelope = paths.signal_plan if paths.signal_plan is not None else "none (not controllable)"
    typer.echo(f"  signal plan: {envelope}")
    for intersection_id, plan in sorted(plans.items()):
        typer.echo(f"    {intersection_id}: stages {sorted(plan.stages)}")


@app.command("metrics")
def metrics(
    run_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Path to a completed run directory."
    ),
) -> None:
    """Score a run directory in place, writing its metrics/ partition (ST-D24)."""
    metrics_dir = write_metrics(RunDirectory(run_dir))
    typer.echo(f"Metrics written to {metrics_dir}")


@app.command("verify-run")
def verify_run(
    left: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="A completed run directory."
    ),
    right: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="The run directory to compare it with."
    ),
) -> None:
    """Say whether two runs may share a table (ST-D33), and refuse if either is dirty."""
    left_manifest = _read_manifest(left)
    right_manifest = _read_manifest(right)
    comparison = compare_manifests(left_manifest, right_manifest)
    if not comparison.comparable:
        for run_dir, manifest, dirty in (
            (left, left_manifest, comparison.left_dirty),
            (right, right_manifest, comparison.right_dirty),
        ):
            if dirty:
                # The digest, not just the fact: ST-D11 exists because a boolean cannot tell
                # two runs made from two different uncommitted trees apart, and a refusal
                # that prints neither is the same message for both of them.
                typer.echo(
                    f"REFUSED  {run_dir}: made from a dirty working tree "
                    f"(cadence_dirty_digest {manifest.cadence_dirty_digest or NO_DIGEST}), "
                    "so cadence_commit does not identify the code that produced it "
                    "(ST-D11, M1a spec §9.2)"
                )
        for field, (left_value, right_value) in comparison.mismatched_comparability_fields.items():
            typer.echo(f"MISMATCH {field}: {left_value} != {right_value}")
        raise typer.Exit(code=1)
    typer.echo(f"{comparison.kind}: {left} vs {right}")
    for field, (left_value, right_value) in comparison.intended_differences.items():
        typer.echo(f"  {field}: {left_value} vs {right_value}")


if __name__ == "__main__":
    app()
