from collections.abc import Iterable

import pytest

from cadence.control.plan import build_signal_plans
from cadence.simulation.scenario import load_scenario, sha256_file
from cadence.simulation.signal_plan_file import SignalPlanFile, load_signal_plan_file
from cadence.simulation.state import SignalState
from cadence.simulation.topology import (
    ConnectionInfo,
    NetworkTopology,
    PhaseInfo,
    ProgramType,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, PhaseId

GREEN = SignalState.GREEN_PROTECTED
PERMISSIVE = SignalState.GREEN_PERMISSIVE
RED = SignalState.RED
YELLOW = SignalState.YELLOW
RED_YELLOW = SignalState.RED_YELLOW
OFF = SignalState.OFF_YIELDING

INTERSECTION = IntersectionId("A0")
# The scenario step length s0 declares; the loader refuses a min_green_s below it.
STEP_LENGTH_S = 1.0


def _phase(
    phase_index: int,
    duration_s: float,
    signals: tuple[SignalState, ...],
    *,
    program_type: ProgramType = ProgramType.STATIC,
) -> PhaseInfo:
    return PhaseInfo(
        intersection_id=INTERSECTION,
        program_id="0",
        program_type=program_type,
        phase_index=phase_index,
        duration_s=duration_s,
        # On a static program SUMO reports minDur == maxDur == duration; the plan reads
        # neither, and spec §4.2 says why the envelope may not come from them.
        min_duration_s=duration_s,
        max_duration_s=duration_s,
        signals=signals,
    )


def _topology(phases: tuple[PhaseInfo, ...], link_count: int) -> NetworkTopology:
    connections: dict[ConnectionId, ConnectionInfo] = {}
    for link_index in range(link_count):
        from_edge = EdgeId(f"in{link_index}")
        to_edge = EdgeId(f"out{link_index}")
        from_lane = LaneId(f"{from_edge}_0")
        to_lane = LaneId(f"{to_edge}_0")
        identifier = ConnectionId(f"{from_lane}|{to_lane}")
        connections[identifier] = ConnectionInfo(
            connection_id=identifier,
            intersection_id=INTERSECTION,
            link_index=link_index,
            from_lane_id=from_lane,
            to_lane_id=to_lane,
            via_lane_id=LaneId(f":{INTERSECTION}_{link_index}_0"),
            from_edge_id=from_edge,
            to_edge_id=to_edge,
            turn_direction=TurnDirection.STRAIGHT,
            movement_id=movement_id(from_edge, to_edge),
        )
    return NetworkTopology(
        lanes={},
        connections=connections,
        movements=build_movements(connections.values()),
        phases=phases,
        vehicle_types={},
    )


def _envelope(stage_indices: Iterable[int], *, intersection: str = "A0") -> SignalPlanFile:
    return SignalPlanFile(
        signal_plan_version=1,
        intersections={
            intersection: {
                "stages": {
                    index: {"min_green_s": 10.0, "max_green_s": 60.0} for index in stage_indices
                }
            }
        },
    )


def _two_stage_program() -> tuple[PhaseInfo, ...]:
    return (
        _phase(0, 42.0, (GREEN, PERMISSIVE, RED, RED)),
        _phase(1, 3.0, (YELLOW, YELLOW, RED, RED)),
        _phase(2, 42.0, (RED, RED, GREEN, PERMISSIVE)),
        _phase(3, 3.0, (RED, RED, YELLOW, YELLOW)),
    )


def test_a_stage_is_a_phase_that_permits_movement_and_shows_no_yellow():
    plans = build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2]))

    plan = plans[INTERSECTION]
    assert tuple(plan.stages) == (PhaseId(0), PhaseId(2))
    assert plan.program_id == "0"


def test_the_successor_chain_runs_to_the_next_stage_and_wraps():
    plan = build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2]))[INTERSECTION]

    assert plan.stages[PhaseId(0)].transition_phase_indices == (1,)
    assert plan.stages[PhaseId(2)].transition_phase_indices == (3,)
    assert plan.next_stage_in_program_order(PhaseId(0)) == PhaseId(2)
    assert plan.next_stage_in_program_order(PhaseId(2)) == PhaseId(0)


def test_a_successor_chain_may_hold_more_than_one_transition_phase():
    program = (
        _phase(0, 42.0, (GREEN, RED)),
        _phase(1, 3.0, (YELLOW, RED)),
        _phase(2, 2.0, (RED, RED)),
        _phase(3, 42.0, (RED, GREEN)),
        _phase(4, 3.0, (RED, YELLOW)),
    )
    plan = build_signal_plans(_topology(program, 2), _envelope([0, 3]))[INTERSECTION]

    assert plan.stages[PhaseId(0)].transition_phase_indices == (1, 2)
    assert plan.stages[PhaseId(3)].transition_phase_indices == (4,)
    assert plan.transition_phase_duration_s == {1: 3.0, 2: 2.0, 4: 3.0}


def test_the_last_stage_of_a_program_chains_through_its_first_phase():
    # A program whose first phase is a transition: the last stage's chain and its successor
    # both have to wrap past the end, which a program that ends on a transition never asks.
    program = (
        _phase(0, 3.0, (RED, YELLOW)),
        _phase(1, 42.0, (GREEN, RED)),
        _phase(2, 3.0, (YELLOW, RED)),
        _phase(3, 42.0, (RED, GREEN)),
    )
    plan = build_signal_plans(_topology(program, 2), _envelope([1, 3]))[INTERSECTION]

    assert plan.stages[PhaseId(3)].transition_phase_indices == (0,)
    assert plan.stages[PhaseId(1)].transition_phase_indices == (2,)
    assert plan.next_stage_in_program_order(PhaseId(3)) == PhaseId(1)


def test_next_stage_in_program_order_refuses_a_phase_that_is_not_a_stage():
    plan = build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2]))[INTERSECTION]

    with pytest.raises(ValueError, match="phase 1 is not a stage"):
        plan.next_stage_in_program_order(PhaseId(1))


def test_permitted_connections_and_movements_come_from_the_stage_signals():
    plan = build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2]))[INTERSECTION]

    first = plan.stages[PhaseId(0)]
    assert first.permitted_connections == frozenset(
        {ConnectionId("in0_0|out0_0"), ConnectionId("in1_0|out1_0")}
    )
    assert first.permitted_movements == frozenset(
        {movement_id(EdgeId("in0"), EdgeId("out0")), movement_id(EdgeId("in1"), EdgeId("out1"))}
    )
    assert first.movement_signature == first.permitted_movements
    assert first.movement_signature.isdisjoint(plan.stages[PhaseId(2)].movement_signature)


def test_two_connections_on_one_link_index_are_both_permitted():
    # SUMO's getControlledLinks returns a group per index, and a grouped junction puts more
    # than one connection in a group; the plan must not collapse them (ST-D05).
    topology = _topology(_two_stage_program(), 4)
    shared = ConnectionId("in0_0|elsewhere_0")
    connections = dict(topology.connections)
    connections[shared] = ConnectionInfo(
        connection_id=shared,
        intersection_id=INTERSECTION,
        link_index=0,
        from_lane_id=LaneId("in0_0"),
        to_lane_id=LaneId("elsewhere_0"),
        via_lane_id=LaneId(":A0_0_1"),
        from_edge_id=EdgeId("in0"),
        to_edge_id=EdgeId("elsewhere"),
        turn_direction=TurnDirection.LEFT,
        movement_id=movement_id(EdgeId("in0"), EdgeId("elsewhere")),
    )
    topology = NetworkTopology(
        lanes={},
        connections=connections,
        movements=build_movements(connections.values()),
        phases=topology.phases,
        vehicle_types={},
    )

    plan = build_signal_plans(topology, _envelope([0, 2]))[INTERSECTION]

    assert shared in plan.stages[PhaseId(0)].permitted_connections
    assert len(plan.stages[PhaseId(0)].permitted_movements) == 3


def test_the_stage_carries_its_envelope_and_the_program_duration_it_replaces():
    plan = build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2]))[INTERSECTION]

    first = plan.stages[PhaseId(0)]
    assert (first.min_green_s, first.max_green_s) == (10.0, 60.0)
    assert first.program_duration_s == 42.0


def test_a_stage_followed_directly_by_a_stage_is_refused():
    program = (
        _phase(0, 42.0, (GREEN, RED)),
        _phase(1, 42.0, (RED, GREEN)),
        _phase(2, 3.0, (RED, YELLOW)),
    )

    with pytest.raises(ValueError, match=r"A0.*stage 0 is followed directly by stage 1"):
        build_signal_plans(_topology(program, 2), _envelope([0, 1]))


def test_a_transition_phase_that_shows_yellow_where_its_stage_was_red_is_refused():
    program = (
        _phase(0, 42.0, (GREEN, RED)),
        _phase(1, 3.0, (YELLOW, YELLOW)),
        _phase(2, 42.0, (RED, GREEN)),
        _phase(3, 3.0, (RED, YELLOW)),
    )

    with pytest.raises(ValueError) as refusal:
        build_signal_plans(_topology(program, 2), _envelope([0, 2]))

    _assert_the_refusal_names_the_offending_signal(refusal.value, transition_signal=YELLOW)


def test_a_transition_phase_that_permits_movement_its_stage_forbade_is_refused():
    program = (
        _phase(0, 42.0, (GREEN, RED)),
        _phase(1, 3.0, (YELLOW, GREEN)),
        _phase(2, 42.0, (RED, GREEN)),
        _phase(3, 3.0, (RED, YELLOW)),
    )

    with pytest.raises(ValueError) as refusal:
        build_signal_plans(_topology(program, 2), _envelope([0, 2]))

    _assert_the_refusal_names_the_offending_signal(refusal.value, transition_signal=GREEN)


def test_a_transition_phase_that_turns_a_signal_on_where_its_stage_was_off_is_refused():
    # "Off" is not "on": a stage that shows o/O at a link permits no movement there, so a
    # transition that shows green at it is the same stage in disguise as one after a red.
    program = (
        _phase(0, 42.0, (GREEN, OFF)),
        _phase(1, 3.0, (YELLOW, GREEN)),
        _phase(2, 42.0, (RED, GREEN)),
        _phase(3, 3.0, (RED, YELLOW)),
    )

    with pytest.raises(ValueError) as refusal:
        build_signal_plans(_topology(program, 2), _envelope([0, 2]))

    _assert_the_refusal_names_the_offending_signal(
        refusal.value, transition_signal=GREEN, stage_signal=OFF
    )


def test_a_transition_phase_that_shows_red_yellow_where_its_stage_was_red_builds():
    # spec §5.2: RED_YELLOW turns nothing on, so a program generated with
    # --tls.red-yellow.time is drivable and must not be refused.
    program = (
        _phase(0, 42.0, (GREEN, RED)),
        _phase(1, 3.0, (YELLOW, RED_YELLOW)),
        _phase(2, 42.0, (RED, GREEN)),
        _phase(3, 3.0, (RED, YELLOW)),
    )

    plan = build_signal_plans(_topology(program, 2), _envelope([0, 2]))[INTERSECTION]

    assert tuple(plan.stages) == (PhaseId(0), PhaseId(2))
    assert plan.stages[PhaseId(0)].transition_phase_indices == (1,)


def _assert_the_refusal_names_the_offending_signal(
    refusal: ValueError,
    *,
    transition_signal: SignalState,
    stage_signal: SignalState = RED,
) -> None:
    message = str(refusal)
    assert str(INTERSECTION) in message
    assert "transition phase 1" in message
    assert "stage 0" in message
    assert "in1_0|out1_0" in message
    assert transition_signal.value in message
    assert stage_signal.value in message


def test_an_envelope_that_names_a_stage_the_program_lacks_is_refused():
    with pytest.raises(ValueError, match=r"A0.*\[4\]") as refusal:
        build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2, 4]))
    # Only the side that is wrong is named; an empty "omits []" would send a reader looking
    # for a second fault that does not exist.
    assert "omits" not in str(refusal.value)


def test_an_envelope_that_omits_a_stage_the_program_has_is_refused():
    with pytest.raises(ValueError, match=r"A0.*\[2\]") as refusal:
        build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0]))
    assert "lacks" not in str(refusal.value)


def test_an_envelope_that_names_an_unknown_intersection_is_refused():
    with pytest.raises(ValueError, match="B1"):
        build_signal_plans(_topology(_two_stage_program(), 4), _envelope([0, 2], intersection="B1"))


def test_a_program_that_is_not_static_is_refused():
    program = tuple(
        _phase(
            phase.phase_index,
            phase.duration_s,
            phase.signals,
            program_type=ProgramType.ACTUATED,
        )
        for phase in _two_stage_program()
    )

    with pytest.raises(ValueError, match=r"A0.*actuated"):
        build_signal_plans(_topology(program, 4), _envelope([0, 2]))


@pytest.mark.sumo
def test_the_s0_plan_matches_the_program_the_network_carries(turning_topology, repo_root):
    # Measured 2026-09-06 on s0_turning/v1 under SUMO 1.27.1 (spec §4.1): program 0 is
    # stage 0 (42 s), yellow 1 (3 s), stage 2 (42 s), yellow 3 (3 s), no all-red.
    envelope = load_signal_plan_file(
        repo_root / "scenarios/s0_turning/v1/signal_plan.yaml", step_length_s=STEP_LENGTH_S
    )

    plans = build_signal_plans(turning_topology, envelope)

    assert set(plans) == {IntersectionId("A0")}
    plan = plans[IntersectionId("A0")]
    assert tuple(plan.stages) == (PhaseId(0), PhaseId(2))
    assert plan.stages[PhaseId(0)].transition_phase_indices == (1,)
    assert plan.stages[PhaseId(2)].transition_phase_indices == (3,)
    assert plan.transition_phase_duration_s == {1: 3.0, 3: 3.0}
    assert plan.next_stage_in_program_order(PhaseId(0)) == PhaseId(2)
    assert plan.next_stage_in_program_order(PhaseId(2)) == PhaseId(0)

    for stage in plan.stages.values():
        assert stage.program_duration_s == 42.0
        assert len(stage.permitted_connections) == 8
        assert len(stage.permitted_movements) == 6
        assert (stage.min_green_s, stage.max_green_s) == (10.0, 60.0)

    assert plan.stages[PhaseId(0)].movement_signature.isdisjoint(
        plan.stages[PhaseId(2)].movement_signature
    )


@pytest.mark.sumo
@pytest.mark.parametrize("scenario_id", ["s0_turning", "s0_turning_oversaturated"])
def test_every_s0_stage_envelope_brackets_the_program_duration(
    turning_topology, repo_root, scenario_id
):
    # spec §7.3: the acceptance test holds only while each stage's [min, max] brackets the
    # duration the static program gives it. Read off the built plan rather than restated as
    # a literal, so retiming the program moves the test with it.
    config, paths = load_scenario(repo_root / "scenarios" / scenario_id / "v1")
    assert paths.signal_plan is not None
    # The two s0 scenarios differ in demand only, so one topology answers for both; the
    # digests are compared rather than assumed.
    turning_network = repo_root / "scenarios/s0_turning/v1/network.net.xml"
    assert sha256_file(paths.network) == sha256_file(turning_network)
    envelope = load_signal_plan_file(paths.signal_plan, step_length_s=config.step_length_s)

    plan = build_signal_plans(turning_topology, envelope)[IntersectionId("A0")]

    for stage in plan.stages.values():
        assert stage.min_green_s <= stage.program_duration_s <= stage.max_green_s


@pytest.mark.sumo
def test_the_s0_program_reads_as_static(turning_topology):
    assert {phase.program_type for phase in turning_topology.phases} == {ProgramType.STATIC}
