import pytest

from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId


def _connection(from_lane: str, to_lane: str, direction: TurnDirection, index: int):
    return ConnectionInfo(
        connection_id=ConnectionId(f"{from_lane}|{to_lane}"),
        intersection_id=IntersectionId("A0"),
        link_index=index,
        from_lane_id=LaneId(from_lane),
        to_lane_id=LaneId(to_lane),
        via_lane_id=LaneId(f":A0_{index}_0"),
        from_edge_id=EdgeId(from_lane.rsplit("_", 1)[0]),
        to_edge_id=EdgeId(to_lane.rsplit("_", 1)[0]),
        turn_direction=direction,
        movement_id=movement_id(
            EdgeId(from_lane.rsplit("_", 1)[0]), EdgeId(to_lane.rsplit("_", 1)[0])
        ),
    )


def test_movement_id_is_the_ordered_edge_pair():
    assert movement_id(EdgeId("top0A0"), EdgeId("A0bottom0")) == "top0A0->A0bottom0"


def test_a_movement_groups_every_lane_that_serves_it():
    # The straight-through movement is served from two lanes; both belong to one movement.
    connections = [
        _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1),
        _connection("top0A0_1", "A0bottom0_1", TurnDirection.STRAIGHT, 2),
        _connection("top0A0_0", "A0left0_0", TurnDirection.RIGHT, 0),
    ]
    movements = build_movements(connections)

    straight = movements[movement_id(EdgeId("top0A0"), EdgeId("A0bottom0"))]
    assert len(straight.connection_ids) == 2
    assert straight.turn_direction is TurnDirection.STRAIGHT
    assert len(movements) == 2


def test_a_movement_with_inconsistent_directions_is_rejected():
    # Two connections between the same edge pair must agree on what turn they are, or the
    # grouping rule is describing something the network does not.
    connections = [
        _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1),
        _connection("top0A0_1", "A0bottom0_1", TurnDirection.LEFT, 2),
    ]
    with pytest.raises(ValueError, match="disagree"):
        build_movements(connections)


def test_topology_indexes_by_identifier():
    lane = LaneInfo(
        lane_id=LaneId("top0A0_0"),
        edge_id=EdgeId("top0A0"),
        lane_index=0,
        length_m=189.6,
        max_speed_mps=13.89,
    )
    connection = _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1)
    topology = NetworkTopology(
        lanes={lane.lane_id: lane},
        connections={connection.connection_id: connection},
        movements=build_movements([connection]),
        phases=(),
    )
    assert topology.lanes[LaneId("top0A0_0")].length_m == 189.6
    assert topology.connections[connection.connection_id].link_index == 1


def test_network_topology_requires_its_phases():
    # The spec declares phases required. A default would let a caller silently get an
    # empty program table, which is the artifact M2's action mask reads.
    with pytest.raises(TypeError):
        NetworkTopology(lanes={}, connections={}, movements={})
