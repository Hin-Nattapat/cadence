"""signal_plan.yaml -- the safety envelope a scenario declares for its signals (SIG-D02).

CONTRACT: the envelope is scenario data, not controller configuration. Every controller
run on a scenario shares it (AP-04), and two runs under different envelopes may not share a
table (ST-D33), which is why its digest is a comparability field of the run manifest. The
file is optional; a scenario without one is not controllable and says so at `cadence run`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadence.simulation.scenario import sha256_file


class StageEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_green_s: float = Field(gt=0.0)
    max_green_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _maximum_is_not_below_minimum(self) -> Self:
        if self.max_green_s < self.min_green_s:
            raise ValueError(
                f"max_green_s ({self.max_green_s}) must not be below min_green_s "
                f"({self.min_green_s})"
            )
        return self


class IntersectionEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Keyed by the stage's PhaseId -- its program index (SIG-D03). Which indices are stages
    # is only known once the program is read, so the stage-set equality check against the
    # built plan lives beside the plan, not here.
    stages: dict[int, StageEnvelope] = Field(min_length=1)


class SignalPlanFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_plan_version: int = Field(ge=1)
    intersections: dict[str, IntersectionEnvelope] = Field(min_length=1)

    def shortest_min_green_s(self) -> float:
        return min(
            stage.min_green_s
            for intersection in self.intersections.values()
            for stage in intersection.stages.values()
        )


def load_signal_plan_file(path: Path, *, step_length_s: float) -> SignalPlanFile:
    plan = SignalPlanFile.model_validate(yaml.safe_load(path.read_text()))
    # A minimum green shorter than one step cannot be enforced: the executor decides once per
    # step, so the shortest hold it can express is step_length_s (spec §4.2).
    shortest_s = plan.shortest_min_green_s()
    if shortest_s < step_length_s:
        raise ValueError(
            f"{path}: min_green_s {shortest_s} is shorter than step_length_s {step_length_s}"
        )
    return plan


def signal_plan_digest(path: Path | None) -> str | None:
    return None if path is None else sha256_file(path)
