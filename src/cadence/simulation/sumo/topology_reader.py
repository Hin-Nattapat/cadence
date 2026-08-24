"""Builds the canonical network topology from a live simulator binding.

GOTCHA: this reads topology from traci rather than sumolib on purpose.
trafficlight.getControlledLinks returns the link-index-to-lane-triple mapping and
lane.getLinks carries the direction character, so the extraction path needs no second SUMO
surface (ST-D12).
"""

from __future__ import annotations

from types import MappingProxyType, ModuleType

from cadence.simulation.sumo.signals import connection_id, decode_signal
from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    PhaseInfo,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId

# The LINKDIR_* constants in sumolib.net.connection, which that module records
# as taken from sumo/src/utils/xml/SUMOXMLDefinitions.cpp. Read from SUMO rather than
# recomputed from geometry, so the project holds no second opinion on what a left turn is.
_BY_DIRECTION_CHARACTER: dict[str, TurnDirection] = {
    "s": TurnDirection.STRAIGHT,
    "t": TurnDirection.TURN,
    "T": TurnDirection.TURN_LEFTHAND,
    "l": TurnDirection.LEFT,
    "r": TurnDirection.RIGHT,
    "L": TurnDirection.PARTIALLY_LEFT,
    "R": TurnDirection.PARTIALLY_RIGHT,
}

# Index of the outgoing lane and of the direction character in a traci lane.getLinks tuple:
# (toLane, hasPrio, isOpen, hasFoe, viaLane, state, direction, length).
_LINK_TO_LANE = 0
_LINK_DIRECTION = 6


def _turn_direction(character: str) -> TurnDirection:
    try:
        return _BY_DIRECTION_CHARACTER[character]
    except KeyError:
        raise ValueError(f"unknown SUMO link direction: {character!r}") from None


def _edge_and_index(lane_id: str) -> tuple[EdgeId, int]:
    # GOTCHA: SUMO composes a lane id as "<edge>_<index>" and exposes no getter for the
    # index. Splitting on the last underscore is the documented composition, not a guess.
    edge, _, index = lane_id.rpartition("_")
    return EdgeId(edge), int(index)


def read_topology(binding: ModuleType) -> NetworkTopology:
    lanes = {
        LaneId(lane_id): LaneInfo(
            lane_id=LaneId(lane_id),
            edge_id=_edge_and_index(lane_id)[0],
            lane_index=_edge_and_index(lane_id)[1],
            length_m=float(binding.lane.getLength(lane_id)),
            max_speed_mps=float(binding.lane.getMaxSpeed(lane_id)),
        )
        for lane_id in sorted(binding.lane.getIDList())
        if not lane_id.startswith(":")
    }

    connections: dict[ConnectionId, ConnectionInfo] = {}
    phases: list[PhaseInfo] = []
    for tls_id in sorted(binding.trafficlight.getIDList()):
        active_program_id = str(binding.trafficlight.getProgram(tls_id))
        logics = binding.trafficlight.getAllProgramLogics(tls_id)
        # GOTCHA: getAllProgramLogics returns every DEFINED program. On a junction with an
        # actuated program and a static fallback the first is not necessarily the running
        # one, and the table M2's action mask reads would describe a program that never
        # executes.
        logic = next(
            (item for item in logics if str(item.programID) == active_program_id), logics[0]
        )
        for phase_index, phase in enumerate(logic.phases):
            phases.append(
                PhaseInfo(
                    intersection_id=IntersectionId(tls_id),
                    program_id=str(logic.programID),
                    phase_index=phase_index,
                    duration_s=float(phase.duration),
                    min_duration_s=float(phase.minDur),
                    max_duration_s=float(phase.maxDur),
                    # The phase's state is a lamp string, decoded before it leaves this
                    # package. That is what keeps ST-D04 true of the artifacts as well as
                    # the code.
                    signals=tuple(decode_signal(character) for character in phase.state),
                )
            )
        for index, group in enumerate(binding.trafficlight.getControlledLinks(tls_id)):
            for from_lane, to_lane, via_lane in group:
                directions = {
                    link[_LINK_TO_LANE]: link[_LINK_DIRECTION]
                    for link in binding.lane.getLinks(from_lane)
                }
                from_edge, _ = _edge_and_index(from_lane)
                to_edge, _ = _edge_and_index(to_lane)
                identifier = connection_id(LaneId(from_lane), LaneId(to_lane))
                connections[identifier] = ConnectionInfo(
                    connection_id=identifier,
                    intersection_id=IntersectionId(tls_id),
                    link_index=index,
                    from_lane_id=LaneId(from_lane),
                    to_lane_id=LaneId(to_lane),
                    via_lane_id=LaneId(via_lane),
                    from_edge_id=from_edge,
                    to_edge_id=to_edge,
                    turn_direction=_turn_direction(directions[to_lane]),
                    movement_id=movement_id(from_edge, to_edge),
                )

    return NetworkTopology(
        lanes=MappingProxyType(lanes),
        connections=MappingProxyType(connections),
        movements=MappingProxyType(dict(build_movements(connections.values()))),
        phases=tuple(phases),
    )
