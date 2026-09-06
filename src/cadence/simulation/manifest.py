"""Run manifest — everything required to reproduce a run (AP-06).

Timestamps are recorded for provenance but are excluded from any reproducibility
comparison, since they differ between two runs that are otherwise identical.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from cadence import __version__ as cadence_version
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths, config_digest, sha256_file
from cadence.simulation.sumo.binding import BindingKind, sumo_version

# Fields that legitimately differ between two identical runs.
NON_REPRODUCIBLE_FIELDS = frozenset({"started_at_utc", "finished_at_utc"})

# ST-D33: comparability and reproducibility are different questions over different field
# sets. The four sets below plus NON_REPRODUCIBLE_FIELDS partition RunManifest exactly
# (tested), so a field added later must be classified before the suite is green again.
# Must agree, or the two runs may not share a table.
COMPARABILITY_FIELDS = frozenset(
    {
        "scenario_id",
        "scenario_version",
        "network_sha256",
        "demand_sha256",
        "config_sha256",
        "begin_s",
        "end_s",
        "step_length_s",
        "time_to_teleport_s",
        "cadence_commit",
        "cadence_version",
        "python_version",
        "platform_tag",
        "sumo_version",
        "binding",
    }
)
# The controller's identity. Spec §7: a difference here is what makes a comparison a
# controller comparison, while a difference in the seed alone is a replicate of one
# controller -- two seeds of one controller is the first thing anyone runs after M2.
CONTROLLER_IDENTITY_FIELDS = frozenset({"controller_id", "controller_version"})
SEED_FIELD = "seed"
# Reported, never compared for equality: a controller comparison differs here by construction.
INTENDED_DIFFERENCE_FIELDS = CONTROLLER_IDENTITY_FIELDS | {SEED_FIELD}
# Results of the run, not inputs to it.
OUTCOME_FIELDS = frozenset(
    {"terminal_time_s", "step_count", "unmatched_traversal_count", "termination_reason"}
)
# The refusal gate (M1a spec §9.2, ST-D11), not a comparison.
DIRTINESS_FIELDS = frozenset({"cadence_dirty", "cadence_dirty_digest"})


class TerminationReason(StrEnum):
    DRAINED = "drained"
    HORIZON = "horizon"
    # Every other way a run can stop: a simulator error, an external kill, a gridlock the
    # harness declines to sit through. Two values would have meant a run ending any other
    # way produces no manifest at all rather than an honest one, and under oversaturation
    # that is a normal outcome, not an impossible one.
    ABORTED = "aborted"


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
    terminal_time_s: float
    step_count: int
    unmatched_traversal_count: int
    termination_reason: TerminationReason
    cadence_dirty_digest: str | None
    started_at_utc: str
    finished_at_utc: str

    def reproducible_fields(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump().items()
            if key not in NON_REPRODUCIBLE_FIELDS
        }


class ComparisonKind(StrEnum):
    # Spec §7: three kinds, told apart by which intended-difference fields differ, so that
    # verify-run says which one it is looking at rather than letting a reader mistake a
    # seed replicate or a rerun for a comparison between two controllers.
    REPRODUCIBILITY = "reproducibility"
    SEED_REPLICATE = "seed-replicate"
    CONTROLLER_COMPARISON = "controller-comparison"


@dataclass(frozen=True)
class RunComparison:
    left_dirty: bool
    right_dirty: bool
    mismatched_comparability_fields: Mapping[str, tuple[object, object]]
    intended_differences: Mapping[str, tuple[object, object]]

    @property
    def comparable(self) -> bool:
        return not (self.left_dirty or self.right_dirty or self.mismatched_comparability_fields)

    @property
    def kind(self) -> ComparisonKind:
        differing = set(self.intended_differences)
        if differing & CONTROLLER_IDENTITY_FIELDS:
            return ComparisonKind.CONTROLLER_COMPARISON
        if SEED_FIELD in differing:
            return ComparisonKind.SEED_REPLICATE
        return ComparisonKind.REPRODUCIBILITY


def _differing_fields(
    left: RunManifest, right: RunManifest, fields: frozenset[str]
) -> Mapping[str, tuple[object, object]]:
    left_values = left.model_dump()
    right_values = right.model_dump()
    return MappingProxyType(
        {
            field: (left_values[field], right_values[field])
            for field in sorted(fields)
            if left_values[field] != right_values[field]
        }
    )


def _is_dirty(manifest: RunManifest) -> bool:
    # Both dirtiness fields, read as one signal. A manifest carrying the flag without the
    # digest is the case where reading either one alone disagrees with the other, and the
    # refusal has to be the answer both times.
    return manifest.cadence_dirty or manifest.cadence_dirty_digest is not None


def compare_manifests(left: RunManifest, right: RunManifest) -> RunComparison:
    """Whether two runs may share a table (ST-D33), and what kind of comparison they are.

    CONTRACT: never reads OUTCOME_FIELDS or NON_REPRODUCIBLE_FIELDS -- outcomes differ by
    construction between any two runs worth comparing -- and never reuses
    `reproducible_fields()`, which answers the other question.
    """
    return RunComparison(
        left_dirty=_is_dirty(left),
        right_dirty=_is_dirty(right),
        mismatched_comparability_fields=_differing_fields(left, right, COMPARABILITY_FIELDS),
        intended_differences=_differing_fields(left, right, INTENDED_DIFFERENCE_FIELDS),
    )


def git_commit(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def working_tree_digest(repo_root: Path) -> str | None:
    """Identity of the uncommitted state, or None when the tree is clean.

    ST-D11: a boolean cannot distinguish two runs made from two different uncommitted
    trees. `git diff HEAD` covers modified tracked files and `git status --porcelain -uall`
    covers the presence of untracked ones; neither alone is enough.
    """
    parts = [
        subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=True).stdout
        for command in (["git", "diff", "HEAD"], ["git", "status", "--porcelain", "-uall"])
    ]
    combined = "".join(parts)
    if not combined.strip():
        return None
    return hashlib.sha256(combined.encode()).hexdigest()


def build_manifest(
    repo_root: Path,
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    binding: BindingKind,
    controller_id: str,
    controller_version: str,
    terminal_time_s: float,
    step_count: int,
    unmatched_traversal_count: int,
    termination_reason: TerminationReason,
    started_at_utc: str,
    finished_at_utc: str,
) -> RunManifest:
    digest = working_tree_digest(repo_root)
    return RunManifest(
        cadence_commit=git_commit(repo_root),
        cadence_dirty=digest is not None,
        cadence_dirty_digest=digest,
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
        terminal_time_s=terminal_time_s,
        step_count=step_count,
        unmatched_traversal_count=unmatched_traversal_count,
        termination_reason=termination_reason,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
    )
