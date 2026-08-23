"""SUMO process lifecycle and per-step raw state retrieval.

Owns starting SUMO, advancing time, collecting events, and shutting down. It decides no
traffic policy; that belongs to the controller layer, which does not exist until M2.
"""

from __future__ import annotations

from types import ModuleType, TracebackType
from typing import Self

from cadence.simulation.events import EventKind, SimulationEvent, StepResult
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.sumo.binding import BindingKind, load_binding
from cadence.simulation.sumo.command import build_sumo_command
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
    ) -> None:
        self._config = config
        self._paths = paths
        self._seed = seed
        self._binding_kind = binding
        self._use_gui = use_gui
        self._binding: ModuleType | None = None
        self.is_closed = False

    def __enter__(self) -> Self:
        binding = load_binding(self._binding_kind)
        command = build_sumo_command(
            self._config, self._paths, seed=self._seed, use_gui=self._use_gui
        )
        binding.start(command)
        self._binding = binding
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

    def step(self) -> StepResult:
        binding = self._require_open()
        binding.simulationStep()
        time_s = float(binding.simulation.getTime())
        events = tuple(
            SimulationEvent(time_s=time_s, kind=kind, vehicle_id=VehicleId(vehicle))
            for kind, getter in _EVENT_GETTERS
            for vehicle in getattr(binding.simulation, getter)()
        )
        return StepResult(
            time_s=time_s,
            events=events,
            expected_remaining_veh=int(binding.simulation.getMinExpectedNumber()),
        )

    def is_finished(self) -> bool:
        binding = self._require_open()
        # GOTCHA: SUMO does not stop at --end while a client is attached; the client owns
        # the clock. Without this check end_s would be recorded but never enforced.
        if float(binding.simulation.getTime()) >= float(binding.simulation.getEndTime()):
            return True
        # getMinExpectedNumber counts loaded-but-not-yet-departed vehicles too, so it
        # reaching zero is the correct drain condition, not an empty network.
        return int(binding.simulation.getMinExpectedNumber()) == 0

    def close(self) -> None:
        # A close that fails must still mark the connection unusable. libsumo allows one
        # simulation per process, so an object that goes on claiming to be open is a
        # worse problem than whatever made the close fail.
        try:
            if self._binding is not None and not self.is_closed:
                self._binding.close()
        finally:
            self.is_closed = True
