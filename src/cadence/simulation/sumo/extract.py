"""Turns one simulator step into canonical state, and — separately — into ground truth.

CONTRACT: StateExtractor and TraversalDetector return only observable quantities.
GroundTruthReader is this module's one deliberate exception: it names
`cadence.simulation.ground_truth` and is itself named in that module's import allowlist
(ST-D01), so reaching for it stays a visible, greppable act rather than a field nobody asked
for (ST-D09).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from types import MappingProxyType, ModuleType

from cadence.simulation.events import EventKind, SimulationEvent
from cadence.simulation.ground_truth import LaneTurnCount, SimulationGroundTruth
from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    MovementState,
    NetworkState,
    SignalState,
    Traversal,
)
from cadence.simulation.sumo.signals import decode_signal
from cadence.simulation.topology import ConnectionInfo, NetworkTopology
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, MovementId, VehicleId


class StateExtractor:
    """Holds the topology and the running totals SUMO does not keep."""

    def __init__(self, topology: NetworkTopology) -> None:
        self._topology = topology
        self._departed_total_veh = 0
        self._arrived_total_veh = 0
        self._teleport_total_veh = 0

    def _accumulate(self, events: Iterable[SimulationEvent]) -> None:
        # GOTCHA: simulation.getDepartedNumber() and getLoadedNumber() report the step just
        # taken, not a running total. Measured at t=120 on a run with over a hundred
        # departures behind it, both returned 0.
        for event in events:
            if event.kind is EventKind.DEPARTED:
                self._departed_total_veh += 1
            elif event.kind is EventKind.ARRIVED:
                self._arrived_total_veh += 1
            elif event.kind is EventKind.TELEPORT_STARTED:
                self._teleport_total_veh += 1

    def _lanes(self, binding: ModuleType) -> Mapping[LaneId, LaneState]:
        return MappingProxyType(
            {
                lane_id: LaneState(
                    lane_id=lane_id,
                    vehicle_count_veh=int(binding.lane.getLastStepVehicleNumber(lane_id)),
                    halting_count_veh=int(binding.lane.getLastStepHaltingNumber(lane_id)),
                    mean_speed_mps=float(binding.lane.getLastStepMeanSpeed(lane_id)),
                    occupancy_ratio=float(binding.lane.getLastStepOccupancy(lane_id)),
                    waiting_total_now_s=float(binding.lane.getWaitingTime(lane_id)),
                )
                for lane_id in self._topology.lanes
            }
        )

    def _intersections(self, binding: ModuleType) -> Mapping[IntersectionId, IntersectionState]:
        # Grouped once, ahead of the per-intersection loop, so a junction with many
        # connections costs one getRedYellowGreenState call rather than one per connection.
        by_intersection: dict[IntersectionId, list[ConnectionInfo]] = defaultdict(list)
        for connection in sorted(
            self._topology.connections.values(), key=lambda item: item.connection_id
        ):
            by_intersection[connection.intersection_id].append(connection)

        intersections: dict[IntersectionId, IntersectionState] = {}
        for intersection_id, connections in sorted(by_intersection.items()):
            lamp_state = binding.trafficlight.getRedYellowGreenState(intersection_id)
            intersections[intersection_id] = IntersectionState(
                intersection_id=intersection_id,
                program_id=str(binding.trafficlight.getProgram(intersection_id)),
                phase_index=int(binding.trafficlight.getPhase(intersection_id)),
                phase_elapsed_s=float(binding.trafficlight.getSpentDuration(intersection_id)),
                connections=tuple(
                    ConnectionState(
                        connection_id=connection.connection_id,
                        signal=decode_signal(lamp_state[connection.link_index]),
                    )
                    for connection in connections
                ),
            )
        return MappingProxyType(intersections)

    def _movements(
        self, intersections: Mapping[IntersectionId, IntersectionState]
    ) -> Mapping[MovementId, MovementState]:
        # Positionally aligned with topology.movements[movement_id].connection_ids, so an
        # adapter can ask which connection shows which signal rather than only whether any
        # is green (ST-D15).
        signal_by_connection: dict[ConnectionId, SignalState] = {
            connection.connection_id: connection.signal
            for intersection in intersections.values()
            for connection in intersection.connections
        }
        return MappingProxyType(
            {
                movement_id: MovementState(
                    movement_id=movement_id,
                    signals=tuple(
                        signal_by_connection[connection_id]
                        for connection_id in definition.connection_ids
                    ),
                )
                for movement_id, definition in self._topology.movements.items()
            }
        )

    def extract(
        self,
        binding: ModuleType,
        time_s: float,
        events: Iterable[SimulationEvent],
        traversals: tuple[Traversal, ...],
    ) -> CanonicalTrafficState:
        self._accumulate(events)
        intersections = self._intersections(binding)
        return CanonicalTrafficState(
            time_s=time_s,
            topology=self._topology,
            lanes=self._lanes(binding),
            movements=self._movements(intersections),
            intersections=intersections,
            traversals=traversals,
            network=NetworkState(
                active_veh=int(binding.vehicle.getIDCount()),
                pending_insertion_veh=len(binding.simulation.getPendingVehicles()),
                departed_total_veh=self._departed_total_veh,
                arrived_total_veh=self._arrived_total_veh,
                teleport_total_veh=self._teleport_total_veh,
            ),
        )


class TraversalDetector:
    """Records a completed movement from the lane a vehicle left and the edge it reached.

    GOTCHA: neither via-lane presence nor the lane pair works. Via-lane presence counts a
    mid-junction lane change twice (322 for 315). The lane pair loses that same vehicle
    entirely (306 for 315), because it exits on a lane the pair does not name. The outgoing
    EDGE resolves in both cases, and a lane serves at most one connection to any given
    edge, so it is unique as well as complete.
    """

    def __init__(self, topology: NetworkTopology) -> None:
        self._by_movement_key: dict[tuple[LaneId, EdgeId], MovementId] = {}
        self._by_lane_pair: dict[tuple[LaneId, LaneId], ConnectionId] = {}
        for connection in topology.connections.values():
            key = (connection.from_lane_id, connection.to_edge_id)
            self._by_movement_key[key] = connection.movement_id
            self._by_lane_pair[(connection.from_lane_id, connection.to_lane_id)] = (
                connection.connection_id
            )
        self._incoming = {from_lane for from_lane, _edge in self._by_movement_key}
        self._lane_edge = {lane_id: info.edge_id for lane_id, info in topology.lanes.items()}
        self._last_lane: dict[str, LaneId] = {}
        self.unmatched_count = 0

    def observe(self, binding: ModuleType, time_s: float) -> tuple[Traversal, ...]:
        traversals: list[Traversal] = []
        active: set[str] = set()
        for vehicle_id in binding.vehicle.getIDList():
            active.add(vehicle_id)
            lane_id = LaneId(binding.vehicle.getLaneID(vehicle_id))
            previous = self._last_lane.get(vehicle_id)
            if lane_id == previous:
                continue
            # An internal lane is a waypoint, not a destination. Hold the approach: a
            # vehicle is usually seen on the via lane, so comparing against the immediately
            # preceding lane would almost never fire (spec section 3.5).
            if lane_id.startswith(":"):
                continue
            if previous in self._incoming:
                edge_id = self._lane_edge.get(lane_id)
                if edge_id is not None and edge_id == self._lane_edge.get(previous):
                    pass  # A lane change on the same approach is not a traversal.
                elif edge_id is None:
                    # A lane absent from the static topology cannot resolve to a movement
                    # either; unmatched for the same reason a wrong-edge exit is.
                    self.unmatched_count += 1
                else:
                    movement = self._by_movement_key.get((previous, edge_id))
                    if movement is None:
                        # Counted, never silent: an undercount at M8 with multi-lane exits
                        # would otherwise look like light demand rather than a defect.
                        self.unmatched_count += 1
                    else:
                        traversals.append(
                            Traversal(
                                time_s=time_s,
                                vehicle_id=VehicleId(vehicle_id),
                                movement_id=movement,
                                connection_id=self._by_lane_pair.get((previous, lane_id)),
                            )
                        )
            self._last_lane[vehicle_id] = lane_id
        for gone in self._last_lane.keys() - active:
            del self._last_lane[gone]
        return tuple(traversals)

    def held_lane(self, vehicle_id: str) -> LaneId | None:
        return self._last_lane.get(vehicle_id)

    def forget(self, vehicle_ids: Iterable[str]) -> None:
        # GOTCHA: SUMO removes a stuck vehicle and reinserts it downstream. Without this the
        # detector compares the approach lane it is still holding against a lane the vehicle
        # never drove to, and either fabricates a traversal -- if that edge happens to be a
        # legal successor -- or trips the unmatched counter. s0_turning has zero teleports,
        # so M1a passes either way; regimes C and D are where it matters, and they are what
        # the project exists to study.
        for vehicle_id in vehicle_ids:
            self._last_lane.pop(vehicle_id, None)


# A vehicle is halting when its speed is below this. Matches SUMO's own
# definition behind getLastStepHaltingNumber, documented as 0.1 m/s.
HALTING_SPEED_MPS = 0.1

# Index into the three-element running tally: [count, halting count, waiting time total].
_TALLY_COUNT = 0
_TALLY_HALTING = 1
_TALLY_WAITING_S = 2


class GroundTruthReader:
    """Cross-tabs lane against the edge each vehicle on it intends to enter next.

    GOTCHA: this halting count and LaneState.halting_count_veh can disagree for four reasons,
    and matching HALTING_SPEED_MPS to SUMO's own threshold removes only the first: (1) SUMO's
    threshold is internal and can drift across versions, ours is in the source; (2) SUMO
    aggregates over the step, this loop reads end-of-step speed; (3) SUMO's lane membership is
    last-step occupancy, this loop's is end-of-step getLaneID(); (4) a vehicle on its final
    edge has no next edge and appears in no row here, while SUMO still counts it as halting --
    no threshold choice fixes that one, which is why the residual row below exists (ST-D19,
    spec section 6.1).
    """

    def __init__(self, topology: NetworkTopology) -> None:
        self._lanes = set(topology.lanes)
        self._routes: dict[str, tuple[str, ...]] = {}

    def read(self, binding: ModuleType, time_s: float) -> SimulationGroundTruth:
        counts: dict[tuple[LaneId, EdgeId], list[float]] = {}
        # One row per lane in the topology, not per lane with traffic: a lane with zero
        # unattributed vehicles still needs a written zero, or the conservation identity in
        # spec section 6.1 has nothing to sum for it.
        residual: dict[LaneId, list[float]] = {lane_id: [0.0, 0.0, 0.0] for lane_id in self._lanes}
        active = set()
        for vehicle_id in binding.vehicle.getIDList():
            active.add(vehicle_id)
            lane_id = LaneId(binding.vehicle.getLaneID(vehicle_id))
            if lane_id not in self._lanes:
                continue
            route = self._routes.get(vehicle_id)
            if route is None:
                # Cached once: a route is static unless the vehicle reroutes, and querying
                # it every step costs roughly twice as much per vehicle.
                route = tuple(binding.vehicle.getRoute(vehicle_id))
                self._routes[vehicle_id] = route
            index = int(binding.vehicle.getRouteIndex(vehicle_id))
            speed = float(binding.vehicle.getSpeed(vehicle_id))
            halting = 1.0 if speed < HALTING_SPEED_MPS else 0.0
            waiting_s = float(binding.vehicle.getWaitingTime(vehicle_id))
            if 0 <= index + 1 < len(route):
                key = (lane_id, EdgeId(route[index + 1]))
                tally = counts.setdefault(key, [0.0, 0.0, 0.0])
            else:
                # The vehicle is on its final route edge: no next edge to attribute it to.
                # It still occupies the lane, so it goes to that lane's residual row rather
                # than being dropped (spec section 6.1, divergence reason 4 above).
                tally = residual[lane_id]
            tally[_TALLY_COUNT] += 1
            tally[_TALLY_HALTING] += halting
            tally[_TALLY_WAITING_S] += waiting_s
        for gone in self._routes.keys() - active:
            del self._routes[gone]

        turn_rows = (
            LaneTurnCount(
                lane_id=lane_id,
                next_edge_id=next_edge_id,
                count_veh=int(tally[_TALLY_COUNT]),
                halting_count_veh=int(tally[_TALLY_HALTING]),
                waiting_total_now_s=tally[_TALLY_WAITING_S],
            )
            for (lane_id, next_edge_id), tally in sorted(counts.items())
        )
        residual_rows = (
            LaneTurnCount(
                lane_id=lane_id,
                next_edge_id=None,
                count_veh=int(tally[_TALLY_COUNT]),
                halting_count_veh=int(tally[_TALLY_HALTING]),
                waiting_total_now_s=tally[_TALLY_WAITING_S],
            )
            for lane_id, tally in sorted(residual.items())
        )
        return SimulationGroundTruth(
            time_s=time_s,
            lane_turns=tuple(turn_rows) + tuple(residual_rows),
        )
