import ast
from pathlib import Path

from conftest import BINDING_MODULE, SRC_ROOT

BANNED_IN_ZONE_A = {"traci", "libsumo", "studies"}

# ARCH §13: SUMO's traffic-light lamp alphabet. A raw lamp string ("GGrrG") is a literal
# built purely from these characters. The signal safety layer (`control/`, arriving at M2)
# is the one place allowed to hold them; nothing in Zone A does yet, so this must find none.
LAMP_STATE_CHARS = frozenset("rygGsuoO")
SIGNAL_SAFETY_LAYER = SRC_ROOT / "control"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_only_the_binding_module_imports_the_simulator():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == BINDING_MODULE:
            continue
        banned = _imported_roots(path) & {"traci", "libsumo"}
        if banned:
            offenders.append(f"{path.relative_to(SRC_ROOT)}: {sorted(banned)}")
    assert not offenders, "ARCH-D02 violated: " + "; ".join(offenders)


def _raw_lamp_string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value) >= 3
        and set(node.value) <= LAMP_STATE_CHARS
    ]


def test_no_raw_lamp_strings_outside_the_signal_safety_layer():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if SIGNAL_SAFETY_LAYER in path.parents:
            continue
        literals = _raw_lamp_string_literals(path)
        if literals:
            offenders.append(f"{path.relative_to(SRC_ROOT)}: {literals}")
    assert not offenders, "ARCH §13 violated: " + "; ".join(offenders)


def test_lamp_string_detector_catches_a_deliberate_violation(tmp_path):
    # GOTCHA: a boundary test that cannot fail is worthless. This proves the detector works.
    offender = tmp_path / "offender.py"
    offender.write_text('STATE = "GGrrG"\n')
    assert _raw_lamp_string_literals(offender) == ["GGrrG"]


def test_zone_a_never_imports_zone_b():
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "studies" in _imported_roots(path)
    ]
    assert not offenders, "PD-D07 violated: " + "; ".join(offenders)


def test_zone_a_contains_no_study_conditionals():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text()
        if "study_name" in text or "STUDY_NAME" in text:
            offenders.append(str(path.relative_to(SRC_ROOT)))
    assert not offenders, "PD-D07 violated by study-specific branching: " + "; ".join(offenders)


def test_detector_catches_a_deliberate_violation(tmp_path):
    # GOTCHA: a boundary test that cannot fail is worthless. This proves the detector works.
    offender = tmp_path / "offender.py"
    offender.write_text("import traci\nfrom studies.one import thing\n")
    assert _imported_roots(offender) & BANNED_IN_ZONE_A == {"traci", "studies"}


def test_detector_ignores_relative_imports(tmp_path):
    # Relative imports cannot reach traci, libsumo, or studies from inside cadence, so
    # node.level == 0 is a deliberate filter rather than a gap.
    sibling = tmp_path / "sibling.py"
    sibling.write_text("from . import scenario\nfrom .sumo import binding\n")
    assert _imported_roots(sibling) == set()


GROUND_TRUTH_MODULE = "cadence.simulation.ground_truth"
# Every module permitted to name the privileged directory or import its types. Extending
# this list is a deliberate edit; a new entry appearing without one is the finding.
GROUND_TRUTH_ALLOWLIST = {
    "simulation/ground_truth.py",
    "simulation/sumo/extract.py",
    "simulation/sumo/connection.py",
    "simulation/artifacts.py",
    "cli.py",
}


def _imports_ground_truth(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "cadence.simulation.ground_truth"
        ):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.startswith(GROUND_TRUTH_MODULE) for alias in node.names
        ):
            return True
    return False


def test_nothing_outside_simulation_imports_ground_truth():
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if not str(path.relative_to(SRC_ROOT)).startswith("simulation/")
        and _imports_ground_truth(path)
    ]
    assert not offenders, "ST-D01 violated: " + "; ".join(offenders)


def test_the_ground_truth_allowlist_is_exactly_what_names_it():
    naming = {
        str(path.relative_to(SRC_ROOT))
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "ground_truth" in path.read_text()
    }
    assert naming == GROUND_TRUTH_ALLOWLIST, (
        "ST-D08: extending the privileged surface must be a deliberate edit. "
        f"unexpected: {sorted(naming - GROUND_TRUTH_ALLOWLIST)}; "
        f"missing: {sorted(GROUND_TRUTH_ALLOWLIST - naming)}"
    )


def test_only_the_sumo_package_imports_sumolib():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "sumo" in path.relative_to(SRC_ROOT).parts:
            continue
        if "sumolib" in _imported_roots(path):
            offenders.append(str(path.relative_to(SRC_ROOT)))
    assert not offenders, "ST-D12 violated: " + "; ".join(offenders)


def _relaxes_strictness(key: str, value: object) -> bool:
    # GOTCHA: `ignore_errors = true` disables mypy for the targeted modules entirely, the
    # same effect as the `disallow_untyped_defs = false` family has one flag at a time --
    # but it reads as `True`, not `False`, so a check that only looks for `value is False`
    # never sees it.
    if key == "ignore_errors":
        return value is True
    return value is False


def _relaxed_cadence_overrides(mypy_config: dict[str, object]) -> list[tuple[list[str], set[str]]]:
    violations = []
    for override in mypy_config.get("overrides", []):
        modules = override.get("module", [])
        targeted = [
            m
            for m in ([modules] if isinstance(modules, str) else modules)
            if m.startswith("cadence")
        ]
        relaxed = {
            key
            for key, value in override.items()
            if key != "module" and _relaxes_strictness(key, value)
        }
        if targeted and relaxed:
            violations.append((targeted, relaxed))
    return violations


def test_mypy_strictness_is_not_disabled_for_any_cadence_package():
    # ST-D02: the import ban and mypy --strict enforce this boundary together. Relaxing
    # strictness anywhere under src/cadence silently relaxes the boundary with it.
    import tomllib

    config = tomllib.loads((SRC_ROOT.parents[1] / "pyproject.toml").read_text())
    assert config["tool"]["mypy"]["strict"] is True
    violations = _relaxed_cadence_overrides(config["tool"]["mypy"])
    assert not violations, f"strictness relaxed: {violations}"


def test_the_strictness_guard_catches_ignore_errors_true():
    # Verified against the tree before this test existed: an override of
    # module = ["cadence.*"] with ignore_errors = true left the guard above green.
    fabricated = {"overrides": [{"module": ["cadence.*"], "ignore_errors": True}]}
    violations = _relaxed_cadence_overrides(fabricated)
    assert violations == [(["cadence.*"], {"ignore_errors"})]
