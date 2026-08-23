from pathlib import Path

import pytest

from cadence.simulation.events import EventKind, EventLog
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"

pytestmark = pytest.mark.sumo


@pytest.fixture
def s0():
    return load_scenario(S0_ROOT)


def test_connection_starts_and_closes_cleanly(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        assert connection.step().time_s > 0.0


def test_time_advances_by_the_step_length(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        first = connection.step().time_s
        second = connection.step().time_s
    assert second - first == pytest.approx(config.step_length_s)


def test_vehicles_depart_and_arrive(s0):
    config, paths = s0
    log = EventLog()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            log.append_step(connection.step())
    assert log.count(EventKind.DEPARTED) > 0
    assert log.count(EventKind.ARRIVED) > 0


def test_every_arrival_follows_its_own_departure(s0):
    config, paths = s0
    log = EventLog()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            log.append_step(connection.step())

    departed: set[str] = set()
    for event in log.events:
        if event.kind is EventKind.DEPARTED:
            departed.add(event.vehicle_id)
        elif event.kind is EventKind.ARRIVED:
            assert event.vehicle_id in departed, f"{event.vehicle_id} arrived without departing"


def test_connection_closes_even_when_the_body_raises(s0):
    config, paths = s0
    connection = SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI)
    with pytest.raises(RuntimeError), connection:
        connection.step()
        raise RuntimeError("boom")
    assert connection.is_closed


def test_stepping_a_closed_connection_is_an_error(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        connection.step()
    with pytest.raises(RuntimeError, match="closed"):
        connection.step()


def test_the_run_stops_at_the_scenario_horizon(s0):
    config, paths = s0
    # S0 drains at roughly 500 s, so a 60 s horizon forces the cut-off path rather than
    # the drain path. Without the horizon check the loop would never terminate.
    short = config.model_copy(update={"end_s": 60.0})
    last_time_s, steps = 0.0, 0
    with SumoConnection(short, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            last_time_s = connection.step().time_s
            steps += 1
            assert steps < 1000, "is_finished never became true; the horizon is not enforced"
    assert last_time_s <= 60.0


def test_libsumo_produces_the_same_event_stream_as_traci(s0):
    config, paths = s0

    def run(binding):
        log = EventLog()
        with SumoConnection(config, paths, seed=1, binding=binding) as connection:
            while not connection.is_finished():
                log.append_step(connection.step())
        return [(event.time_s, event.kind, event.vehicle_id) for event in log.events]

    assert run(BindingKind.TRACI) == run(BindingKind.LIBSUMO)
