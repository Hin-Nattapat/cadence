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
        # M1b's vehicle accounting rests on departed = arrived + still-active, and both of
        # these turn a vehicle into a fourth outcome that the identity has no term for.
        # Both values are SUMO's own defaults today, measured from --save-template, so this
        # changes no run -- it stops a later SUMO from changing what a run means.
        "--collision.action",
        "teleport",
        "--time-to-teleport.remove",
        "false",
        # A third way out, and the same argument: -1 disables it, which is SUMO's default.
        "--max-depart-delay",
        "-1",
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
