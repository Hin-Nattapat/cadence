"""What the executor writes down: one row per decision, in simulated time (spec §5.4).

CONTRACT: every field is a function of simulated time and canonical domain state, never of
a wall clock (SIG-D07), so two faithful runs produce byte-identical rows. `from_phase_id`
and `to_phase_id` are program phase indices; both name stages in every kind but
`stage_entered`, whose `from_phase_id` is the transition phase being left. `reason` carries
a `DeferralReason` for `request_deferred`, a `RejectionReason` for `action_rejected`, and is
None for every other kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cadence.types import IntersectionId, PhaseId


class SignalEventKind(StrEnum):
    STAGE_REQUESTED = "stage_requested"
    REQUEST_DEFERRED = "request_deferred"
    REQUEST_SUPERSEDED = "request_superseded"
    TRANSITION_STARTED = "transition_started"
    STAGE_ENTERED = "stage_entered"
    MAX_GREEN_FORCED = "max_green_forced"
    ACTION_REJECTED = "action_rejected"


class DeferralReason(StrEnum):
    MIN_GREEN = "min_green"
    IN_TRANSITION = "in_transition"


class RejectionReason(StrEnum):
    NOT_A_STAGE = "not_a_stage"
    ALREADY_CURRENT = "already_current"


@dataclass(frozen=True, slots=True)
class SignalEvent:
    time_s: float
    intersection_id: IntersectionId
    kind: SignalEventKind
    from_phase_id: PhaseId | None
    to_phase_id: PhaseId | None
    reason: str | None
