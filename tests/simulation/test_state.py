import dataclasses
from types import MappingProxyType

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    MovementState,
    NetworkState,
    SignalState,
)
from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    MovementDefinition,
    NetworkTopology,
    TurnDirection,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, MovementId


def _lane(**overrides):
    fields = {
        "lane_id": LaneId("top0A0_0"),
        "vehicle_count_veh": 3,
        "halting_count_veh": 2,
        "mean_speed_mps": 4.2,
        "occupancy_ratio": 0.15,
        "waiting_total_now_s": 8.0,
    }
    fields.update(overrides)
    return LaneState(**fields)


def _empty_topology() -> NetworkTopology:
    return NetworkTopology(
        lanes=MappingProxyType({}),
        connections=MappingProxyType({}),
        movements=MappingProxyType({}),
        phases=(),
    )


def _topology_with_one_movement() -> NetworkTopology:
    lane_id = LaneId("top0A0_0")
    connection_id = ConnectionId("top0A0_0|A0bottom0_0")
    movement = MovementId("top0A0->A0bottom0")
    connection = ConnectionInfo(
        connection_id=connection_id,
        intersection_id=IntersectionId("A0"),
        link_index=0,
        from_lane_id=lane_id,
        to_lane_id=LaneId("A0bottom0_0"),
        via_lane_id=LaneId(":A0_0_0"),
        from_edge_id=EdgeId("top0A0"),
        to_edge_id=EdgeId("A0bottom0"),
        turn_direction=TurnDirection.STRAIGHT,
        movement_id=movement,
    )
    return NetworkTopology(
        lanes=MappingProxyType(
            {
                lane_id: LaneInfo(
                    lane_id=lane_id,
                    edge_id=EdgeId("top0A0"),
                    lane_index=0,
                    length_m=100.0,
                    max_speed_mps=13.9,
                )
            }
        ),
        connections=MappingProxyType({connection_id: connection}),
        movements=MappingProxyType(
            {
                movement: MovementDefinition(
                    movement_id=movement,
                    from_edge_id=EdgeId("top0A0"),
                    to_edge_id=EdgeId("A0bottom0"),
                    turn_direction=TurnDirection.STRAIGHT,
                    connection_ids=(connection_id,),
                )
            }
        ),
        phases=(),
    )


def _state_with_topology() -> CanonicalTrafficState:
    topology = _topology_with_one_movement()
    lane_id = next(iter(topology.lanes))
    movement_id = next(iter(topology.movements))
    return CanonicalTrafficState(
        time_s=0.0,
        topology=topology,
        lanes={lane_id: _lane(lane_id=lane_id)},
        movements={
            movement_id: MovementState(
                movement_id=movement_id, signals=(SignalState.GREEN_PROTECTED,)
            )
        },
        intersections={},
        traversals=(),
        network=NetworkState(
            active_veh=0,
            pending_insertion_veh=0,
            departed_total_veh=0,
            arrived_total_veh=0,
            teleport_total_veh=0,
        ),
    )


def test_lane_state_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _lane().vehicle_count_veh = 99


def test_canonical_state_carries_no_derived_quantity():
    # ST-D17: anything derived and interpretive belongs to M1b. If one of these ever
    # appears here, the M1a/M1b line has moved and the spec has to move with it.
    forbidden = {"queue_length_m", "storage_capacity_veh", "available_storage_ratio"}
    present = {field.name for field in dataclasses.fields(LaneState)}
    assert not present & forbidden


@given(
    vehicles=st.integers(min_value=0, max_value=200),
    halting=st.integers(min_value=0, max_value=200),
)
def test_halting_never_exceeds_vehicle_count(vehicles, halting):
    # A physical invariant, asserted on the constructor's own guard rather than on SUMO.
    if halting > vehicles:
        with pytest.raises(ValueError, match="halting"):
            _lane(vehicle_count_veh=vehicles, halting_count_veh=halting)
    else:
        assert _lane(vehicle_count_veh=vehicles, halting_count_veh=halting)


@given(occupancy=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False))
def test_occupancy_stays_within_zero_and_one(occupancy):
    if 0.0 <= occupancy <= 1.0:
        assert _lane(occupancy_ratio=occupancy)
    else:
        with pytest.raises(ValueError, match="occupancy"):
            _lane(occupancy_ratio=occupancy)


def test_state_indexes_by_identifier():
    lane = _lane()
    intersection = IntersectionState(
        intersection_id=IntersectionId("A0"),
        program_id="0",
        phase_index=0,
        phase_elapsed_s=12.0,
        connections=(
            ConnectionState(
                connection_id=ConnectionId("top0A0_0|A0bottom0_0"),
                signal=SignalState.GREEN_PROTECTED,
            ),
        ),
    )
    state = CanonicalTrafficState(
        time_s=42.0,
        topology=_empty_topology(),
        lanes={lane.lane_id: lane},
        movements={},
        intersections={intersection.intersection_id: intersection},
        traversals=(),
        network=NetworkState(
            active_veh=5,
            pending_insertion_veh=0,
            departed_total_veh=10,
            arrived_total_veh=5,
            teleport_total_veh=0,
        ),
    )
    assert state.lanes[LaneId("top0A0_0")].halting_count_veh == 2
    assert (
        state.intersections[IntersectionId("A0")].connections[0].signal
        is SignalState.GREEN_PROTECTED
    )


def test_canonical_state_can_reach_a_movements_incident_lanes():
    # The check that ST-D15 is real rather than decorative. If this needs anything outside
    # CanonicalTrafficState, an M8 adapter needs it too, and it will take it from wherever
    # it can get it.
    state = _state_with_topology()
    movement = next(iter(state.movements.values()))
    definition = state.topology.movements[movement.movement_id]
    lanes = {
        state.topology.connections[connection_id].from_lane_id
        for connection_id in definition.connection_ids
    }
    assert lanes and all(lane_id in state.lanes for lane_id in lanes)


def test_a_movement_reports_a_signal_for_every_contributing_connection():
    movement = MovementState(
        movement_id=MovementId("top0A0->A0bottom0"),
        signals=(SignalState.GREEN_PROTECTED, SignalState.RED),
    )
    assert len(movement.signals) == 2
    assert any(signal.permits_movement for signal in movement.signals)


def test_movement_state_carries_no_queue():
    # ST-D15/ST-D17: a movement queue needs a shared-lane attribution rule, which is an
    # interpretation, which is M1b's. A queue field here means the line has moved.
    names = {field.name for field in dataclasses.fields(MovementState)}
    assert not names & {"queue_count_veh", "queue_length_m", "turn_ratio"}
