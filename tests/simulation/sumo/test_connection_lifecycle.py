from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cadence.simulation.manifest import TerminationReason
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"
TURNING_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_turning" / "v1"


def _connection_with(binding):
    config, paths = load_scenario(S0_ROOT)
    connection = SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI)
    connection._binding = binding
    return connection


def test_a_failing_close_still_marks_the_connection_closed():
    # SUMO dying mid-run makes traci's close() raise. If is_closed stayed False the
    # object would keep accepting steps against a dead process.
    binding = MagicMock()
    binding.close.side_effect = RuntimeError("socket already dead")
    connection = _connection_with(binding)

    with pytest.raises(RuntimeError, match="socket already dead"):
        connection.close()

    assert connection.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        connection.step()


def test_close_is_idempotent():
    binding = MagicMock()
    connection = _connection_with(binding)
    connection.close()
    connection.close()
    assert binding.close.call_count == 1


@pytest.mark.sumo
def test_a_failure_reading_topology_does_not_leak_the_process(monkeypatch, repo_root):
    from cadence.simulation.sumo import connection as connection_module

    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    opened: list[SumoConnection] = []
    original = connection_module.read_topology

    def explode(binding):
        raise ValueError("unknown SUMO link direction: 'q'")

    monkeypatch.setattr(connection_module, "read_topology", explode)
    candidate = SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO)
    opened.append(candidate)
    with pytest.raises(ValueError, match="unknown SUMO link direction"):
        candidate.__enter__()

    assert candidate.is_closed, "the process was started and never shut down"

    # The real proof: a second connection in this same process must still work, which
    # it cannot if the first left libsumo holding a simulation.
    monkeypatch.setattr(connection_module, "read_topology", original)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as second:
        assert second.topology.connections


@pytest.mark.sumo
def test_the_turning_fixture_drains_rather_than_hitting_the_horizon():
    config, paths = load_scenario(TURNING_ROOT)
    steps = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            connection.step()
            steps += 1
        reason = connection.termination_reason()
        terminal_time_s = connection.time_s()

    assert reason is TerminationReason.DRAINED
    assert terminal_time_s == 558.0
    assert steps == 558
