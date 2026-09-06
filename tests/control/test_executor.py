from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise
from types import MappingProxyType
from typing import NamedTuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cadence.control.events import (
    DeferralReason,
    RejectionReason,
    SignalEvent,
    SignalEventKind,
)
from cadence.control.executor import (
    SetPhase,
    SetRemainingDuration_s,
    SignalCommand,
    SignalExecutor,
    SignalPhaseState,
)
from cadence.control.plan import SignalPlan, Stage
from cadence.simulation.state import IntersectionState
from cadence.types import IntersectionId, PhaseId

INTERSECTION = IntersectionId("A0")
PROGRAM_ID = "0"
# scenarios/s0_turning/v1 declares step-length 1.0 s (spec §3).
STEP_LENGTH_S = 1.0
# Measured 2026-09-06 on s0_turning/v1 under SUMO 1.27.1 (spec §4.1): program 0 is
# stage 0 (42 s), yellow 1 (3 s), stage 2 (42 s), yellow 3 (3 s), no all-red.
S0_TRANSITION_DURATION_S = 3.0
S0_PROGRAM_DURATION_S = 42.0
# scenarios/s0_turning/v1/signal_plan.yaml, the placeholder envelope of spec §4.2.
MIN_GREEN_S = 10.0
MAX_GREEN_S = 60.0
# Simulated time accumulates by repeated addition of the step length, so a tick's time can
# miss the multiple it names by a float error; 1e-6 s is far below the shortest step tested.
_TIME_TOLERANCE_S = 1e-6
# 1.0 s is what s0_turning/v1 declares; 0.5 s and 0.1 s are shorter steps a scenario may
# declare, and 0.1 s is the shortest at which repeated addition stops landing on the grid.
_STEP_LENGTHS_S = (1.0, 0.5, 0.1)
_over_step_lengths = pytest.mark.parametrize("step_length_s", _STEP_LENGTHS_S)


def _approx_s(time_s: float) -> object:
    return pytest.approx(time_s, abs=_TIME_TOLERANCE_S)


def _stage(
    phase_id: int,
    chain: tuple[int, ...],
    *,
    min_green_s: float = MIN_GREEN_S,
    max_green_s: float = MAX_GREEN_S,
    program_duration_s: float = S0_PROGRAM_DURATION_S,
) -> Stage:
    return Stage(
        phase_id=PhaseId(phase_id),
        permitted_connections=frozenset(),
        permitted_movements=frozenset(),
        min_green_s=min_green_s,
        max_green_s=max_green_s,
        program_duration_s=program_duration_s,
        transition_phase_indices=chain,
    )


def _plan(stages: Sequence[Stage], transition_duration_s: Mapping[int, float]) -> SignalPlan:
    return SignalPlan(
        intersection_id=INTERSECTION,
        program_id=PROGRAM_ID,
        stages=MappingProxyType({stage.phase_id: stage for stage in stages}),
        transition_phase_duration_s=MappingProxyType(dict(transition_duration_s)),
    )


def _s0_plan() -> SignalPlan:
    return _plan(
        [_stage(0, (1,)), _stage(2, (3,))],
        {1: S0_TRANSITION_DURATION_S, 3: S0_TRANSITION_DURATION_S},
    )


def _three_stage_plan() -> SignalPlan:
    return _plan(
        [_stage(0, (1,)), _stage(2, (3,)), _stage(4, (5,))],
        {1: S0_TRANSITION_DURATION_S, 3: S0_TRANSITION_DURATION_S, 5: S0_TRANSITION_DURATION_S},
    )


class _FakeSumo:
    """What SUMO would report one step after a command was applied (SIM-D02).

    CONTRACT: commands are applied at time t and the phase they select is what the next
    extracted state reports, with `phase_elapsed_s` counting one step from the switch.
    A phase that runs out its own duration switches by itself, which under SIG-D01 must
    never happen while the executor holds the stage -- so it raises instead.
    """

    def __init__(
        self,
        program_duration_s: Mapping[int, float],
        *,
        phase_index: int,
        phase_elapsed_s: float,
        now_s: float,
        step_length_s: float = STEP_LENGTH_S,
    ) -> None:
        self._program_duration_s = dict(program_duration_s)
        self.phase_index = phase_index
        self.phase_elapsed_s = phase_elapsed_s
        self.now_s = now_s
        self.step_length_s = step_length_s
        self.remaining_at_s = self._program_duration_s[phase_index]

    def state(self) -> IntersectionState:
        return IntersectionState(
            intersection_id=INTERSECTION,
            program_id=PROGRAM_ID,
            phase_index=self.phase_index,
            phase_elapsed_s=self.phase_elapsed_s,
            connections=(),
        )

    def apply_and_step(self, commands: Iterable[SignalCommand]) -> None:
        for command in commands:
            if isinstance(command, SetPhase):
                self.phase_index = command.phase_index
                self.phase_elapsed_s = 0.0
                self.remaining_at_s = self._program_duration_s[command.phase_index]
            else:
                self.remaining_at_s = self.phase_elapsed_s + command.remaining_s
        if self.phase_elapsed_s >= self.remaining_at_s:
            raise AssertionError(
                f"SUMO would have left phase {self.phase_index} by itself at t = {self.now_s}"
            )
        self.phase_elapsed_s += self.step_length_s
        self.now_s += self.step_length_s


def _program_duration_s(plan: SignalPlan) -> Mapping[int, float]:
    durations = {stage.phase_id: stage.program_duration_s for stage in plan.stages.values()}
    return {**durations, **plan.transition_phase_duration_s}


class _Tick(NamedTuple):
    at_s: float
    before: SignalPhaseState
    commands: tuple[SignalCommand, ...]
    events: tuple[SignalEvent, ...]
    after: SignalPhaseState


def _run(
    plan: SignalPlan,
    requests: Sequence[PhaseId | None],
    *,
    phase_index: int = 0,
    phase_elapsed_s: float = 0.0,
    now_s: float = 0.0,
    step_length_s: float = STEP_LENGTH_S,
) -> tuple[SignalExecutor, list[_Tick]]:
    sumo = _FakeSumo(
        _program_duration_s(plan),
        phase_index=phase_index,
        phase_elapsed_s=phase_elapsed_s,
        now_s=now_s,
        step_length_s=step_length_s,
    )
    executor = SignalExecutor(plan, sumo.state(), sumo.now_s, step_length_s)
    ticks: list[_Tick] = []
    for request in requests:
        at_s = sumo.now_s
        before = executor.phase_state(at_s)
        commands, events = executor.tick(sumo.state(), at_s, request)
        ticks.append(_Tick(at_s, before, commands, events, executor.phase_state(at_s)))
        sumo.apply_and_step(commands)
    return executor, ticks


def _requests_at(
    schedule: Mapping[float, PhaseId],
    *,
    until_s: float,
    step_length_s: float,
    now_s: float,
) -> list[PhaseId | None]:
    tick_count = round((until_s - now_s) / step_length_s) + 1
    requests: list[PhaseId | None] = [None] * tick_count
    for at_s, request in schedule.items():
        requests[round((at_s - now_s) / step_length_s)] = request
    return requests


def _drive(
    plan: SignalPlan,
    schedule: Mapping[float, PhaseId] | None = None,
    *,
    until_s: float,
    step_length_s: float = STEP_LENGTH_S,
    phase_index: int = 0,
    phase_elapsed_s: float = 0.0,
    now_s: float = 0.0,
) -> tuple[SignalExecutor, list[_Tick]]:
    requests = _requests_at(
        schedule or {}, until_s=until_s, step_length_s=step_length_s, now_s=now_s
    )
    return _run(
        plan,
        requests,
        phase_index=phase_index,
        phase_elapsed_s=phase_elapsed_s,
        now_s=now_s,
        step_length_s=step_length_s,
    )


def _of_kind(ticks: Sequence[_Tick], kind: SignalEventKind) -> list[tuple[float, SignalEvent]]:
    return [(tick.at_s, event) for tick in ticks for event in tick.events if event.kind is kind]


def _set_phases(ticks: Sequence[_Tick]) -> list[tuple[float, int]]:
    return [
        (tick.at_s, command.phase_index)
        for tick in ticks
        for command in tick.commands
        if isinstance(command, SetPhase)
    ]


def _state(phase_index: int, phase_elapsed_s: float) -> IntersectionState:
    return IntersectionState(
        intersection_id=INTERSECTION,
        program_id=PROGRAM_ID,
        phase_index=phase_index,
        phase_elapsed_s=phase_elapsed_s,
        connections=(),
    )


def _at(ticks: Sequence[_Tick], at_s: float) -> _Tick:
    matches = [tick for tick in ticks if abs(tick.at_s - at_s) < _TIME_TOLERANCE_S]
    assert len(matches) == 1, f"expected exactly one tick at t = {at_s}, got {len(matches)}"
    return matches[0]


# --- (a) the review's double-serve -------------------------------------------------------


@_over_step_lengths
def test_a_repeat_of_the_request_a_transition_is_already_serving_is_rejected_as_already_current(
    step_length_s,
):
    plan = _s0_plan()

    _, ticks = _drive(
        plan, {10.0: PhaseId(2), 11.0: PhaseId(2)}, until_s=29.0, step_length_s=step_length_s
    )

    assert _set_phases(ticks) == [(_approx_s(10.0), 1), (_approx_s(13.0), 2)]
    rejected = _of_kind(ticks, SignalEventKind.ACTION_REJECTED)
    assert [(at_s, event.reason) for at_s, event in rejected] == [
        (_approx_s(11.0), RejectionReason.ALREADY_CURRENT)
    ]
    assert [at_s for at_s, _ in _of_kind(ticks, SignalEventKind.TRANSITION_STARTED)] == [
        _approx_s(10.0)
    ]
    assert [at_s for at_s, _ in _of_kind(ticks, SignalEventKind.STAGE_ENTERED)] == [_approx_s(13.0)]
    assert _at(ticks, 13.0).after.pending is None


# --- (b) minimum green defers, then serves ------------------------------------------------


@_over_step_lengths
def test_a_request_inside_minimum_green_is_deferred_and_served_when_it_expires(step_length_s):
    plan = _s0_plan()

    _, ticks = _drive(plan, {3.0: PhaseId(2)}, until_s=13.0, step_length_s=step_length_s)

    deferred = _of_kind(ticks, SignalEventKind.REQUEST_DEFERRED)
    assert [(at_s, event.reason, event.to_phase_id) for at_s, event in deferred] == [
        (_approx_s(3.0), DeferralReason.MIN_GREEN, PhaseId(2))
    ]
    started = _of_kind(ticks, SignalEventKind.TRANSITION_STARTED)
    assert [(at_s, event.from_phase_id, event.to_phase_id) for at_s, event in started] == [
        (_approx_s(10.0), PhaseId(0), PhaseId(2))
    ]
    assert _set_phases(ticks) == [(_approx_s(10.0), 1), (_approx_s(13.0), 2)]


# --- (c) the second request supersedes the first ------------------------------------------


@_over_step_lengths
def test_a_second_request_inside_minimum_green_supersedes_the_first_and_is_served_alone(
    step_length_s,
):
    plan = _three_stage_plan()

    _, ticks = _drive(
        plan, {3.0: PhaseId(2), 4.0: PhaseId(4)}, until_s=16.0, step_length_s=step_length_s
    )

    superseded = _of_kind(ticks, SignalEventKind.REQUEST_SUPERSEDED)
    assert [(at_s, event.from_phase_id, event.to_phase_id) for at_s, event in superseded] == [
        (_approx_s(4.0), PhaseId(2), PhaseId(4))
    ]
    started = _of_kind(ticks, SignalEventKind.TRANSITION_STARTED)
    assert [(at_s, event.to_phase_id) for at_s, event in started] == [(_approx_s(10.0), PhaseId(4))]
    entered = _of_kind(ticks, SignalEventKind.STAGE_ENTERED)
    assert [(at_s, event.to_phase_id) for at_s, event in entered] == [(_approx_s(13.0), PhaseId(4))]


# --- (d) maximum green forces program order -----------------------------------------------


@_over_step_lengths
def test_nothing_pending_at_maximum_green_forces_the_next_stage_in_program_order(step_length_s):
    plan = _s0_plan()

    _, ticks = _drive(plan, until_s=61.0, step_length_s=step_length_s)

    forced = _of_kind(ticks, SignalEventKind.MAX_GREEN_FORCED)
    assert [(at_s, event.from_phase_id, event.to_phase_id) for at_s, event in forced] == [
        (_approx_s(60.0), PhaseId(0), PhaseId(2))
    ]
    assert _set_phases(ticks) == [(_approx_s(60.0), 1)]


# --- (e) seeding inside a transition phase -------------------------------------------------


@_over_step_lengths
def test_seeding_inside_a_transition_phase_targets_the_next_stage_and_completes_the_chain(
    step_length_s,
):
    plan = _s0_plan()

    executor, ticks = _drive(
        plan,
        until_s=4.0,
        phase_index=1,
        phase_elapsed_s=1.0,
        now_s=1.0,
        step_length_s=step_length_s,
    )

    assert _set_phases(ticks) == [(_approx_s(3.0), 2)]
    entered = _of_kind(ticks, SignalEventKind.STAGE_ENTERED)
    assert [(at_s, event.from_phase_id, event.to_phase_id) for at_s, event in entered] == [
        (_approx_s(3.0), PhaseId(1), PhaseId(2))
    ]
    assert executor.phase_state(4.0).current_stage_id == PhaseId(2)
    assert not executor.phase_state(4.0).in_transition


def test_the_seeded_state_of_a_transition_phase_reads_as_in_transition_before_the_first_tick():
    plan = _s0_plan()
    sumo = _FakeSumo(_program_duration_s(plan), phase_index=1, phase_elapsed_s=1.0, now_s=1.0)

    executor = SignalExecutor(plan, sumo.state(), sumo.now_s, STEP_LENGTH_S)

    phase_state = executor.phase_state(1.0)
    assert phase_state.in_transition
    assert phase_state.current_stage_id == PhaseId(2)
    assert phase_state.elapsed_s == _approx_s(1.0)
    assert phase_state.pending is None


# --- a chain of two transition phases (gate 1 re-review: nothing drove one) -----------------

# A yellow followed by an all-red, as `netconvert --tls.allred.time` generates (spec §4.2).
ALL_RED_DURATION_S = 2.0


def _yellow_then_all_red_plan() -> SignalPlan:
    return _plan(
        [_stage(0, (1, 2)), _stage(3, (4, 5))],
        {
            1: S0_TRANSITION_DURATION_S,
            2: ALL_RED_DURATION_S,
            4: S0_TRANSITION_DURATION_S,
            5: ALL_RED_DURATION_S,
        },
    )


@_over_step_lengths
def test_a_two_phase_chain_runs_yellow_then_all_red_then_the_target(step_length_s):
    plan = _yellow_then_all_red_plan()

    _, ticks = _drive(plan, {10.0: PhaseId(3)}, until_s=16.0, step_length_s=step_length_s)

    assert _set_phases(ticks) == [(_approx_s(10.0), 1), (_approx_s(13.0), 2), (_approx_s(15.0), 3)]
    entered = _of_kind(ticks, SignalEventKind.STAGE_ENTERED)
    assert [(at_s, event.from_phase_id, event.to_phase_id) for at_s, event in entered] == [
        (_approx_s(15.0), PhaseId(2), PhaseId(3))
    ]
    assert _at(ticks, 15.0).after.pending is None
    assert not _at(ticks, 16.0).before.in_transition


@_over_step_lengths
def test_seeding_inside_the_second_phase_of_a_chain_finishes_only_its_remainder(step_length_s):
    plan = _yellow_then_all_red_plan()

    executor, ticks = _drive(
        plan,
        until_s=3.0,
        phase_index=2,
        phase_elapsed_s=1.0,
        now_s=1.0,
        step_length_s=step_length_s,
    )

    assert _set_phases(ticks) == [(_approx_s(2.0), 3)]
    assert executor.phase_state(3.0).current_stage_id == PhaseId(3)
    assert not executor.phase_state(3.0).in_transition


def test_the_phase_state_inside_a_chain_defers_past_every_remaining_phase():
    # Seeded 1 s into a 3 s yellow: 2 s of yellow, 2 s of all-red, then the target's minimum
    # green -- the re-review's worked example (spec §6.4, deferred_until_s).
    plan = _yellow_then_all_red_plan()
    sumo = _FakeSumo(_program_duration_s(plan), phase_index=1, phase_elapsed_s=1.0, now_s=1.0)

    executor = SignalExecutor(plan, sumo.state(), sumo.now_s, STEP_LENGTH_S)

    phase_state = executor.phase_state(1.0)
    assert phase_state.in_transition
    assert phase_state.deferred_until_s == _approx_s(3.0 + ALL_RED_DURATION_S + MIN_GREEN_S)


# --- (f) the hold command on stage entry ---------------------------------------------------


@_over_step_lengths
def test_entering_a_stage_holds_it_past_maximum_green_so_sumo_never_pre_empts(step_length_s):
    plan = _s0_plan()

    _, ticks = _drive(plan, {10.0: PhaseId(2)}, until_s=15.0, step_length_s=step_length_s)

    assert _at(ticks, 13.0).commands == (
        SetPhase(INTERSECTION, 2),
        SetRemainingDuration_s(INTERSECTION, MAX_GREEN_S + step_length_s),
    )
    assert _at(ticks, 0.0).commands == (
        SetRemainingDuration_s(INTERSECTION, MAX_GREEN_S + step_length_s),
    )


# --- (g) illegal requests are rejected, never raised ---------------------------------------


@_over_step_lengths
def test_a_request_for_a_transition_phase_is_rejected_as_not_a_stage(step_length_s):
    plan = _s0_plan()

    _, ticks = _drive(plan, {0.0: PhaseId(1)}, until_s=0.0, step_length_s=step_length_s)

    assert not [command for command in ticks[0].commands if isinstance(command, SetPhase)]
    rejected = _of_kind(ticks, SignalEventKind.ACTION_REJECTED)
    assert [(event.to_phase_id, event.reason) for _, event in rejected] == [
        (PhaseId(1), RejectionReason.NOT_A_STAGE)
    ]


@_over_step_lengths
def test_a_request_for_the_current_stage_is_rejected_as_already_current(step_length_s):
    plan = _s0_plan()

    executor, ticks = _drive(plan, {12.0: PhaseId(0)}, until_s=12.0, step_length_s=step_length_s)

    rejected = _of_kind(ticks, SignalEventKind.ACTION_REJECTED)
    assert [(at_s, event.reason) for at_s, event in rejected] == [
        (_approx_s(12.0), RejectionReason.ALREADY_CURRENT)
    ]
    assert executor.phase_state(12.0).pending is None


# --- the mask the contract reads (§6.4) -----------------------------------------------------


@_over_step_lengths
def test_the_phase_state_exposes_when_a_deferred_request_becomes_servable(step_length_s):
    plan = _s0_plan()

    executor, _ = _drive(plan, {4.0: PhaseId(2)}, until_s=4.0, step_length_s=step_length_s)

    phase_state = executor.phase_state(4.0)
    assert phase_state.pending == PhaseId(2)
    assert phase_state.deferred_until_s == _approx_s(MIN_GREEN_S)
    assert not phase_state.max_green_reached


def test_the_phase_state_reports_maximum_green_reached_before_the_tick_that_forces():
    # The mask is read to build the observation, so it is read before the tick that acts on
    # it; at maximum green it must already say the force is coming (spec §6.4).
    plan = _s0_plan()
    sumo = _FakeSumo(
        _program_duration_s(plan),
        phase_index=0,
        phase_elapsed_s=MAX_GREEN_S,
        now_s=MAX_GREEN_S,
    )
    executor = SignalExecutor(plan, sumo.state(), sumo.now_s, STEP_LENGTH_S)

    assert executor.phase_state(MAX_GREEN_S).max_green_reached
    assert executor.phase_state(MAX_GREEN_S).deferred_until_s is None

    _, events = executor.tick(sumo.state(), sumo.now_s, None)

    assert [event.kind for event in events] == [SignalEventKind.MAX_GREEN_FORCED]


@_over_step_lengths
def test_the_phase_state_answers_for_the_time_it_is_given_not_for_the_last_tick(step_length_s):
    plan = _s0_plan()

    executor, _ = _drive(plan, until_s=MAX_GREEN_S - 1.0, step_length_s=step_length_s)

    ran = executor.phase_state(MAX_GREEN_S - 1.0)
    assert ran.elapsed_s == _approx_s(MAX_GREEN_S - 1.0)
    assert not ran.max_green_reached
    about_to_run = executor.phase_state(MAX_GREEN_S)
    assert about_to_run.elapsed_s == _approx_s(MAX_GREEN_S)
    assert about_to_run.max_green_reached


@_over_step_lengths
def test_the_mask_stops_deferring_on_exactly_the_tick_the_executor_serves(step_length_s):
    # Repeated addition of 0.1 s reaches minimum green at 9.99999999999998 s, so a mask that
    # compares without the tolerance the serve uses would still say "deferred" on the tick
    # the transition starts.
    plan = _s0_plan()

    _, ticks = _drive(
        plan, {1.0: PhaseId(2)}, until_s=MIN_GREEN_S + 1.0, step_length_s=step_length_s
    )

    started = [
        tick.at_s
        for tick in ticks
        if any(event.kind is SignalEventKind.TRANSITION_STARTED for event in tick.events)
    ]
    servable = [
        tick.at_s
        for tick in ticks
        if tick.before.pending is not None and tick.before.deferred_until_s is None
    ]
    assert started == [_approx_s(MIN_GREEN_S)]
    assert servable[:1] == started


@_over_step_lengths
def test_the_phase_state_stops_deferring_at_the_time_it_is_asked_about(step_length_s):
    plan = _s0_plan()

    executor, _ = _drive(
        plan, {1.0: PhaseId(2)}, until_s=MIN_GREEN_S - 1.0, step_length_s=step_length_s
    )

    assert executor.phase_state(MIN_GREEN_S - 1.0).deferred_until_s == _approx_s(MIN_GREEN_S)
    assert executor.phase_state(MIN_GREEN_S).deferred_until_s is None


@_over_step_lengths
def test_a_request_after_minimum_green_is_recorded_as_stage_requested_and_served_at_once(
    step_length_s,
):
    plan = _s0_plan()

    _, ticks = _drive(
        plan, {MIN_GREEN_S: PhaseId(2)}, until_s=MIN_GREEN_S + 1.0, step_length_s=step_length_s
    )

    requested = _of_kind(ticks, SignalEventKind.STAGE_REQUESTED)
    assert [
        (at_s, event.from_phase_id, event.to_phase_id, event.reason) for at_s, event in requested
    ] == [(_approx_s(MIN_GREEN_S), PhaseId(0), PhaseId(2), None)]
    assert not _of_kind(ticks, SignalEventKind.REQUEST_DEFERRED)
    assert [at_s for at_s, _ in _of_kind(ticks, SignalEventKind.TRANSITION_STARTED)] == [
        _approx_s(MIN_GREEN_S)
    ]


@_over_step_lengths
def test_a_request_arriving_during_a_transition_is_deferred_as_in_transition(step_length_s):
    plan = _three_stage_plan()

    _, ticks = _drive(
        plan,
        {MIN_GREEN_S: PhaseId(2), MIN_GREEN_S + 1.0: PhaseId(4)},
        until_s=MIN_GREEN_S + 2.0,
        step_length_s=step_length_s,
    )

    deferred = _of_kind(ticks, SignalEventKind.REQUEST_DEFERRED)
    assert [
        (at_s, event.from_phase_id, event.to_phase_id, event.reason) for at_s, event in deferred
    ] == [(_approx_s(MIN_GREEN_S + 1.0), PhaseId(2), PhaseId(4), DeferralReason.IN_TRANSITION)]


@_over_step_lengths
def test_the_phase_state_in_a_transition_defers_until_the_chain_ends_plus_minimum_green(
    step_length_s,
):
    plan = _s0_plan()

    executor, _ = _drive(
        plan, {MIN_GREEN_S: PhaseId(2)}, until_s=MIN_GREEN_S + 1.0, step_length_s=step_length_s
    )

    phase_state = executor.phase_state(MIN_GREEN_S + 1.0)
    assert phase_state.in_transition
    assert phase_state.current_stage_id == PhaseId(2)
    assert not phase_state.max_green_reached
    assert phase_state.deferred_until_s == _approx_s(
        MIN_GREEN_S + S0_TRANSITION_DURATION_S + MIN_GREEN_S
    )


# --- reconciliation ---------------------------------------------------------------------------


def _seeded_at_stage_zero(step_length_s: float = STEP_LENGTH_S) -> SignalExecutor:
    return SignalExecutor(_s0_plan(), _state(0, 0.0), 0.0, step_length_s)


def test_a_phase_index_that_disagrees_with_the_executor_mode_raises_naming_both():
    executor = _seeded_at_stage_zero()

    with pytest.raises(ValueError, match=r"reports phase 2.*expects phase 0"):
        executor.tick(_state(2, 0.0), 0.0, None)


def test_a_phase_elapsed_that_disagrees_by_more_than_one_step_raises():
    executor = _seeded_at_stage_zero()

    with pytest.raises(ValueError, match=r"9.0 s.*1.0 s"):
        executor.tick(_state(0, 9.0), 1.0, None)


@_over_step_lengths
def test_a_phase_elapsed_that_lags_the_executor_by_exactly_one_step_reconciles(step_length_s):
    executor = _seeded_at_stage_zero(step_length_s)

    commands, events = executor.tick(_state(0, 0.0), step_length_s, None)

    assert commands == (SetRemainingDuration_s(INTERSECTION, MAX_GREEN_S + step_length_s),)
    assert events == ()


@_over_step_lengths
def test_a_phase_elapsed_that_lags_the_executor_by_one_step_more_than_that_raises(step_length_s):
    executor = _seeded_at_stage_zero(step_length_s)

    with pytest.raises(ValueError, match="may differ by at most one step"):
        executor.tick(_state(0, 0.0), 2 * step_length_s, None)


def test_a_state_for_another_intersection_raises():
    executor = _seeded_at_stage_zero()
    elsewhere = IntersectionState(
        intersection_id=IntersectionId("B1"),
        program_id=PROGRAM_ID,
        phase_index=0,
        phase_elapsed_s=0.0,
        connections=(),
    )

    with pytest.raises(ValueError, match="B1"):
        executor.tick(elsewhere, 0.0, None)


# --- property tests (spec §10) ----------------------------------------------------------------

# Small enough that one hypothesis example covers several cycles; the executor reads no
# absolute magnitude, only the ordering of elapsed_s against the envelope.
PROPERTY_MIN_GREEN_S = 4.0
PROPERTY_MAX_GREEN_S = 12.0
PROPERTY_TRANSITION_DURATION_S = 2.0
PROPERTY_PROGRAM_DURATION_S = 20.0


def _property_plan() -> SignalPlan:
    stages = [
        _stage(
            phase_id,
            (phase_id + 1,),
            min_green_s=PROPERTY_MIN_GREEN_S,
            max_green_s=PROPERTY_MAX_GREEN_S,
            program_duration_s=PROPERTY_PROGRAM_DURATION_S,
        )
        for phase_id in (0, 2, 4)
    ]
    return _plan(
        stages,
        dict.fromkeys((1, 3, 5), PROPERTY_TRANSITION_DURATION_S),
    )


# Legal stages, a transition phase, an index the program lacks, and the no-op.
_REQUESTS = st.sampled_from(
    [None, PhaseId(0), PhaseId(2), PhaseId(4), PhaseId(1), PhaseId(5), PhaseId(9)]
)
_REQUEST_SEQUENCES = st.lists(_REQUESTS, min_size=1, max_size=60)
_PROPERTY_EXAMPLES = 200
_LEAVES_A_STAGE = (SignalEventKind.TRANSITION_STARTED, SignalEventKind.MAX_GREEN_FORCED)
# Every phase of the property plan, most of them entered part-way through: spec §5.1 seeds
# from whatever the first extracted state reports, and a non-zero offset or a begin_s past
# zero makes that any phase at any elapsed time, not stage 0 at 0 s.
_PROPERTY_SEEDS = st.sampled_from(
    ((0, 0.0), (0, 3.0), (2, 5.0), (4, 11.0), (1, 0.0), (3, 1.0), (5, 1.5))
)


def _run_seeded(
    plan: SignalPlan, requests: Sequence[PhaseId | None], seed: tuple[int, float]
) -> tuple[SignalExecutor, list[_Tick]]:
    phase_index, phase_elapsed_s = seed
    return _run(
        plan,
        requests,
        phase_index=phase_index,
        phase_elapsed_s=phase_elapsed_s,
        now_s=phase_elapsed_s,
    )


@settings(max_examples=_PROPERTY_EXAMPLES, deadline=None)
@given(requests=_REQUEST_SEQUENCES, seed=_PROPERTY_SEEDS)
def test_two_consecutive_set_phase_commands_never_name_two_stages(requests, seed):
    plan = _property_plan()

    _, ticks = _run_seeded(plan, requests, seed)

    selected = [phase_index for _, phase_index in _set_phases(ticks)]
    stage_indices = {int(phase_id) for phase_id in plan.stages}
    for earlier, later in pairwise(selected):
        assert not (earlier in stage_indices and later in stage_indices), selected


@settings(max_examples=_PROPERTY_EXAMPLES, deadline=None)
@given(requests=_REQUEST_SEQUENCES, seed=_PROPERTY_SEEDS)
def test_a_stage_is_never_held_past_maximum_green_nor_left_before_minimum_green(requests, seed):
    plan = _property_plan()

    _, ticks = _run_seeded(plan, requests, seed)

    # _run_seeded starts the clock at phase_elapsed_s, so whatever phase the seed names
    # began at 0.0 s; a transition seed has no stage until the first stage_entered.
    entered_at_s = 0.0
    for tick in ticks:
        for event in tick.events:
            if event.kind in _LEAVES_A_STAGE:
                assert tick.at_s - entered_at_s >= PROPERTY_MIN_GREEN_S
            if event.kind is SignalEventKind.STAGE_ENTERED:
                entered_at_s = tick.at_s
        if not tick.after.in_transition:
            assert tick.after.elapsed_s <= PROPERTY_MAX_GREEN_S + STEP_LENGTH_S


@settings(max_examples=_PROPERTY_EXAMPLES, deadline=None)
@given(requests=_REQUEST_SEQUENCES, seed=_PROPERTY_SEEDS)
def test_a_pending_request_is_served_as_soon_as_it_is_legal_and_never_against_its_own_stage(
    requests, seed
):
    plan = _property_plan()

    _, ticks = _run_seeded(plan, requests, seed)

    for tick in ticks:
        for event in tick.events:
            if event.kind is SignalEventKind.TRANSITION_STARTED:
                assert event.from_phase_id != event.to_phase_id
        if tick.after.pending is not None:
            assert tick.after.in_transition or tick.after.elapsed_s < PROPERTY_MIN_GREEN_S
            assert tick.after.pending != tick.after.current_stage_id


@settings(max_examples=_PROPERTY_EXAMPLES, deadline=None)
@given(requests=_REQUEST_SEQUENCES, seed=_PROPERTY_SEEDS)
def test_every_pending_request_that_is_replaced_is_logged_as_superseded(requests, seed):
    plan = _property_plan()

    _, ticks = _run_seeded(plan, requests, seed)

    for tick, request in zip(ticks, requests, strict=True):
        replaced = tick.before.pending
        # Spec §5.1 step 2: a request is absorbed iff it names a stage other than the
        # current one (the transition's target, during one). The row is owed on the tick it
        # is absorbed, whether or not the same tick then serves it and clears pending.
        absorbed = (
            request if request in plan.stages and request != tick.before.current_stage_id else None
        )
        expected = (
            [(replaced, absorbed)]
            if replaced is not None and absorbed is not None and absorbed != replaced
            else []
        )
        superseded = [
            event for event in tick.events if event.kind is SignalEventKind.REQUEST_SUPERSEDED
        ]
        assert [(event.from_phase_id, event.to_phase_id) for event in superseded] == expected


@settings(max_examples=_PROPERTY_EXAMPLES, deadline=None)
@given(requests=_REQUEST_SEQUENCES, seed=_PROPERTY_SEEDS)
def test_replaying_the_same_request_sequence_yields_identical_commands_and_events(requests, seed):
    plan = _property_plan()

    _, first = _run_seeded(plan, requests, seed)
    _, second = _run_seeded(plan, requests, seed)

    assert first == second
