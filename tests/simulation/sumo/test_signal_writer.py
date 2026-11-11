from types import ModuleType
from typing import cast

import pytest

from cadence.control.executor import SetPhase, SetRemainingDuration_s
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.signal_writer import apply_signal_commands
from cadence.types import IntersectionId

A0 = IntersectionId("A0")
TURNING = "scenarios/s0_turning/v1"


class _RecordingTrafficLight:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def setPhase(self, tls_id: str, phase_index: int) -> None:  # noqa: N802
        self.calls.append(("setPhase", tls_id, phase_index))

    def setPhaseDuration(self, tls_id: str, remaining_s: float) -> None:  # noqa: N802
        self.calls.append(("setPhaseDuration", tls_id, remaining_s))


class _RecordingBinding:
    def __init__(self) -> None:
        self.trafficlight = _RecordingTrafficLight()


def _apply(commands) -> list[tuple[str, str, float]]:
    fake = _RecordingBinding()
    apply_signal_commands(cast(ModuleType, fake), commands)
    return fake.trafficlight.calls


def test_commands_become_calls_in_the_order_given():
    assert _apply((SetPhase(A0, 2), SetRemainingDuration_s(A0, 61.0))) == [
        ("setPhase", "A0", 2),
        ("setPhaseDuration", "A0", 61.0),
    ]


def test_the_writer_never_reorders():
    assert _apply((SetRemainingDuration_s(A0, 61.0), SetPhase(A0, 2))) == [
        ("setPhaseDuration", "A0", 61.0),
        ("setPhase", "A0", 2),
    ]


def test_no_commands_make_no_calls():
    assert _apply(()) == []


_BINDINGS = pytest.mark.parametrize(
    "binding", [BindingKind.TRACI, BindingKind.LIBSUMO], ids=["traci", "libsumo"]
)


def _phase_at_each_step(connection, until_s):
    phases = {}
    while True:
        result = connection.step()
        phases[result.time_s] = result.state.intersections[A0].phase_index
        if result.time_s >= until_s:
            return phases


@pytest.mark.sumo
@_BINDINGS
def test_set_phase_takes_effect_on_the_next_step(repo_root, binding):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        connection.step()
        connection.apply_signal_commands((SetPhase(A0, 1),))
        result = connection.step()
    assert result.state.intersections[A0].phase_index == 1


@pytest.mark.sumo
@_BINDINGS
def test_set_remaining_duration_holds_the_stage_past_its_program_switch(repo_root, binding):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        connection.step()
        connection.apply_signal_commands((SetRemainingDuration_s(A0, 61.0),))
        phases = _phase_at_each_step(connection, until_s=50.0)
    assert set(phases.values()) == {0}


@pytest.mark.sumo
@_BINDINGS
def test_an_untouched_run_leaves_stage_zero_by_fifty_seconds(repo_root, binding):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        phases = _phase_at_each_step(connection, until_s=50.0)
    assert phases[50.0] != 0


@pytest.mark.sumo
@_BINDINGS
def test_remaining_duration_counts_from_the_step_it_is_applied(repo_root, binding):
    # Asserted at 29 s and 32 s, not at the boundary: the exact boundary is P2-03's
    # zero-margin question. "From now" expires near 30 s; "from the phase's start" would
    # have expired by 20 s, so phase 0 would already be gone at 29 s.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=binding) as connection:
        _phase_at_each_step(connection, until_s=10.0)
        connection.apply_signal_commands((SetRemainingDuration_s(A0, 20.0),))
        phases = _phase_at_each_step(connection, until_s=32.0)
    assert phases[29.0] == 0
    assert phases[32.0] == 1


@pytest.mark.sumo
def test_applying_commands_to_a_closed_connection_raises(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        pass
    with pytest.raises(RuntimeError, match="closed"):
        connection.apply_signal_commands(())
