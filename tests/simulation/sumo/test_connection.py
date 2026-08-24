from pathlib import Path

import pytest

from cadence.simulation.events import EventKind, EventLog
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"
TURNING = "scenarios/s0_turning/v1"

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
            log.append(connection.step().events)
    assert log.count(EventKind.DEPARTED) > 0
    assert log.count(EventKind.ARRIVED) > 0


def test_every_arrival_follows_its_own_departure(s0):
    config, paths = s0
    log = EventLog()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            log.append(connection.step().events)

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
                log.append(connection.step().events)
        return [(event.time_s, event.kind, event.vehicle_id) for event in log.events]

    assert run(BindingKind.TRACI) == run(BindingKind.LIBSUMO)


def test_every_vehicle_produces_exactly_one_traversal(repo_root):
    # Measured: via-lane presence gives 322, the lane pair gives 306, the outgoing edge
    # gives 315. This asserts ST-D16.
    config, paths = load_scenario(repo_root / TURNING)
    total = 0
    departed = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            result = connection.step()
            total += len(result.state.traversals)
            departed += sum(1 for e in result.events if e.kind is EventKind.DEPARTED)
        unmatched = connection.unmatched_traversals()

    assert departed == 315
    assert total == 315
    assert unmatched == 0


def test_per_movement_totals_match_the_demand_they_were_built_from(
    repo_root, expected_movement_traversals
):
    # The stronger test. A swapped MovementId derivation leaves the total at 315 and moves
    # these twelve, which is the entire reason the demand is asymmetric.
    from collections import Counter

    config, paths = load_scenario(repo_root / TURNING)
    counts: Counter[str] = Counter()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            for traversal in connection.step().state.traversals:
                counts[str(traversal.movement_id)] += 1

    assert dict(counts) == expected_movement_traversals


def test_a_mid_junction_lane_change_leaves_the_connection_unresolved(repo_root):
    # Nine of 315 exit on another lane of the correct edge. The movement always resolves;
    # the connection does not, and a null says so rather than the vehicle disappearing.
    config, paths = load_scenario(repo_root / TURNING)
    unresolved = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            for traversal in connection.step().state.traversals:
                assert traversal.movement_id is not None
                unresolved += traversal.connection_id is None

    assert unresolved == 9


def test_a_teleport_carries_the_real_approach_lane_it_left(repo_root):
    # No integration test reaches the held-lane -> forget() -> observe() order in step():
    # s0_turning has zero teleports at its own scenario default, and the detector's unit
    # test cannot reach the teleport record because step() is what builds it. A future
    # reorder would silently blank TeleportEvent.from_lane_id or fabricate a traversal, with
    # nothing failing. Lowering time_to_teleport_s well below the default makes a normal
    # red-light queue teleport, without any gridlock -- 30.0 s produced 35 teleports on this
    # fixture and seed, none of them from an unresolved or internal held lane.
    config, paths = load_scenario(repo_root / TURNING)
    config = config.model_copy(update={"time_to_teleport_s": 30.0})
    teleports = []
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            teleports.extend(connection.step().teleports)

    assert teleports, "no threshold tried produced a teleport on this fixture"
    for teleport in teleports:
        assert teleport.from_lane_id, "a teleport must carry the lane it left"
        assert not teleport.from_lane_id.startswith(":"), "an internal lane is not an approach"
