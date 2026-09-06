"""The signal executor: the state machine between a controller's request and the simulator.

CONTRACT: one executor per controlled intersection, one `tick` per simulation step, called
after the step that produced the state and before the next one (SIM-D02). It selects
program phases and emits commands as data -- it composes no lamp string (SIG-D01), imports
nothing from `simulation/sumo` (SIG-D04), and reads no clock and no randomness, so `tick` is
a function of the plan, its own three-field state and its arguments (AP-06). An illegal
request is rejected and logged, never raised (spec §6.5); a simulator that changed phase
without being asked is a loud failure and does raise (spec §5.1 step 1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cadence.control.events import (
    DeferralReason,
    RejectionReason,
    SignalEvent,
    SignalEventKind,
)
from cadence.control.plan import SignalPlan, Stage
from cadence.simulation.state import IntersectionState
from cadence.types import IntersectionId, PhaseId

# Simulated time is accumulated by repeated addition of the step length, so an elapsed
# comparison against an envelope boundary must not turn on the last bit of a float.
_CLOCK_TOLERANCE_S = 1e-9


@dataclass(frozen=True, slots=True)
class SetPhase:
    intersection_id: IntersectionId
    phase_index: int


# CLAUDE.md §4 puts the unit in the name; N801's CapWords rule has no way to spell `_s`.
@dataclass(frozen=True, slots=True)
class SetRemainingDuration_s:  # noqa: N801
    intersection_id: IntersectionId
    remaining_s: float


type SignalCommand = SetPhase | SetRemainingDuration_s


@dataclass(frozen=True, slots=True)
class SignalPhaseState:
    """The executor's own view, and the source of the legal action mask (spec §6.4)."""

    intersection_id: IntersectionId
    current_stage_id: PhaseId
    elapsed_s: float
    pending: PhaseId | None
    in_transition: bool
    max_green_reached: bool
    deferred_until_s: float | None


@dataclass(frozen=True, slots=True)
class _InStage:
    phase_id: PhaseId
    # GOTCHA: spec §5.1 step 6 holds a stage "on entering" it, but a seeded executor never
    # enters the stage it wakes up inside, and SUMO would switch out of it at
    # program_duration_s. The hold is owed for the seeded stage too, so it is carried here
    # and paid on the first tick that still holds the stage.
    hold_owed: bool


@dataclass(frozen=True, slots=True)
class _InTransition:
    target_phase_id: PhaseId
    current_phase_index: int
    remaining_phase_indices: tuple[int, ...]


type _Mode = _InStage | _InTransition


class SignalExecutor:
    def __init__(
        self,
        plan: SignalPlan,
        first: IntersectionState,
        now_s: float,
        step_length_s: float,
    ) -> None:
        self._plan = plan
        self._step_length_s = step_length_s
        self._mode = _seed_mode(plan, first)
        self._entered_at_s = now_s - first.phase_elapsed_s
        self._pending: PhaseId | None = None

    def phase_state(self, now_s: float) -> SignalPhaseState:
        mode = self._mode
        elapsed_s = now_s - self._entered_at_s
        if isinstance(mode, _InStage):
            stage = self._plan.stages[mode.phase_id]
            servable_at_s = self._entered_at_s + stage.min_green_s
            deferred = not self._min_green_expired(mode.phase_id, now_s)
            return SignalPhaseState(
                intersection_id=self._plan.intersection_id,
                current_stage_id=mode.phase_id,
                elapsed_s=elapsed_s,
                pending=self._pending,
                in_transition=False,
                max_green_reached=_has_reached(elapsed_s, stage.max_green_s),
                deferred_until_s=servable_at_s if deferred else None,
            )
        target = self._plan.stages[mode.target_phase_id]
        chain_ends_at_s = self._entered_at_s + sum(
            self._plan.transition_phase_duration_s[index]
            for index in (mode.current_phase_index, *mode.remaining_phase_indices)
        )
        return SignalPhaseState(
            intersection_id=self._plan.intersection_id,
            current_stage_id=mode.target_phase_id,
            elapsed_s=elapsed_s,
            pending=self._pending,
            in_transition=True,
            max_green_reached=False,
            deferred_until_s=chain_ends_at_s + target.min_green_s,
        )

    def tick(
        self, state: IntersectionState, now_s: float, request: PhaseId | None
    ) -> tuple[tuple[SignalCommand, ...], tuple[SignalEvent, ...]]:
        self._reconcile(state, now_s)
        commands: list[SignalCommand] = []
        events: list[SignalEvent] = []
        self._absorb(request, now_s, events)
        self._advance_transition(now_s, commands, events)
        self._serve_or_force(now_s, commands, events)
        self._hold(commands)
        return tuple(commands), tuple(events)

    def _reconcile(self, state: IntersectionState, now_s: float) -> None:
        plan = self._plan
        if state.intersection_id != plan.intersection_id:
            raise ValueError(
                f"executor for intersection {plan.intersection_id} was given the state of "
                f"intersection {state.intersection_id}"
            )
        mode = self._mode
        expected = mode.phase_id if isinstance(mode, _InStage) else mode.current_phase_index
        if state.phase_index != expected:
            raise ValueError(
                f"intersection {plan.intersection_id}: SUMO reports phase "
                f"{state.phase_index} while the executor expects phase {expected}; the "
                f"program switched without being asked, which SIG-D01 forbids"
            )
        drift_s = abs((now_s - self._entered_at_s) - state.phase_elapsed_s)
        if drift_s > self._step_length_s + _CLOCK_TOLERANCE_S:
            raise ValueError(
                f"intersection {plan.intersection_id}: SUMO reports phase_elapsed_s "
                f"{state.phase_elapsed_s} s in phase {state.phase_index} while the "
                f"executor's own clock says {now_s - self._entered_at_s} s; the two may "
                f"differ by at most one step of {self._step_length_s} s"
            )

    def _absorb(self, request: PhaseId | None, now_s: float, events: list[SignalEvent]) -> None:
        if request is None:
            return
        mode = self._mode
        current = mode.phase_id if isinstance(mode, _InStage) else mode.target_phase_id
        if request not in self._plan.stages:
            events.append(
                self._event(
                    now_s,
                    SignalEventKind.ACTION_REJECTED,
                    current,
                    request,
                    RejectionReason.NOT_A_STAGE,
                )
            )
            return
        if request == current:
            events.append(
                self._event(
                    now_s,
                    SignalEventKind.ACTION_REJECTED,
                    current,
                    request,
                    RejectionReason.ALREADY_CURRENT,
                )
            )
            return
        if self._pending is not None and self._pending != request:
            events.append(
                self._event(now_s, SignalEventKind.REQUEST_SUPERSEDED, self._pending, request, None)
            )
        self._pending = request
        if isinstance(mode, _InStage) and self._min_green_expired(mode.phase_id, now_s):
            events.append(
                self._event(now_s, SignalEventKind.STAGE_REQUESTED, current, request, None)
            )
            return
        reason = (
            DeferralReason.MIN_GREEN if isinstance(mode, _InStage) else DeferralReason.IN_TRANSITION
        )
        events.append(
            self._event(now_s, SignalEventKind.REQUEST_DEFERRED, current, request, reason)
        )

    def _advance_transition(
        self, now_s: float, commands: list[SignalCommand], events: list[SignalEvent]
    ) -> None:
        mode = self._mode
        if not isinstance(mode, _InTransition):
            return
        duration_s = self._plan.transition_phase_duration_s[mode.current_phase_index]
        if not _has_reached(now_s - self._entered_at_s, duration_s):
            return
        if mode.remaining_phase_indices:
            next_index, *rest = mode.remaining_phase_indices
            commands.append(SetPhase(self._plan.intersection_id, next_index))
            self._mode = _InTransition(mode.target_phase_id, next_index, tuple(rest))
            self._entered_at_s = now_s
            return
        target = mode.target_phase_id
        commands.append(SetPhase(self._plan.intersection_id, target))
        self._mode = _InStage(target, hold_owed=True)
        self._entered_at_s = now_s
        events.append(
            self._event(
                now_s,
                SignalEventKind.STAGE_ENTERED,
                PhaseId(mode.current_phase_index),
                target,
                None,
            )
        )

    def _serve_or_force(
        self, now_s: float, commands: list[SignalCommand], events: list[SignalEvent]
    ) -> None:
        mode = self._mode
        if not isinstance(mode, _InStage):
            return
        stage = self._plan.stages[mode.phase_id]
        elapsed_s = now_s - self._entered_at_s
        pending = self._pending
        if pending is not None and pending != mode.phase_id:
            if not self._min_green_expired(mode.phase_id, now_s):
                return
            self._begin_transition(stage, pending, now_s, commands)
            self._pending = None
            events.append(
                self._event(now_s, SignalEventKind.TRANSITION_STARTED, mode.phase_id, pending, None)
            )
            return
        if pending is None and _has_reached(elapsed_s, stage.max_green_s):
            forced = self._plan.next_stage_in_program_order(mode.phase_id)
            self._begin_transition(stage, forced, now_s, commands)
            events.append(
                self._event(now_s, SignalEventKind.MAX_GREEN_FORCED, mode.phase_id, forced, None)
            )

    def _hold(self, commands: list[SignalCommand]) -> None:
        mode = self._mode
        if not isinstance(mode, _InStage) or not mode.hold_owed:
            return
        stage = self._plan.stages[mode.phase_id]
        commands.append(
            SetRemainingDuration_s(
                self._plan.intersection_id, stage.max_green_s + self._step_length_s
            )
        )
        self._mode = replace(mode, hold_owed=False)

    def _begin_transition(
        self, stage: Stage, target: PhaseId, now_s: float, commands: list[SignalCommand]
    ) -> None:
        first_index, *rest = stage.transition_phase_indices
        commands.append(SetPhase(self._plan.intersection_id, first_index))
        self._mode = _InTransition(target, first_index, tuple(rest))
        self._entered_at_s = now_s

    def _min_green_expired(self, phase_id: PhaseId, now_s: float) -> bool:
        min_green_s = self._plan.stages[phase_id].min_green_s
        return _has_reached(now_s - self._entered_at_s, min_green_s)

    def _event(
        self,
        now_s: float,
        kind: SignalEventKind,
        from_phase_id: PhaseId | None,
        to_phase_id: PhaseId | None,
        reason: str | None,
    ) -> SignalEvent:
        return SignalEvent(
            time_s=now_s,
            intersection_id=self._plan.intersection_id,
            kind=kind,
            from_phase_id=from_phase_id,
            to_phase_id=to_phase_id,
            reason=reason,
        )


def _has_reached(elapsed_s: float, boundary_s: float) -> bool:
    return elapsed_s >= boundary_s - _CLOCK_TOLERANCE_S


def _seed_mode(plan: SignalPlan, first: IntersectionState) -> _Mode:
    phase_index = first.phase_index
    if phase_index in plan.stages:
        return _InStage(PhaseId(phase_index), hold_owed=True)
    for stage in plan.stages.values():
        chain = stage.transition_phase_indices
        if phase_index not in chain:
            continue
        position = chain.index(phase_index)
        return _InTransition(
            target_phase_id=plan.next_stage_in_program_order(stage.phase_id),
            current_phase_index=phase_index,
            remaining_phase_indices=chain[position + 1 :],
        )
    raise ValueError(
        f"intersection {plan.intersection_id}: the first state reports phase {phase_index}, "
        f"which program {plan.program_id} has neither as a stage nor in any successor chain"
    )
