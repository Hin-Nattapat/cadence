"""Run manifest — everything required to reproduce a run (AP-06).

Timestamps are recorded for provenance but are excluded from any reproducibility
comparison, since they differ between two runs that are otherwise identical.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from cadence import __version__ as cadence_version
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths, config_digest, sha256_file
from cadence.simulation.sumo.binding import BindingKind, sumo_version

# Fields that legitimately differ between two identical runs.
NON_REPRODUCIBLE_FIELDS = frozenset({"started_at_utc", "finished_at_utc"})


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cadence_commit: str
    cadence_dirty: bool
    cadence_version: str
    sumo_version: str
    python_version: str
    platform_tag: str
    binding: str
    controller_id: str
    controller_version: str
    scenario_id: str
    scenario_version: int
    network_sha256: str
    demand_sha256: str
    config_sha256: str
    seed: int
    begin_s: float
    end_s: float
    step_length_s: float
    time_to_teleport_s: float
    started_at_utc: str
    finished_at_utc: str

    def reproducible_fields(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump().items()
            if key not in NON_REPRODUCIBLE_FIELDS
        }


def git_commit(repo_root: Path) -> tuple[str, bool]:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return sha, bool(status)


def build_manifest(
    repo_root: Path,
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    binding: BindingKind,
    controller_id: str,
    controller_version: str,
    started_at_utc: str,
    finished_at_utc: str,
) -> RunManifest:
    sha, dirty = git_commit(repo_root)
    return RunManifest(
        cadence_commit=sha,
        cadence_dirty=dirty,
        cadence_version=cadence_version,
        sumo_version=sumo_version(),
        python_version=platform.python_version(),
        # eclipse-sumo ships platform-specific binary wheels and SUMO's floating-point
        # results are not guaranteed identical across builds, so the OS and architecture
        # are part of what determines a run's output.
        platform_tag=f"{platform.system()}-{platform.machine()}",
        binding=binding.value,
        controller_id=controller_id,
        controller_version=controller_version,
        scenario_id=str(config.scenario_id),
        scenario_version=config.scenario_version,
        network_sha256=sha256_file(paths.network),
        demand_sha256=sha256_file(paths.demand),
        config_sha256=config_digest(config),
        seed=seed,
        begin_s=config.begin_s,
        end_s=config.end_s,
        step_length_s=config.step_length_s,
        time_to_teleport_s=config.time_to_teleport_s,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
    )
