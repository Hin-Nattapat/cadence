"""Builds the SUMO argument vector for a scenario run.

Every flag that affects determinism or failure behaviour is set explicitly, so that a SUMO
upgrade cannot change experiment semantics through a changed default (AP-06).
"""

from __future__ import annotations

from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.sumo.binding import sumo_home


def build_sumo_command(
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    use_gui: bool = False,
) -> list[str]:
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")

    binary = sumo_home() / "bin" / ("sumo-gui" if use_gui else "sumo")
    return [
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
    ]
