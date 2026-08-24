from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.topology_reader import read_topology
from cadence.simulation.topology import TurnDirection
from cadence.types import LaneId

TURNING = "scenarios/s0_turning/v1"


@pytest.fixture
def topology(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        return connection.topology


@pytest.mark.sumo
def test_every_controlled_connection_is_read(topology):
    assert len(topology.connections) == 16


@pytest.mark.sumo
def test_connections_collapse_to_twelve_movements(topology):
    # Four approaches times three turns. Sixteen links, twelve movements: the straight
    # movement of each approach is served from two lanes.
    assert len(topology.movements) == 12


@pytest.mark.sumo
def test_a_shared_lane_serves_two_movements(topology):
    shared = LaneId("top0A0_0")
    serving = {
        connection.movement_id
        for connection in topology.connections.values()
        if connection.from_lane_id == shared
    }
    assert len(serving) == 2, "S0's approach lanes each serve a turn and a through movement"


@pytest.mark.sumo
def test_turn_direction_comes_from_sumo(topology):
    directions = {connection.turn_direction for connection in topology.connections.values()}
    assert directions == {TurnDirection.RIGHT, TurnDirection.STRAIGHT, TurnDirection.LEFT}


@pytest.mark.sumo
def test_lane_geometry_is_recorded(topology):
    lane = topology.lanes[LaneId("top0A0_0")]
    assert lane.edge_id == "top0A0"
    assert lane.lane_index == 0
    assert lane.length_m > 0.0
    assert lane.max_speed_mps > 0.0


@pytest.mark.sumo
def test_no_internal_lane_is_recorded(topology):
    assert not [lane for lane in topology.lanes if lane.startswith(":")]


@pytest.mark.sumo
def test_the_signal_program_is_recorded(topology):
    # Without this, phase_index is an integer with no meaning, min and max green are
    # recoverable from nothing, and a phase that is never served leaves no trace at all -
    # which is the starvation case the spec flags as needing a test (ST-D19).
    assert {phase.phase_index for phase in topology.phases} == {0, 1, 2, 3}
    assert all(phase.duration_s > 0 for phase in topology.phases)
    assert all(len(phase.signals) == 16 for phase in topology.phases)
    assert any(signal.permits_movement for phase in topology.phases for signal in phase.signals)


def test_the_active_program_is_selected_when_several_are_defined():
    # Regression for taking getAllProgramLogics()[0] unconditionally: on a junction with an
    # actuated program and a static fallback, index 0 need not be the one SUMO is running.
    # S0 defines only one program, so this cannot be caught against the real network; a fake
    # binding with two is the only way to see it.
    binding = MagicMock()
    binding.lane.getIDList.return_value = ["top0A0_0"]
    binding.lane.getLength.return_value = 100.0
    binding.lane.getMaxSpeed.return_value = 13.89
    binding.trafficlight.getIDList.return_value = ["A0"]
    binding.trafficlight.getProgram.return_value = "actuated"
    binding.trafficlight.getControlledLinks.return_value = []
    fallback = SimpleNamespace(
        programID="0",
        phases=[SimpleNamespace(duration=42.0, minDur=42.0, maxDur=42.0, state="G")],
    )
    active = SimpleNamespace(
        programID="actuated",
        phases=[SimpleNamespace(duration=10.0, minDur=5.0, maxDur=20.0, state="G")],
    )
    binding.trafficlight.getAllProgramLogics.return_value = [fallback, active]

    topology = read_topology(binding)

    assert {phase.program_id for phase in topology.phases} == {"actuated"}


def test_the_first_logic_is_recorded_when_no_program_matches():
    # getProgram reporting an id no defined logic declares is stranger than either branch;
    # the fallback records the first logic rather than refusing to read the network.
    binding = MagicMock()
    binding.lane.getIDList.return_value = ["top0A0_0"]
    binding.lane.getLength.return_value = 100.0
    binding.lane.getMaxSpeed.return_value = 13.89
    binding.trafficlight.getIDList.return_value = ["A0"]
    binding.trafficlight.getProgram.return_value = "unknown"
    binding.trafficlight.getControlledLinks.return_value = []
    first = SimpleNamespace(
        programID="0",
        phases=[SimpleNamespace(duration=42.0, minDur=42.0, maxDur=42.0, state="G")],
    )
    second = SimpleNamespace(
        programID="1",
        phases=[SimpleNamespace(duration=10.0, minDur=5.0, maxDur=20.0, state="G")],
    )
    binding.trafficlight.getAllProgramLogics.return_value = [first, second]

    topology = read_topology(binding)

    assert {phase.program_id for phase in topology.phases} == {"0"}
