"""Simulator binding selection.

The only module in CADENCE permitted to import traci or libsumo (ARCH-D02). Both expose
the same call surface for the subset the harness uses, so the choice is a configuration
value rather than a code path.

libsumo runs in-process and is materially faster, but supports no GUI and only one
simulation per process. TraCI is the binding for inspection and for anything needing more
than one connection.
"""

from __future__ import annotations

import functools
import importlib.metadata
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import cast


class BindingKind(StrEnum):
    TRACI = "traci"
    LIBSUMO = "libsumo"


def _import_sumo_package() -> ModuleType:
    # GOTCHA: importing `sumo` is what sets SUMO_HOME, which traci and libsumo need. sumolib
    # tolerates SUMO_HOME being unset, but `import sumo` first is the convention everywhere
    # in this codebase for consistency.
    import sumo

    return cast(ModuleType, sumo)


def sumo_home() -> Path:
    return Path(_import_sumo_package().SUMO_HOME)


def sumo_version() -> str:
    # GOTCHA: sumo.__version__ is always "0.0.0". The package resolves its own version
    # under the name "sumo" while the distribution is "eclipse-sumo", and swallows the
    # PackageNotFoundError that results.
    return importlib.metadata.version("eclipse-sumo")


@functools.lru_cache(maxsize=len(BindingKind))
def load_binding(kind: BindingKind) -> ModuleType:
    _import_sumo_package()
    if kind is BindingKind.LIBSUMO:
        import libsumo

        return cast(ModuleType, libsumo)
    import traci

    return cast(ModuleType, traci)
