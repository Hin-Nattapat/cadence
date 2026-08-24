"""CADENCE command line interface."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from cadence.simulation.artifacts import RunRecorder
from cadence.simulation.events import EventLog
from cadence.simulation.manifest import RunManifest, TerminationReason, build_manifest
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.validation import validate_network

app = typer.Typer(help="CADENCE traffic control experimentation platform.")
REPO_ROOT = Path(__file__).resolve().parents[2]

# No controller exists before M2 (ARCH-D01); "none" is the harness running the scenario
# with no control logic applied, versioned like any other controller identity (`AP-06`).
NO_CONTROLLER_ID = "none"
NO_CONTROLLER_VERSION = "v1"

DIRTY_TREE_WARNING = (
    "WARNING: this run was made from a dirty working tree, so cadence_commit does not\n"
    "         identify the code that produced it. The result is not reproducible."
)


def run_scenario(
    scenario_root: Path,
    output_root: Path,
    *,
    seed: int,
    binding: BindingKind,
) -> Path:
    config, paths = load_scenario(scenario_root)
    started = datetime.now(UTC).isoformat()

    stamp = started.replace(":", "").replace("-", "")[:15]
    run_dir = output_root / (
        f"{stamp}__{config.scenario_id}-v{config.scenario_version}"
        f"__{NO_CONTROLLER_ID}-{NO_CONTROLLER_VERSION}__seed{seed}"
    )
    # exist_ok=False on purpose: the stamp is second-resolution, so two runs of the same
    # scenario and seed starting in the same second would otherwise clobber the first's
    # manifest and events. Losing an artifact silently is worse than failing loudly.
    run_dir.mkdir(parents=True, exist_ok=False)

    log = EventLog()
    steps = 0
    tripinfo_xml = run_dir / "tripinfo.xml"
    with SumoConnection(
        config, paths, seed=seed, binding=binding, tripinfo_path=tripinfo_xml
    ) as connection:
        recorder = RunRecorder(run_dir, connection.topology)
        while not connection.is_finished():
            result = connection.step()
            log.append(result.events)
            recorder.record(result.state, result.teleports, connection.read_ground_truth())
            steps += 1
        terminal_time_s = connection.time_s()
        unmatched_traversal_count = connection.unmatched_traversals()
        termination_reason = connection.termination_reason()

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
        controller_id=NO_CONTROLLER_ID,
        controller_version=NO_CONTROLLER_VERSION,
        terminal_time_s=terminal_time_s,
        step_count=steps,
        unmatched_traversal_count=unmatched_traversal_count,
        termination_reason=termination_reason,
        started_at_utc=started,
        finished_at_utc=finished,
    )

    log.to_parquet(run_dir / "events.parquet")
    recorder.write()
    recorder.write_tripinfo(tripinfo_xml)
    tripinfo_xml.unlink()
    # Last, so that the manifest's presence means the run finished. run_dir is created
    # before SUMO starts, so a run that dies mid-loop leaves a directory behind; without
    # this ordering it would leave one carrying a complete-looking manifest over a partial
    # or absent set of artifacts, which is the one state a reader cannot detect.
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    return run_dir


def _warn_if_dirty(run_dir: Path) -> None:
    # R-15: the warning, not the fail/warn/hash-the-diff decision, which is deferred to M1.
    # It only helps if it reaches the person running the simulation, at the moment they can
    # still act — so stderr, right after the run, not buried in the manifest alone.
    manifest = RunManifest(**json.loads((run_dir / "manifest.json").read_text()))
    if manifest.cadence_dirty:
        typer.echo(DIRTY_TREE_WARNING, err=True)


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


@app.command("validate-scenario")
def validate_scenario(
    scenario: Path = typer.Option(..., help="Path to a scenario version directory."),
) -> None:
    config, paths = load_scenario(scenario)
    problems = validate_network(paths)
    for problem in problems:
        typer.echo(f"FAIL  {problem}")
    if problems:
        raise typer.Exit(code=1)
    typer.echo(f"{config.scenario_id} v{config.scenario_version}: OK")
    typer.echo(f"  network: {paths.network}")
    typer.echo(f"  demand:  {paths.demand}")


if __name__ == "__main__":
    app()
