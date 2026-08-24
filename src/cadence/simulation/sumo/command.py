"""Builds the SUMO argument vector for a scenario run.

Every flag that affects determinism or failure behaviour is set explicitly, so that a SUMO
upgrade cannot change experiment semantics through a changed default (AP-06).
"""

from __future__ import annotations

from pathlib import Path

from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.sumo.binding import sumo_home


def build_sumo_command(
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    use_gui: bool = False,
    tripinfo_path: Path | None = None,
) -> list[str]:
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")

    binary = sumo_home() / "bin" / ("sumo-gui" if use_gui else "sumo")
    arguments = [
        str(binary),
        "--net-file",
        str(paths.network),
        "--route-files",
        str(paths.demand),
        "--begin",
        str(config.begin_s),
        "--end",
        str(config.end_s),
        "--step-length",
        str(config.step_length_s),
        "--seed",
        str(seed),
        "--random",
        "false",
        "--time-to-teleport",
        str(config.time_to_teleport_s),
        "--no-step-log",
        "true",
        "--duration-log.disable",
        "true",
        # SUMO documents this as "length of time interval", i.e. a duration, not an
        # absolute time. Its 100 s default would truncate waiting metrics on a longer run.
        "--waiting-time-memory",
        str(config.end_s - config.begin_s),
        # GroundTruthReader caches each vehicle's route on first sight (extract.py) on the
        # premise that a route is static unless the vehicle reroutes. SUMO's own default
        # for this flag is already 0, so this changes no run; it turns a precondition that
        # was only prose into one SUMO itself refuses to violate.
        "--device.rerouting.probability",
        "0",
    ]
    if tripinfo_path is not None:
        # ST-D18: M1b's trip metrics -- travel time, time loss, depart delay -- have no
        # other source, and this flag was absent from every run since M0.
        # GOTCHA: write-unfinished is not optional. SUMO emits no row for a vehicle still in
        # the network at the end, and a run under regime C or D ends at the horizon with the
        # most delayed trips unfinished -- censoring the tail the research question is about.
        arguments += [
            "--tripinfo-output",
            str(tripinfo_path),
            "--tripinfo-output.write-unfinished",
            "true",
        ]
    return arguments
