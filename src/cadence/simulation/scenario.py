"""Scenario definition, validation, and content hashing.

A scenario is an immutable, versioned input. Its identity is the pair (id, version) plus
the content hashes of its network and demand files, all of which enter the run manifest
(AP-06).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadence.types import ScenarioId

_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB; large enough that hashing a network file is one read.


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: ScenarioId
    scenario_version: int = Field(ge=1)
    description: str
    network_file: str
    demand_file: str
    begin_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    step_length_s: float = Field(gt=0.0)
    time_to_teleport_s: float
    default_seed: int = Field(ge=0)

    @model_validator(mode="after")
    def _end_follows_begin(self) -> Self:
        if self.end_s <= self.begin_s:
            raise ValueError(f"end_s ({self.end_s}) must be greater than begin_s ({self.begin_s})")
        return self


@dataclass(frozen=True)
class ScenarioPaths:
    root: Path
    network: Path
    demand: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def config_digest(config: ScenarioConfig) -> str:
    canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_scenario(root: Path) -> tuple[ScenarioConfig, ScenarioPaths]:
    config = ScenarioConfig(**yaml.safe_load((root / "scenario.yaml").read_text()))
    paths = ScenarioPaths(
        root=root,
        network=root / config.network_file,
        demand=root / config.demand_file,
    )
    for path in (paths.network, paths.demand):
        if not path.is_file():
            raise FileNotFoundError(f"scenario {config.scenario_id}: missing {path}")
    return config, paths
