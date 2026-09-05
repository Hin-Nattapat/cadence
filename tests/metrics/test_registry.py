import ast
import dataclasses
import importlib
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

import cadence.metrics as metrics_package
from cadence.metrics import registry
from cadence.metrics.registry import MetricDefinition, Population, QuantityKind
from conftest import METRICS_ROOT

# Files that declare the mechanism itself rather than a metric -- excluded from both sides
# of the same-set comparison below.
_MECHANISM_FILES = {"registry.py", "__init__.py"}

# A metric-registering module planted only under a monkeypatched package __path__, never
# imported by this test file itself -- see test_registered_metrics_discovers_a_module_this_
# test_never_imports below.
_PLANTED_METRIC_MODULE = """\
from types import MappingProxyType

from cadence.metrics.registry import MetricDefinition, Population, QuantityKind, register


@register(
    MetricDefinition(
        name="planted_metric_v1",
        version=1,
        definition="planted to prove the import walk, not this test, discovers it",
        unit="s",
        population=Population.RUN,
        quantity_kind=QuantityKind.FLOW,
        input_fields=("example_field",),
        aggregation="sum",
        limitations=(),
        config_dependencies=MappingProxyType({}),
        thresholds=None,
    )
)
def compute_planted_metric_v1():
    return 1
"""


def _definition_kwargs(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "name": "example_metric_v1",
        "version": 1,
        "definition": "an example metric, used only by this test file",
        "unit": "s",
        "population": Population.RUN,
        "quantity_kind": QuantityKind.FLOW,
        "input_fields": ("example_field",),
        "aggregation": "sum",
        "limitations": (),
        "config_dependencies": MappingProxyType({}),
        "thresholds": None,
    }
    fields.update(overrides)
    return fields


def _definition(**overrides: object) -> MetricDefinition:
    return MetricDefinition(**_definition_kwargs(**overrides))


def test_metric_definition_is_frozen():
    definition = _definition()
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.name = "renamed"  # type: ignore[misc]


def test_population_is_required():
    fields = _definition_kwargs()
    del fields["population"]
    with pytest.raises(TypeError):
        MetricDefinition(**fields)


def test_quantity_kind_is_required():
    fields = _definition_kwargs()
    del fields["quantity_kind"]
    with pytest.raises(TypeError):
        MetricDefinition(**fields)


def test_name_must_end_with_the_version_suffix():
    # CLAUDE.md §4: version and the name's _v suffix are one fact, not two independently
    # settable fields.
    fields = _definition_kwargs(name="example_metric_v1", version=2)
    with pytest.raises(ValueError, match="_v2"):
        MetricDefinition(**fields)


@pytest.mark.parametrize("population", list(Population))
def test_limitations_required_exactly_where_the_unnamed_bucket_could_belong(population):
    # ST-D29: the requirement is structural, keyed off population, not a per-metric choice.
    if population in registry.POPULATIONS_MISSING_THE_UNNAMED_BUCKET:
        with pytest.raises(ValueError, match="limitations"):
            _definition(population=population, limitations=())
        _definition(population=population, limitations=("excludes X",))
    else:
        _definition(population=population, limitations=())


def test_every_population_is_accounted_for_by_the_unnamed_bucket_exemption():
    # ST-D29: a new Population member must land on one side of this line deliberately, not
    # silently in the exempt branch above.
    assert set(Population) == registry.POPULATIONS_MISSING_THE_UNNAMED_BUCKET | {
        Population.DUE_VEHICLES,
        Population.LANE_STEPS,
        Population.RUN,
    }


def test_register_adds_a_definition_beside_its_function(monkeypatch):
    monkeypatch.setattr(registry, "_DEFINITIONS", {})
    definition = _definition(name="scratch_metric_v1")

    @registry.register(definition)
    def compute_scratch_metric_v1():
        return 42

    assert registry.registered_metrics()["scratch_metric_v1"] is definition
    assert compute_scratch_metric_v1() == 42


def test_register_refuses_a_second_definition_under_the_same_name(monkeypatch):
    monkeypatch.setattr(registry, "_DEFINITIONS", {})
    registry.register(_definition(name="scratch_metric_v1"))(lambda: None)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_definition(name="scratch_metric_v1"))(lambda: None)


def test_registered_metrics_discovers_a_module_this_test_never_imports(monkeypatch, tmp_path):
    # Item 1: the same-set check must not depend on which cadence.metrics submodules the
    # pytest session happened to import already. Plant a metric-registering module where only
    # registry.py's own pkgutil walk -- not this test, and nothing else in the suite -- can
    # reach it, and show registered_metrics() finds it anyway.
    monkeypatch.setattr(registry, "_DEFINITIONS", {})
    (tmp_path / "planted_metric.py").write_text(_PLANTED_METRIC_MODULE)
    monkeypatch.setattr(metrics_package, "__path__", [*metrics_package.__path__, str(tmp_path)])
    monkeypatch.delitem(sys.modules, "cadence.metrics.planted_metric", raising=False)
    importlib.invalidate_caches()

    assert "planted_metric_v1" not in registry._DEFINITIONS

    assert "planted_metric_v1" in registry.registered_metrics()

    monkeypatch.delitem(sys.modules, "cadence.metrics.planted_metric", raising=False)


def _compute_function_names(path: Path) -> set[str]:
    # CONTRACT: a module under cadence.metrics that computes a metric names its function
    # compute_<metric name> -- a convention independent of the register() call itself, so
    # this scan and the live registry can disagree if one is edited without the other.
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.name.removeprefix("compute_")
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("compute_")
    }


def _emitted_metric_names(root: Path) -> frozenset[str]:
    names: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if path.name in _MECHANISM_FILES:
            continue
        names |= _compute_function_names(path)
    return frozenset(names)


def _declared_metric_names() -> frozenset[str]:
    return frozenset(registry.registered_metrics())


def test_declared_and_emitted_metrics_are_the_same_set_in_both_directions():
    # Either direction alone would pass a subset check while a metric quietly stopped being
    # emitted, or a compute_ function appeared with no registration -- both are checked.
    paths = sorted(METRICS_ROOT.rglob("*.py"))
    assert paths, f"{METRICS_ROOT} matched no files"
    declared = _declared_metric_names()
    emitted = _emitted_metric_names(METRICS_ROOT)
    assert declared == emitted, (
        f"registered but no compute_ function: {sorted(declared - emitted)}; "
        f"a compute_ function with no registration: {sorted(emitted - declared)}"
    )


def test_no_metric_is_declared_yet():
    # Documents the state this task leaves the package in, per its own brief.
    assert registry.registered_metrics() == {}


def test_emitted_detector_finds_a_compute_function(tmp_path):
    # GOTCHA: a same-set test that cannot fail is worthless (the pattern test_architecture.py
    # uses for its own detectors). Prove this one actually distinguishes the two sides.
    (tmp_path / "helper.py").write_text("def _not_a_metric():\n    pass\n")
    (tmp_path / "trip.py").write_text("def compute_travel_time_mean_s():\n    pass\n")
    assert _emitted_metric_names(tmp_path) == {"travel_time_mean_s"}


def test_emitted_detector_ignores_the_mechanism_files(tmp_path):
    (tmp_path / "registry.py").write_text("def compute_should_be_ignored():\n    pass\n")
    (tmp_path / "__init__.py").write_text("def compute_also_ignored():\n    pass\n")
    assert _emitted_metric_names(tmp_path) == set()
