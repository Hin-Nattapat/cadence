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
