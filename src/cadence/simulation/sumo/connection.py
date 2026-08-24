"""SUMO process lifecycle and per-step raw state retrieval.

Owns starting SUMO, advancing time, collecting events, and shutting down. It decides no
traffic policy; that belongs to the controller layer, which does not exist until M2.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, TracebackType
from typing import Self

from cadence.simulation.events import EventKind, SimulationEvent, StepResult
from cadence.simulation.ground_truth import SimulationGroundTruth
from cadence.simulation.manifest import TerminationReason
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.state import TeleportEvent, TeleportKind
from cadence.simulation.sumo.binding import BindingKind, load_binding
from cadence.simulation.sumo.command import build_sumo_command
from cadence.simulation.sumo.extract import GroundTruthReader, StateExtractor, TraversalDetector
from cadence.simulation.sumo.topology_reader import read_topology
from cadence.simulation.topology import NetworkTopology
from cadence.types import VehicleId

# Maps an EventKind to the traci.simulation getter that reports it for the step just taken.
_EVENT_GETTERS: tuple[tuple[EventKind, str], ...] = (
    (EventKind.DEPARTED, "getDepartedIDList"),
    (EventKind.ARRIVED, "getArrivedIDList"),
    (EventKind.TELEPORT_STARTED, "getStartingTeleportIDList"),
    (EventKind.TELEPORT_ENDED, "getEndingTeleportIDList"),
    (EventKind.COLLISION, "getCollidingVehiclesIDList"),
)


class SumoConnection:
    def __init__(
        self,
        config: ScenarioConfig,
        paths: ScenarioPaths,
        *,
        seed: int,
        binding: BindingKind,
        use_gui: bool = False,
        tripinfo_path: Path | None = None,
    ) -> None:
        self._config = config
        self._paths = paths
        self._seed = seed
        self._binding_kind = binding
        self._use_gui = use_gui
        self._tripinfo_path = tripinfo_path
        self._binding: ModuleType | None = None
        self._topology: NetworkTopology | None = None
        self._extractor: StateExtractor | None = None
        self._traversals: TraversalDetector | None = None
        self._ground_truth: GroundTruthReader | None = None
        self.is_closed = False

    def __enter__(self) -> Self:
        binding = load_binding(self._binding_kind)
        command = build_sumo_command(
            self._config,
            self._paths,
            seed=self._seed,
            use_gui=self._use_gui,
            tripinfo_path=self._tripinfo_path,
        )
        binding.start(command)
        self._binding = binding
        try:
            self._topology = read_topology(binding)
            self._extractor = StateExtractor(self._topology)
            self._traversals = TraversalDetector(self._topology)
            self._ground_truth = GroundTruthReader(self._topology)
        except Exception:
            # GOTCHA: Python does not call __exit__ when __enter__ raises, so the caller
            # never gets an object to close. libsumo permits one simulation per process,
            # which makes a leaked process fatal to every later connection in it.
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _require_open(self) -> ModuleType:
        if self._binding is None or self.is_closed:
            raise RuntimeError("simulation connection is closed")
        return self._binding

    def _require_extraction(self) -> tuple[StateExtractor, TraversalDetector]:
        # Set together with _binding in __enter__ and never individually, so the invariant
        # _require_open() checks holds for these too; mypy still needs the narrowing spelled
        # out since it does not track that cross-attribute relationship.
        if self._extractor is None or self._traversals is None:
            raise RuntimeError("simulation connection is closed")
        return self._extractor, self._traversals

    @property
    def topology(self) -> NetworkTopology:
        # Deliberately not a `binding` property. The architecture test scans imports, not
        # method calls, so exposing the module would hand every holder of a connection a
        # route to traci that ARCH-D02 could not see.
        if self._topology is None:
            raise RuntimeError("simulation connection is closed")
        return self._topology

    def step(self) -> StepResult:
        binding = self._require_open()
        extractor, traversal_detector = self._require_extraction()
        binding.simulationStep()
        time_s = float(binding.simulation.getTime())
        events = tuple(
            SimulationEvent(time_s=time_s, kind=kind, vehicle_id=VehicleId(vehicle))
            for kind, getter in _EVENT_GETTERS
            for vehicle in getattr(binding.simulation, getter)()
        )
        teleporting = binding.simulation.getStartingTeleportIDList()
        teleports = tuple(
            TeleportEvent(
                time_s=time_s,
                vehicle_id=VehicleId(vehicle_id),
                # GOTCHA: getLaneID() returns "" for a vehicle mid-teleport. The lane it
                # left survives only in what the detector is holding, so read it here and
                # not from the binding.
                from_lane_id=traversal_detector.held_lane(vehicle_id),
                kind=TeleportKind.STARTED,
            )
            for vehicle_id in teleporting
        )
        traversal_detector.forget(teleporting)
        traversals = traversal_detector.observe(binding, time_s)
        return StepResult(
            time_s=time_s,
            events=events,
            state=extractor.extract(binding, time_s, events, traversals),
            teleports=teleports,
        )

    def read_ground_truth(self) -> SimulationGroundTruth:
        # ST-D01, ST-D09: the one named, greppable place a caller reaches for privileged
        # information. It is not returned from step() alongside everything else.
        binding = self._require_open()
        if self._ground_truth is None:
            raise RuntimeError("simulation connection is closed")
        return self._ground_truth.read(binding, float(binding.simulation.getTime()))

    def unmatched_traversals(self) -> int:
        _, traversal_detector = self._require_extraction()
        return traversal_detector.unmatched_count

    def time_s(self) -> float:
        return float(self._require_open().simulation.getTime())

    def termination_reason(self) -> TerminationReason | None:
        """Which condition ended the run, or None if neither has fired yet."""
        binding = self._require_open()
        # GOTCHA: SUMO does not stop at --end while a client is attached; the client owns
        # the clock. This check comes first because a run that reaches the horizon with
        # vehicles still loaded is a horizon stop, not a drain.
        if float(binding.simulation.getTime()) >= float(binding.simulation.getEndTime()):
            return TerminationReason.HORIZON
        # getMinExpectedNumber counts loaded-but-not-yet-departed vehicles too, so it
        # reaching zero is the correct drain condition, not an empty network.
        if int(binding.simulation.getMinExpectedNumber()) == 0:
            return TerminationReason.DRAINED
        return None

    def is_finished(self) -> bool:
        return self.termination_reason() is not None

    def close(self) -> None:
        # A close that fails must still mark the connection unusable. libsumo allows one
        # simulation per process, so an object that goes on claiming to be open is a
        # worse problem than whatever made the close fail.
        try:
            if self._binding is not None and not self.is_closed:
                self._binding.close()
        finally:
            self.is_closed = True
            self._topology = None
            self._extractor = None
            self._traversals = None
            self._ground_truth = None
