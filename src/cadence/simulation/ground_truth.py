"""cadence.simulation.ground_truth — privileged simulator truth. Controllers must not reach this.

CONTRACT: exact per-vehicle turn intent is unobservable in the field — on a shared lane no
sensor reports how many queued vehicles intend to turn. It exists here for validation,
debugging, and explicitly labelled oracle experiments, and an architecture test refuses any
import of this module from outside `simulation/` (ST-D01).
"""

from __future__ import annotations

from dataclasses import dataclass

from cadence.types import EdgeId, LaneId


@dataclass(frozen=True, slots=True)
class LaneTurnCount:
    lane_id: LaneId
    # None marks the residual row: vehicles on this lane whose next edge does not resolve,
    # because they are on their final edge. One such row exists per lane, written whether or
    # not it is zero, and it is what makes conservation against LaneState.vehicle_count_veh
    # possible (ST-D19, spec section 6.1).
    next_edge_id: EdgeId | None
    count_veh: int
    halting_count_veh: int
    waiting_total_now_s: float


@dataclass(frozen=True, slots=True)
class SimulationGroundTruth:
    time_s: float
    lane_turns: tuple[LaneTurnCount, ...]


@dataclass(frozen=True, slots=True)
class LaneTurnVehicleCount:
    lane_id: LaneId
    # None marks the same residual population as LaneTurnCount.next_edge_id: vehicles on
    # this lane with no next edge to attribute to.
    next_edge_id: EdgeId | None
    # Distinct vehicles ever seen on (lane_id, next_edge_id), accumulated over the whole run
    # rather than read at one step. count_veh in LaneTurnCount is a step snapshot and cannot
    # answer "how many vehicles", only "how many vehicle-steps".
    distinct_veh: int
