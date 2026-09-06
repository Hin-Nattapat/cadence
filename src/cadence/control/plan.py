"""The signal plan: which program phases a controller may request, under which envelope.

CONTRACT: a stage is a program phase with at least one permissive signal and no yellow, and
its PhaseId is its program index (SIG-D03). Every transition between stages is the program's
own phases, so the plan carries the successor chain rather than a lamp state (SIG-D01). The
plan is built once, at connection time, and refuses a program no executor can drive safely
(spec §5.2). An intersection the envelope does not name gets no plan and is simply not
controlled; an intersection the envelope names that the network has no program for is a data
error and raises.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cadence.simulation.signal_plan_file import IntersectionEnvelope, SignalPlanFile
from cadence.simulation.state import SignalState
from cadence.simulation.topology import ConnectionInfo, NetworkTopology, PhaseInfo, ProgramType
from cadence.types import ConnectionId, IntersectionId, MovementId, PhaseId

# The signals SIG-D03 calls a clearance: present anywhere in a phase, the phase is a
# transition and never a stage, whatever else it shows.
_CLEARANCE_SIGNALS = frozenset({SignalState.YELLOW, SignalState.RED_YELLOW})

# A link index can carry more than one connection: SUMO's getControlledLinks returns a group
# per index, and a grouped junction puts several in one group (ST-D05).
type _ConnectionsByLinkIndex = dict[tuple[IntersectionId, int], list[ConnectionInfo]]


@dataclass(frozen=True, slots=True)
class Stage:
    phase_id: PhaseId
    permitted_connections: frozenset[ConnectionId]
    permitted_movements: frozenset[MovementId]
    min_green_s: float
    max_green_s: float
    program_duration_s: float
    transition_phase_indices: tuple[int, ...]

    @property
    def movement_signature(self) -> frozenset[MovementId]:
        # The stage identity that survives a network regeneration, which a program index does
        # not (spec §4.3, ST-D05). M8's Max-Pressure keys on this, not on phase_id (MP-D04).
        return self.permitted_movements


@dataclass(frozen=True, slots=True)
class SignalPlan:
    intersection_id: IntersectionId
    program_id: str
    stages: Mapping[PhaseId, Stage]
    transition_phase_duration_s: Mapping[int, float]

    def next_stage_in_program_order(self, phase_id: PhaseId) -> PhaseId:
        order = tuple(self.stages)
        if phase_id not in self.stages:
            raise ValueError(
                f"intersection {self.intersection_id}: phase {phase_id} is not a stage of "
                f"program {self.program_id}; its stages are {list(order)}"
            )
        return order[(order.index(phase_id) + 1) % len(order)]


def build_signal_plans(
    topology: NetworkTopology, envelope: SignalPlanFile
) -> Mapping[IntersectionId, SignalPlan]:
    program_by_intersection: dict[IntersectionId, list[PhaseInfo]] = defaultdict(list)
    for phase in topology.phases:
        program_by_intersection[phase.intersection_id].append(phase)

    connections_by_link_index: _ConnectionsByLinkIndex = defaultdict(list)
    for connection in topology.connections.values():
        key = (connection.intersection_id, connection.link_index)
        connections_by_link_index[key].append(connection)

    plans: dict[IntersectionId, SignalPlan] = {}
    for name, intersection_envelope in sorted(envelope.intersections.items()):
        intersection_id = IntersectionId(name)
        program = program_by_intersection.get(intersection_id)
        if not program:
            raise ValueError(
                f"signal_plan.yaml names intersection {intersection_id}, which the network "
                f"has no traffic-light program for"
            )
        plans[intersection_id] = _build_one_plan(
            intersection_id=intersection_id,
            program=tuple(sorted(program, key=lambda phase: phase.phase_index)),
            intersection_envelope=intersection_envelope,
            topology=topology,
            connections_by_link_index=connections_by_link_index,
        )
    return MappingProxyType(plans)


def _is_stage(phase: PhaseInfo) -> bool:
    if any(signal in _CLEARANCE_SIGNALS for signal in phase.signals):
        return False
    return any(signal.permits_movement for signal in phase.signals)


def _build_one_plan(
    *,
    intersection_id: IntersectionId,
    program: tuple[PhaseInfo, ...],
    intersection_envelope: IntersectionEnvelope,
    topology: NetworkTopology,
    connections_by_link_index: _ConnectionsByLinkIndex,
) -> SignalPlan:
    program_id = program[0].program_id
    _refuse_a_program_that_is_not_static(intersection_id, program)

    chains = {
        phase.phase_index: _successor_chain(intersection_id, program, position)
        for position, phase in enumerate(program)
        if _is_stage(phase)
    }
    by_index = {phase.phase_index: phase for phase in program}
    for stage_index, chain in chains.items():
        _refuse_a_transition_that_turns_a_signal_on(
            intersection_id=intersection_id,
            stage=by_index[stage_index],
            chain=chain,
            by_index=by_index,
            connections_by_link_index=connections_by_link_index,
        )
    _refuse_an_envelope_that_disagrees_with_the_program(
        intersection_id, frozenset(chains), intersection_envelope
    )

    stages: dict[PhaseId, Stage] = {}
    for stage_index, chain in chains.items():
        phase = by_index[stage_index]
        permitted_connections = frozenset(
            connection.connection_id
            for link_index, signal in enumerate(phase.signals)
            if signal.permits_movement
            for connection in connections_by_link_index.get((intersection_id, link_index), ())
        )
        permitted_movements = frozenset(
            topology.movements[topology.connections[identifier].movement_id].movement_id
            for identifier in permitted_connections
        )
        stage_envelope = intersection_envelope.stages[stage_index]
        stages[PhaseId(stage_index)] = Stage(
            phase_id=PhaseId(stage_index),
            permitted_connections=permitted_connections,
            permitted_movements=permitted_movements,
            min_green_s=stage_envelope.min_green_s,
            max_green_s=stage_envelope.max_green_s,
            program_duration_s=phase.duration_s,
            transition_phase_indices=chain,
        )

    return SignalPlan(
        intersection_id=intersection_id,
        program_id=program_id,
        stages=MappingProxyType(stages),
        transition_phase_duration_s=MappingProxyType(
            {
                phase.phase_index: phase.duration_s
                for phase in program
                if phase.phase_index not in chains
            }
        ),
    )


def _refuse_a_program_that_is_not_static(
    intersection_id: IntersectionId, program: tuple[PhaseInfo, ...]
) -> None:
    kinds = {phase.program_type for phase in program}
    if kinds != {ProgramType.STATIC}:
        raise ValueError(
            f"intersection {intersection_id}: program {program[0].program_id} has type "
            f"{', '.join(sorted(kind.value for kind in kinds))}; only a static program can be "
            f"driven by the executor, since any other switches by itself (SIG-D01)"
        )


def _successor_chain(
    intersection_id: IntersectionId, program: tuple[PhaseInfo, ...], position: int
) -> tuple[int, ...]:
    chain: list[int] = []
    cursor = (position + 1) % len(program)
    while cursor != position:
        successor = program[cursor]
        if _is_stage(successor):
            break
        chain.append(successor.phase_index)
        cursor = (cursor + 1) % len(program)
    if not chain:
        raise ValueError(
            f"intersection {intersection_id}: stage {program[position].phase_index} is "
            f"followed directly by stage {program[(position + 1) % len(program)].phase_index} "
            f"with no transition phase between them, so no executor can leave it safely "
            f"(SIG-D01)"
        )
    return tuple(chain)


def _refuse_a_transition_that_turns_a_signal_on(
    *,
    intersection_id: IntersectionId,
    stage: PhaseInfo,
    chain: tuple[int, ...],
    by_index: Mapping[int, PhaseInfo],
    connections_by_link_index: _ConnectionsByLinkIndex,
) -> None:
    for transition_index in chain:
        transition = by_index[transition_index]
        pairs = zip(stage.signals, transition.signals, strict=True)
        for link_index, (stage_signal, transition_signal) in enumerate(pairs):
            if stage_signal.permits_movement:
                continue
            # RED_YELLOW, RED and the two OFF_* states let nothing move, so none of them is
            # a signal turned on; a red-yellow program is drivable (spec §5.2).
            if not (transition_signal.permits_movement or transition_signal is SignalState.YELLOW):
                continue
            raise ValueError(
                f"intersection {intersection_id}: transition phase {transition_index} shows "
                f"{transition_signal.value} at link index {link_index} "
                f"({_named_connections(intersection_id, link_index, connections_by_link_index)}), "
                f"which stage {stage.phase_index} showed {stage_signal.value}; a transition "
                f"phase may not turn a signal on, and one that does is a stage in disguise "
                f"(SIG-D03)"
            )


def _named_connections(
    intersection_id: IntersectionId,
    link_index: int,
    connections_by_link_index: _ConnectionsByLinkIndex,
) -> str:
    connections = connections_by_link_index.get((intersection_id, link_index), ())
    return ", ".join(sorted(connection.connection_id for connection in connections)) or (
        "no connection"
    )


def _refuse_an_envelope_that_disagrees_with_the_program(
    intersection_id: IntersectionId,
    stage_indices: frozenset[int],
    intersection_envelope: IntersectionEnvelope,
) -> None:
    declared = frozenset(intersection_envelope.stages)
    if declared == stage_indices:
        return
    faults = []
    if declared - stage_indices:
        faults.append(f"names stages the program lacks {sorted(declared - stage_indices)}")
    if stage_indices - declared:
        faults.append(f"omits stages it has {sorted(stage_indices - declared)}")
    raise ValueError(f"intersection {intersection_id}: signal_plan.yaml {' and '.join(faults)}")
