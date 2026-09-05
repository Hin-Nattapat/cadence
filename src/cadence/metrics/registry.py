"""cadence.metrics.registry — the contract every metric declaration must satisfy.

CONTRACT: a metric is declared with `register` immediately beside the function that
computes it, never in a list kept apart from the code — that separation is exactly the
drift CLAUDE.md §7 asks the registry to prevent. `register` is a decorator so declaring a
metric with no computing function, or vice versa, is not an expressible mistake: the two
lines cannot exist independently of each other.

The privileged partition of the run directory is off limits to every module in this
package, enforced by an architecture test elsewhere.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])
# `registry` is this module itself -- importing it again through the walk below is a no-op
# at best, and the one module in the package that cannot be scanned for its own side effects.
_MECHANISM_MODULE_NAMES = frozenset({"registry"})


class QuantityKind(StrEnum):
    """ST-D28: a level that decays (STOCK) is never summed across steps as if it were an
    accrual (FLOW). The unit already carries the answer; this field states it explicitly
    so a metric's own registry entry is what a reviewer checks, not the unit suffix alone.
    """

    STOCK = "stock"
    FLOW = "flow"


class Population(StrEnum):
    """ST-D25: which bucket of spec §3 a metric is computed over. "Mean waiting time" is
    not a metric; "mean waiting time per completed trip" is, and per departed vehicle is a
    different number that can pick a different winner.
    """

    COMPLETED_TRIPS = "completed_trips"
    UNFINISHED_TRIPS = "unfinished_trips"
    DEPARTED_VEHICLES = "departed_vehicles"
    DUE_VEHICLES = "due_vehicles"
    LANE_STEPS = "lane_steps"
    RUN = "run"


# ST-D29: populations that are proper subsets of true demand can silently exclude spec
# §3.3's unnamed bucket from their denominator; DUE_VEHICLES, LANE_STEPS and RUN cannot.
POPULATIONS_MISSING_THE_UNNAMED_BUCKET: frozenset[Population] = frozenset(
    {Population.COMPLETED_TRIPS, Population.UNFINISHED_TRIPS, Population.DEPARTED_VEHICLES}
)


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: str
    version: int
    definition: str
    unit: str
    population: Population
    quantity_kind: QuantityKind
    input_fields: tuple[str, ...]
    aggregation: str
    limitations: tuple[str, ...]
    # Empty on every M1b entry (spec §6.2): CLAUDE.md §4 pushes interpretation into the
    # name and the version, leaving nothing here to discriminate two metrics with. Declared
    # so M8's turn-ratio window and prior weight need no schema change when they arrive.
    config_dependencies: Mapping[str, object]
    # None on every M1b entry (spec §6.2): thresholds arrive with spillback and gridlock
    # at M8. Declared now so that milestone needs no schema change either.
    thresholds: Mapping[str, float] | None

    def __post_init__(self) -> None:
        if not self.name.endswith(f"_v{self.version}"):
            raise ValueError(
                f"metric {self.name!r}: name must end with _v{self.version} to match "
                f"version={self.version} -- version and the name's _v suffix are one fact, "
                "not two (CLAUDE.md §4)"
            )
        if self.population in POPULATIONS_MISSING_THE_UNNAMED_BUCKET and not self.limitations:
            raise ValueError(
                f"metric {self.name!r}: population {self.population} excludes spec §3.3's "
                "never-inserted bucket from its denominator without saying so -- "
                "limitations must state it (ST-D29)"
            )


_DEFINITIONS: dict[str, MetricDefinition] = {}


def register(definition: MetricDefinition) -> Callable[[F], F]:
    """Declare `definition` beside the function that computes it.

    Raises ValueError if `definition.name` is already registered: a metric definition is
    immutable (CLAUDE.md §4) and a changed interpretation gets a new name ending `_v2`,
    never an edit in place.
    """

    def decorator(func: F) -> F:
        if definition.name in _DEFINITIONS:
            raise ValueError(f"metric {definition.name!r} is already registered")
        _DEFINITIONS[definition.name] = definition
        return func

    return decorator


def _import_every_metric_module() -> None:
    """Import every module under `cadence.metrics`, so a module's `register` calls have run
    before anything inspects `_DEFINITIONS` -- regardless of which of them the caller already
    happened to import. Without this, the same-set check in `test_registry.py` would depend
    on pytest's import order rather than on what is actually declared.
    """
    assert __package__ is not None  # this module is always imported as part of a package
    package = importlib.import_module(__package__)
    for module_info in pkgutil.iter_modules(package.__path__, f"{package.__name__}."):
        if module_info.name.rsplit(".", maxsplit=1)[-1] in _MECHANISM_MODULE_NAMES:
            continue
        importlib.import_module(module_info.name)


def registered_metrics() -> Mapping[str, MetricDefinition]:
    """Every metric declared anywhere in `cadence.metrics`, keyed by name.

    CONTRACT: imports every module in the package first (see `_import_every_metric_module`),
    so the result does not depend on what the caller already imported.
    """
    _import_every_metric_module()
    return MappingProxyType(_DEFINITIONS)
