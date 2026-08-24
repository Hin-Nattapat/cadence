"""Canonical traffic state — what a controller is permitted to see.

CONTRACT: every field here is a quantity the simulator reports directly. Anything derived
carries an interpretation, and an interpretation carries a version, so it belongs to the
metric registry at M1b rather than here (ST-D17).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from cadence.types import ConnectionId, IntersectionId, LaneId, MovementId, VehicleId

if TYPE_CHECKING:
    # Imported only for type checking. topology.py imports SignalState from this
    # module, so a runtime import here would be circular; imports run one direction,
    # topology.py to state.py (task-4-brief).
    from cadence.simulation.topology import NetworkTopology


class SignalState(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    RED_YELLOW = "red_yellow"
    GREEN_PROTECTED = "green_protected"
    GREEN_PERMISSIVE = "green_permissive"
    GREEN_STOP_THEN_GO = "green_stop_then_go"
    OFF_YIELDING = "off_yielding"
    OFF_PRIORITY = "off_priority"

    @property
    def permits_movement(self) -> bool:
        # From SUMO's Traffic Lights documentation: G, g and s all let a vehicle
        # proceed; they differ in priority and in whether a stop is required first. This is
        # SUMO's classification, not the project's, so no adapter has to invent it and two
        # adapters cannot disagree about what counts as a go.
        return self in _PERMISSIVE


_PERMISSIVE = frozenset(
    {
        SignalState.GREEN_PROTECTED,
        SignalState.GREEN_PERMISSIVE,
        SignalState.GREEN_STOP_THEN_GO,
    }
)


@dataclass(frozen=True, slots=True)
class LaneState:
    lane_id: LaneId
    vehicle_count_veh: int
    halting_count_veh: int
    mean_speed_mps: float
    occupancy_ratio: float
    waiting_total_now_s: float

    def __post_init__(self) -> None:
        # These are physical impossibilities, not preferences. Catching them here turns a
        # simulator or extraction defect into a loud failure instead of a plausible number
        # that reaches a report.
        if self.halting_count_veh > self.vehicle_count_veh:
            raise ValueError(
                f"lane {self.lane_id}: halting {self.halting_count_veh} exceeds "
                f"vehicle count {self.vehicle_count_veh}"
            )
        if not 0.0 <= self.occupancy_ratio <= 1.0:
            raise ValueError(
                f"lane {self.lane_id}: occupancy {self.occupancy_ratio} outside [0, 1]"
            )


@dataclass(frozen=True, slots=True)
class ConnectionState:
    connection_id: ConnectionId
    signal: SignalState


@dataclass(frozen=True, slots=True)
class IntersectionState:
    intersection_id: IntersectionId
    program_id: str
    phase_index: int
    phase_elapsed_s: float
    connections: tuple[ConnectionState, ...]


@dataclass(frozen=True, slots=True)
class NetworkState:
    active_veh: int
    pending_insertion_veh: int
    departed_total_veh: int
    arrived_total_veh: int
    teleport_total_veh: int


class TeleportKind(StrEnum):
    STARTED = "started"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class Traversal:
    time_s: float
    vehicle_id: VehicleId
    movement_id: MovementId
    # None when the vehicle changed lane inside the junction, or when its exit lane is one
    # of two the approach serves on that edge. The movement always resolves; the connection
    # does not, and a null says so rather than the vehicle disappearing (ST-D16).
    connection_id: ConnectionId | None


@dataclass(frozen=True, slots=True)
class TeleportEvent:
    time_s: float
    vehicle_id: VehicleId
    from_lane_id: LaneId | None
    kind: TeleportKind


@dataclass(frozen=True, slots=True)
class MovementState:
    movement_id: MovementId
    # Positionally aligned with topology.movements[movement_id].connection_ids, so an
    # adapter can ask which connection shows which signal, not merely whether any is green.
    signals: tuple[SignalState, ...]


@dataclass(frozen=True, slots=True)
class CanonicalTrafficState:
    time_s: float
    topology: NetworkTopology
    lanes: Mapping[LaneId, LaneState]
    movements: Mapping[MovementId, MovementState]
    intersections: Mapping[IntersectionId, IntersectionState]
    traversals: tuple[Traversal, ...]
    network: NetworkState
