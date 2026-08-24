"""Distinct identifier types for the traffic domain.

In SUMO an edge id and a lane id are both plain strings ("e1" versus "e1_0"), and
confusing them is the most common defect class in SUMO-based code. These NewTypes let
mypy eliminate it (PD-D04 rule R2).
"""

from typing import NewType

LaneId = NewType("LaneId", str)
EdgeId = NewType("EdgeId", str)
JunctionId = NewType("JunctionId", str)
IntersectionId = NewType("IntersectionId", str)
ConnectionId = NewType("ConnectionId", str)
MovementId = NewType("MovementId", str)
PhaseId = NewType("PhaseId", int)
VehicleId = NewType("VehicleId", str)
ScenarioId = NewType("ScenarioId", str)
ControllerId = NewType("ControllerId", str)
Seed = NewType("Seed", int)
