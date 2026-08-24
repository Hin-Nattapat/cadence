"""Static network structure, read once when a run opens.

CONTRACT: a movement is the ordered edge pair, and a TLS link index is recorded but is not
an identity. The same junction converted with --tls.group-signals yields a different index
set while the edge pair is unchanged, so a metric keyed on the index cannot be compared
across two conversions of one site (ST-D05, ST-D06).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from cadence.simulation.state import SignalState
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, MovementId


class TurnDirection(StrEnum):
    STRAIGHT = "straight"
    TURN = "turn"
    TURN_LEFTHAND = "turn_lefthand"
    LEFT = "left"
    RIGHT = "right"
    PARTIALLY_LEFT = "partially_left"
    PARTIALLY_RIGHT = "partially_right"


@dataclass(frozen=True, slots=True)
class LaneInfo:
    lane_id: LaneId
    edge_id: EdgeId
    lane_index: int
    length_m: float
    max_speed_mps: float


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    connection_id: ConnectionId
    intersection_id: IntersectionId
    link_index: int
    from_lane_id: LaneId
    to_lane_id: LaneId
    via_lane_id: LaneId
    from_edge_id: EdgeId
    to_edge_id: EdgeId
    turn_direction: TurnDirection
    movement_id: MovementId


@dataclass(frozen=True, slots=True)
class MovementDefinition:
    movement_id: MovementId
    from_edge_id: EdgeId
    to_edge_id: EdgeId
    turn_direction: TurnDirection
    connection_ids: tuple[ConnectionId, ...]


@dataclass(frozen=True, slots=True)
class PhaseInfo:
    intersection_id: IntersectionId
    program_id: str
    phase_index: int
    duration_s: float
    min_duration_s: float
    max_duration_s: float
    signals: tuple[SignalState, ...]


@dataclass(frozen=True, slots=True)
class NetworkTopology:
    lanes: Mapping[LaneId, LaneInfo]
    connections: Mapping[ConnectionId, ConnectionInfo]
    movements: Mapping[MovementId, MovementDefinition]
    phases: tuple[PhaseInfo, ...]


def movement_id(from_edge: EdgeId, to_edge: EdgeId) -> MovementId:
    return MovementId(f"{from_edge}->{to_edge}")


def build_movements(
    connections: Iterable[ConnectionInfo],
) -> Mapping[MovementId, MovementDefinition]:
    grouped: dict[MovementId, list[ConnectionInfo]] = defaultdict(list)
    for connection in connections:
        grouped[connection.movement_id].append(connection)

    movements: dict[MovementId, MovementDefinition] = {}
    for identifier, members in sorted(grouped.items()):
        directions = {member.turn_direction for member in members}
        if len(directions) > 1:
            raise ValueError(
                f"connections of movement {identifier} disagree on turn direction: "
                + ", ".join(sorted(direction.value for direction in directions))
            )
        first = members[0]
        movements[identifier] = MovementDefinition(
            movement_id=identifier,
            from_edge_id=first.from_edge_id,
            to_edge_id=first.to_edge_id,
            turn_direction=first.turn_direction,
            connection_ids=tuple(sorted(member.connection_id for member in members)),
        )
    return movements
