"""Raw simulation events captured per step.

The event stream is the harness's primary output and the basis of the reproducibility
check. It is controller-independent by construction (ARCH-D05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import polars as pl

from cadence.types import VehicleId


class EventKind(StrEnum):
    DEPARTED = "departed"
    ARRIVED = "arrived"
    TELEPORT_STARTED = "teleport_started"
    TELEPORT_ENDED = "teleport_ended"
    COLLISION = "collision"


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    time_s: float
    kind: EventKind
    vehicle_id: VehicleId


@dataclass(frozen=True, slots=True)
class StepResult:
    time_s: float
    events: tuple[SimulationEvent, ...]
    expected_remaining_veh: int


@dataclass
class EventLog:
    _events: list[SimulationEvent] = field(default_factory=list)

    @property
    def events(self) -> tuple[SimulationEvent, ...]:
        return tuple(self._events)

    def append_step(self, result: StepResult) -> None:
        self._events.extend(result.events)

    def count(self, kind: EventKind) -> int:
        return sum(1 for event in self._events if event.kind is kind)

    def to_parquet(self, path: Path) -> None:
        frame = pl.DataFrame(
            {
                "time_s": [event.time_s for event in self._events],
                "kind": [event.kind.value for event in self._events],
                "vehicle_id": [str(event.vehicle_id) for event in self._events],
            },
            schema={"time_s": pl.Float64, "kind": pl.Utf8, "vehicle_id": pl.Utf8},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
