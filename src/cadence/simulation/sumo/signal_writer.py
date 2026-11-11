"""The one place a light is changed in SUMO (SIG-D04).

Applies commands in the order given and never reorders them; the executor owns the order,
`SetPhase` before `SetRemainingDuration_s` within a tick. It passes phase indices and
seconds only, never a lamp string (ST-D04).
"""

from __future__ import annotations

from collections.abc import Iterable
from types import ModuleType
from typing import assert_never

from cadence.control.executor import SetPhase, SetRemainingDuration_s, SignalCommand


def apply_signal_commands(binding: ModuleType, commands: Iterable[SignalCommand]) -> None:
    for command in commands:
        match command:
            case SetPhase():
                binding.trafficlight.setPhase(str(command.intersection_id), command.phase_index)
            case SetRemainingDuration_s():
                binding.trafficlight.setPhaseDuration(
                    str(command.intersection_id), command.remaining_s
                )
            case _:
                assert_never(command)
