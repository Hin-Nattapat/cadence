import pytest

from cadence.cli import start_executors, tick_executors
from cadence.control.executor import SetPhase
from cadence.control.plan import build_signal_plans
from cadence.simulation.scenario import load_scenario
from cadence.simulation.signal_plan_file import load_signal_plan_file
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.types import IntersectionId, PhaseId

pytestmark = pytest.mark.sumo

TURNING = "scenarios/s0_turning/v1"
# These measured 2 hard-braking vehicles on s0_turning seed 1 under the raw path, on both
# bindings.
SWITCH_TIMES_S = (20.0, 40.0, 60.0, 80.0, 100.0, 130.0, 160.0, 200.0, 240.0, 300.0)
A0 = IntersectionId("A0")

_BINDINGS = pytest.mark.parametrize(
    "binding", [BindingKind.TRACI, BindingKind.LIBSUMO], ids=["traci", "libsumo"]
)


def _target(result) -> PhaseId:
    return PhaseId(2) if result.state.intersections[A0].phase_index == 0 else PhaseId(0)


@_BINDINGS
def test_the_executor_never_brakes_a_vehicle_harder_than_its_decel(repo_root, binding):
    config, paths = load_scenario(repo_root / TURNING)
    assert paths.signal_plan is not None
    envelope = load_signal_plan_file(paths.signal_plan, step_length_s=config.step_length_s)
    braking = []
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        plans = build_signal_plans(connection.topology, envelope)
        result = connection.step()
        executors = start_executors(plans, result.state, step_length_s=config.step_length_s)
        while not connection.is_finished():
            requests = {A0: _target(result)} if result.time_s in SWITCH_TIMES_S else {}
            tick_executors(connection, executors, state=result.state, requests=requests)
            result = connection.step()
            braking.extend(connection.hard_braking_vehicles())
    assert braking == []


@_BINDINGS
def test_a_raw_switch_that_skips_the_yellow_does_brake_vehicles_hard(repo_root, binding):
    config, paths = load_scenario(repo_root / TURNING)
    braking = []
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        result = connection.step()
        while not connection.is_finished():
            if result.time_s in SWITCH_TIMES_S:
                connection.apply_signal_commands((SetPhase(A0, _target(result)),))
            result = connection.step()
            braking.extend(connection.hard_braking_vehicles())
    assert braking != []


def test_hard_braking_on_a_closed_connection_raises(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        pass
    with pytest.raises(RuntimeError, match="closed"):
        connection.hard_braking_vehicles()
