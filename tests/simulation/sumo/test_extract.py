import pytest

from cadence.simulation.events import EventKind, SimulationEvent
from cadence.simulation.scenario import load_scenario
from cadence.simulation.state import SignalState
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.extract import StateExtractor, TraversalDetector
from cadence.types import IntersectionId, VehicleId

TURNING = "scenarios/s0_turning/v1"

# SumoConnection deliberately has no public `binding` property (de6a238 closed
# that as a traci escape hatch ARCH-D02's import scanner cannot see). These tests drive raw
# steps to isolate the extractor from StepResult, which Task 5 wires it into, so they reach
# into the private attribute the same way test_connection_lifecycle.py already does.


@pytest.mark.sumo
def test_the_extractor_reports_every_lane_and_connection(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        topology = connection.topology
        extractor = StateExtractor(topology)
        for _ in range(60):
            connection._binding.simulationStep()
        state = extractor.extract(connection._binding, time_s=60.0, events=(), traversals=())

    assert set(state.lanes) == set(topology.lanes)
    assert set(state.movements) == set(topology.movements)
    assert state.topology is topology, "ST-D15: the movement layer has to be reachable"
    for movement_id, movement in state.movements.items():
        assert len(movement.signals) == len(topology.movements[movement_id].connection_ids)
    intersection = state.intersections[IntersectionId("A0")]
    assert len(intersection.connections) == len(topology.connections)
    assert all(isinstance(item.signal, SignalState) for item in intersection.connections)


@pytest.mark.sumo
def test_phase_elapsed_never_exceeds_its_phase(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        topology = connection.topology
        extractor = StateExtractor(topology)
        logic = connection._binding.trafficlight.getAllProgramLogics("A0")[0]
        longest_s = max(phase.duration for phase in logic.phases)
        for step in range(1, 200):
            connection._binding.simulationStep()
            state = extractor.extract(
                connection._binding, time_s=float(step), events=(), traversals=()
            )
            assert state.intersections[IntersectionId("A0")].phase_elapsed_s <= longest_s


def test_totals_accumulate_across_steps():
    # No simulator needed: the accumulator is the part that must not be trusted to SUMO,
    # because getDepartedNumber reports the step, not a running total.
    extractor = StateExtractor.__new__(StateExtractor)
    extractor._departed_total_veh = 0
    extractor._arrived_total_veh = 0
    extractor._teleport_total_veh = 0

    first = (SimulationEvent(1.0, EventKind.DEPARTED, VehicleId("a")),)
    second = (
        SimulationEvent(2.0, EventKind.DEPARTED, VehicleId("b")),
        SimulationEvent(2.0, EventKind.ARRIVED, VehicleId("a")),
        SimulationEvent(2.0, EventKind.TELEPORT_STARTED, VehicleId("b")),
    )
    extractor._accumulate(first)
    extractor._accumulate(second)

    assert extractor._departed_total_veh == 2
    assert extractor._arrived_total_veh == 1
    assert extractor._teleport_total_veh == 1


class _FakeVehicleApi:
    def __init__(self, lanes_by_step):
        self._lanes_by_step = lanes_by_step
        self._step = -1

    def advance(self):
        self._step += 1

    def getIDList(self):  # noqa: N802
        return tuple(self._lanes_by_step[self._step])

    def getLaneID(self, vehicle_id):  # noqa: N802
        return self._lanes_by_step[self._step][vehicle_id]


class _FakeBinding:
    def __init__(self, lanes_by_step):
        self.vehicle = _FakeVehicleApi(lanes_by_step)


def test_a_mid_junction_lane_change_produces_one_traversal(turning_topology):
    # The defect via-lane counting has: this vehicle is seen on two internal lanes and
    # would be counted twice. Keyed on the lane pair it is one traversal.
    steps = [
        {"v0": "top0A0_0"},
        {"v0": ":A0_1_0"},
        {"v0": ":A0_1_1"},
        {"v0": "A0bottom0_1"},
    ]
    binding = _FakeBinding(steps)
    detector = TraversalDetector(turning_topology)

    seen = []
    for index in range(len(steps)):
        binding.vehicle.advance()
        seen.extend(detector.observe(binding, time_s=float(index)))

    assert len(seen) == 1
    assert seen[0].vehicle_id == "v0"


def test_a_vehicle_that_never_leaves_its_approach_produces_none(turning_topology):
    steps = [{"v0": "top0A0_0"}, {"v0": "top0A0_0"}, {"v0": "top0A0_0"}]
    binding = _FakeBinding(steps)
    detector = TraversalDetector(turning_topology)

    seen = []
    for index in range(len(steps)):
        binding.vehicle.advance()
        seen.extend(detector.observe(binding, time_s=float(index)))

    assert seen == []


def test_a_teleported_vehicle_produces_no_traversal(turning_topology):
    # Approach lane held, vehicle reappears two edges downstream. Without forget() the
    # detector matches (top0A0_0, A0bottom0) and invents a crossing that never happened.
    detector = TraversalDetector(turning_topology)
    binding = _FakeBinding([{"v0": "top0A0_0"}, {"v0": "A0bottom0_0"}])

    binding.vehicle.advance()
    detector.observe(binding, time_s=0.0)
    detector.forget(["v0"])
    binding.vehicle.advance()
    seen = detector.observe(binding, time_s=1.0)

    assert seen == ()
    assert detector.unmatched_count == 0
