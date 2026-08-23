from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"


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
