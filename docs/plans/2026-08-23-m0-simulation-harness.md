# CADENCE M-1 + M0 — Bootstrap and Simulation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the CADENCE toolchain and a deterministic SUMO simulation harness that
can load a versioned scenario, run it reproducibly, capture raw state and events, and shut
down cleanly — with the project's architectural rules enforced as tests from the first
commit.

**Architecture:** A single module owns the simulator binding; nothing else may import
`traci` or `libsumo`, and that rule is a lint error and a test rather than a convention.
Scenario definitions are immutable YAML validated by Pydantic and content-hashed. A
`SumoConnection` context manager owns the process lifecycle and yields one frozen
`SimulationStepResult` per step. Every run writes a manifest containing everything needed
to reproduce it.

**Tech Stack:** Python 3.12 · uv · Eclipse SUMO 1.27.1 (from PyPI) · TraCI / libsumo ·
Pydantic v2 · Polars · Typer · pytest · hypothesis · ruff · mypy

**Spec:** `docs/specs/2026-08-22-project-direction.md`

## Global Constraints

Copied verbatim from the spec. Every task's requirements implicitly include these.

- Python **3.12** exactly (`>=3.12,<3.13`). `libsumo` publishes a `cp312` macOS arm64 wheel.
- SUMO pinned at **1.27.1** across `eclipse-sumo`, `traci`, `libsumo`, `sumolib`.
- `mypy --strict` passes on `src` and `tools`. Zone B (`studies/`) is exempt.
- Every physical quantity carries a unit suffix: `_m`, `_s`, `_mps`, `_mps2`, `_veh`,
  `_vehph`, `_ratio`, `_pct`.
- Every identifier kind is a distinct `NewType`.
- Every numeric constant carries a PROVENANCE comment. No exceptions.
- Comments default to none; each must be PROVENANCE, GOTCHA, DECISION, or CONTRACT.
  No `Args:` / `Returns:` blocks.
- No `traci` / `libsumo` import outside `src/cadence/simulation/sumo/binding.py`.
- No `import studies.*` anywhere in `src/`.
- No wall-clock, unseeded randomness, or dict-ordering dependence in Zone A. The single
  exception is the run manifest's `started_at_utc` / `finished_at_utc`, which are
  provenance only and are excluded from every reproducibility comparison.
- Code, comments, commits, and documents in English.
- Milestone discipline: **no RL, no Max-Pressure, no MPC, no controller logic in this plan.**
  M0 has no intelligence in it at all.

## Verified Environment Facts

Established by inspecting the published wheels on 2026-08-23. Do not re-derive.

- `eclipse-sumo` installs a Python package named `sumo`. Importing it sets
  `os.environ["SUMO_HOME"]` to the package directory as a side effect. **This is why
  `import sumo` must happen before `import traci` or `import sumolib`.**
- Binaries live at `<sumo.SUMO_HOME>/bin/{sumo,sumo-gui,netconvert,netgenerate,duarouter}`
  and are also exposed as console scripts on the virtualenv `PATH`.
- **`sumo.__version__` is NOT usable.** The package's `__init__.py` calls
  `importlib.metadata.version(__name__)` — that is `version("sumo")`, but the distribution
  is named `eclipse-sumo`, so it raises `PackageNotFoundError`, which subclasses
  `ImportError` and is swallowed by the package's own `except ImportError`, leaving the
  hardcoded fallback `"0.0.0"`. Read the version with
  `importlib.metadata.version("eclipse-sumo")` instead.
- `traci.start(cmd, port=None, numRetries=..., label="default", verbose=False, ...)` where
  `cmd` is a Popen-style list; the port option is appended automatically.
- `libsumo` mirrors that surface: `start`, `simulationStep`, `close`, and domain classes
  `simulation`, `lane`, `edge`, `trafficlight`, `vehicle`, `junction`, `lanearea`,
  `inductionloop`. It re-exports `traci.constants` and `traci.exceptions`.
- `traci.simulation` provides `getTime`, `getDepartedIDList`, `getArrivedIDList`,
  `getStartingTeleportIDList`, `getEndingTeleportIDList`, `getCollidingVehiclesIDList`,
  `getMinExpectedNumber`, `getLoadedNumber`.
- **libsumo limitation:** no GUI, and one simulation per process. TraCI is the binding for
  inspection and for any parallel-connection work.

---

# File Structure

```
pyproject.toml                            project, dependencies, ruff, mypy, pytest config
uv.lock                                   locked dependency graph, includes SUMO 1.27.1
.python-version                           3.12
Makefile                                  make check is the single gate
.pre-commit-config.yaml

src/cadence/
  __init__.py                             version string only
  types.py                                NewType identifiers shared across the platform
  simulation/
    __init__.py
    scenario.py                           ScenarioConfig model, loader, content hashing
    events.py                             SimulationEvent, EventKind, EventLog
    manifest.py                           RunManifest model and construction
    validation.py                         scenario network validation
    sumo/
      __init__.py
      binding.py                          ONLY module allowed to import traci / libsumo
      command.py                          builds the SUMO argv from a ScenarioConfig
      connection.py                       SumoConnection lifecycle and stepping
  cli.py                                  Typer app: run, validate-scenario

tools/
  check_decisions.py                      PD-D06 layers 1 and 3
  build_s0_scenario.py                    generates the S0 network and demand

scenarios/s0_single_intersection/v1/
  scenario.yaml
  network.net.xml                         generated, committed
  demand.rou.xml                          generated, committed

tests/
  conftest.py                             shared fixtures
  test_toolchain.py                       pins the environment
  test_architecture.py                    Zone and dependency boundaries as tests
  test_decisions_registry.py              exercises tools/check_decisions.py
  simulation/
    test_scenario.py
    test_events.py
    test_manifest.py
    test_validation.py
    sumo/
      test_binding.py
      test_command.py
      test_connection.py                  SUMO integration
      test_reproducibility.py             SUMO integration
```

`tools/` sits outside `src/cadence/` deliberately: the documentation checker and the
scenario generator are project infrastructure, not traffic-domain code, and Zone A should
not grow a module that has nothing to do with traffic.

---

# Task 1: Bootstrap the toolchain and pin the environment

**Files:**
- Create: `.python-version`, `pyproject.toml`, `Makefile`, `src/cadence/__init__.py`
- Create: `tests/test_toolchain.py`

**Interfaces:**
- Consumes: nothing
- Produces: a working `uv` project; `make check`; `cadence.__version__: str`

- [ ] **Step 1: Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l
uv --version
```

- [ ] **Step 2: Pin the Python version**

```bash
cd /Users/calypso/Project/Ottery/cadence
echo "3.12" > .python-version
uv python install 3.12
```

- [ ] **Step 3: Write pyproject.toml**

```toml
[project]
name = "cadence"
version = "0.0.0"
description = "A controller-agnostic platform for network-aware adaptive traffic signal control"
requires-python = ">=3.12,<3.13"
dependencies = [
    "eclipse-sumo==1.27.1",
    "traci==1.27.1",
    "libsumo==1.27.1",
    "sumolib==1.27.1",
    "pydantic>=2.9",
    "pyyaml>=6.0",
    "polars>=1.0",
    "typer>=0.12",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "hypothesis>=6.100",
    "mypy>=1.11",
    "ruff>=0.6",
    "types-PyYAML",
    "pre-commit",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cadence"]

[tool.ruff]
line-length = 100
src = ["src", "tests", "tools"]
# ruff 0.16 lints and formats Python fences inside Markdown. Every Markdown file in this
# repository is documentation, and its code is illustrative — deliberately not always
# import-clean. Exclude the format rather than enumerating directories.
extend-exclude = ["*.md"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "TID", "ANN", "RUF"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"traci".msg = "Import the simulator binding through cadence.simulation.sumo.binding (ARCH-D02)."
"libsumo".msg = "Import the simulator binding through cadence.simulation.sumo.binding (ARCH-D02)."
"studies".msg = "Zone A must not import Zone B (PD-D07)."

[tool.ruff.lint.per-file-ignores]
"src/cadence/simulation/sumo/binding.py" = ["TID251"]
"tests/**" = ["ANN", "TID251"]
"tools/**" = ["TID251"]

[tool.mypy]
python_version = "3.12"
strict = true
# tools/ joins this list in Task 3, which supplies its first module. mypy hard-errors on
# a directory holding zero .py files, so naming it earlier breaks `make type`.
files = ["src"]

[[tool.mypy.overrides]]
module = ["traci.*", "libsumo.*", "sumolib.*", "sumo", "polars.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = [
    "sumo: starts a real SUMO process; slower than a unit test",
]
```

- [ ] **Step 4: Create the package entry point**

`src/cadence/__init__.py`:

```python
"""CADENCE — a controller-agnostic traffic signal control experimentation platform."""

__version__ = "0.0.0"
```

- [ ] **Step 5: Write the Makefile**

Use real tab characters for recipe indentation.

```make
.PHONY: check lint format type test docs-check install

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy

docs-check:
	uv run python tools/check_decisions.py

test:
	uv run pytest

check: lint type docs-check test
```

- [ ] **Step 6: Resolve the dependency graph**

```bash
uv sync
uv run python -c "import sumo; print(sumo.__version__, sumo.SUMO_HOME)"
```

Expected: `1.27.1` followed by a path ending in `/site-packages/sumo`.

- [ ] **Step 7: Write the failing toolchain test**

`tests/test_toolchain.py`:

```python
import subprocess
import sys
from pathlib import Path

EXPECTED_SUMO_VERSION = "1.27.1"


def test_python_is_3_12():
    assert sys.version_info[:2] == (3, 12)


def test_sumo_version_is_pinned():
    import importlib.metadata

    # GOTCHA: sumo.__version__ is always "0.0.0" — the package looks itself up under the
    # wrong distribution name and swallows the resulting PackageNotFoundError.
    assert importlib.metadata.version("eclipse-sumo") == EXPECTED_SUMO_VERSION


def test_importing_sumo_sets_sumo_home():
    import os

    import sumo

    assert os.environ["SUMO_HOME"] == sumo.SUMO_HOME


def test_sumo_binary_is_executable():
    import sumo

    binary = Path(sumo.SUMO_HOME) / "bin" / "sumo"
    assert binary.is_file()
    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert EXPECTED_SUMO_VERSION in result.stdout


def test_netgenerate_binary_is_executable():
    import sumo

    binary = Path(sumo.SUMO_HOME) / "bin" / "netgenerate"
    assert binary.is_file()
```

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_toolchain.py -v`
Expected: 5 passed. If `test_sumo_version_is_pinned` fails, `uv.lock` did not pin 1.27.1 —
fix the constraint rather than the test.

- [ ] **Step 9: Confirm the lockfile is tracked**

`.gitignore` already covers `.venv/`, `__pycache__/`, and the tool caches. `uv.lock` must
be committed — it is what pins SUMO 1.27.1 for anyone who clones the repository.

```bash
git check-ignore -v uv.lock || echo "uv.lock will be committed (correct)"
```

- [ ] **Step 10: Commit**

```bash
git add .python-version pyproject.toml uv.lock Makefile .gitignore src/cadence/__init__.py tests/test_toolchain.py
git commit -m "build: bootstrap uv toolchain with SUMO 1.27.1 pinned (PD-D03)"
```

---

# Task 2: Enforce the architecture boundaries as tests

**Files:**
- Create: `tests/test_architecture.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: `src/cadence/` package layout from Task 1
- Produces: module constants `SRC_ROOT: Path` and `BINDING_MODULE: Path` in
  `tests/conftest.py`, imported directly (`from conftest import SRC_ROOT`) rather than
  injected as fixtures

The rules in `CLAUDE.md` §3 become executable here. Ruff `TID251` catches violations while
typing; this catches them in CI and covers rules ruff cannot express.

- [ ] **Step 1: Write conftest with the source-scanning helper**

`tests/conftest.py`:

```python
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "cadence"

# The single module permitted to import the simulator bindings (ARCH-D02).
BINDING_MODULE = SRC_ROOT / "simulation" / "sumo" / "binding.py"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


```

- [ ] **Step 2: Write the failing architecture test**

`tests/test_architecture.py`:

```python
import ast
from pathlib import Path

from conftest import BINDING_MODULE, SRC_ROOT

BANNED_IN_ZONE_A = {"traci", "libsumo", "studies"}


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
```

- [ ] **Step 3: Make the conftest import explicit**

Add to `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
pythonpath = ["tests"]
```

pytest usually puts the tests directory on `sys.path` on its own, but relying on that is
fragile. Declaring it makes `from conftest import ...` work regardless of layout changes.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: 4 passed.

This is a test-only task, so there is no red phase in the usual sense: with a single file
in `src/cadence/`, the first three assertions hold vacuously. Step 5 supplies the red phase.

- [ ] **Step 5: Prove the tests are not vacuous**

```bash
printf 'import traci\nfrom studies.one import thing\nstudy_name = "x"\n' >> src/cadence/__init__.py
uv run pytest tests/test_architecture.py -q ; echo "pytest exit: $?"
git checkout src/cadence/__init__.py
uv run pytest tests/test_architecture.py -q ; echo "pytest exit: $?"
```

Expected: the first run fails with three failures naming `ARCH-D02` and `PD-D07`; the
second passes. If the first run passes, the detector is broken — fix it before continuing.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_architecture.py pyproject.toml
git commit -m "test: enforce ARCH-D02 and PD-D07 zone boundaries as tests"
```

---

# Task 3: Documentation consistency checker

**Files:**
- Create: `tools/check_decisions.py`
- Create: `tests/test_decisions_registry.py`

**Interfaces:**
- Consumes: `research/decisions.yaml`
- Produces: `load_registry(path) -> dict[str, Decision]`, `check(repo_root) -> list[str]`,
  `Decision` dataclass with `id`, `statement`, `source`, `status`

Implements PD-D06 layers 1 and 3. Layer 2 (section hashing) is M1 and is deliberately absent.

- [ ] **Step 1: Write the failing test**

`tests/test_decisions_registry.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from check_decisions import check, load_registry

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_registry_loads_every_entry():
    registry = load_registry(REPO_ROOT / "research" / "decisions.yaml")
    assert len(registry) >= 77  # 77 at M0; SIM-D entries are added during this milestone
    assert registry["ARCH-D02"].status == "adopted"
    assert "TraCI" in registry["ARCH-D02"].statement


def test_repository_passes_its_own_check():
    assert check(REPO_ROOT) == []


def test_check_reports_an_id_missing_from_its_source(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D01:\n'
        '  statement: "A statement."\n'
        '  source:    ghost.md\n'
        '  status:    adopted\n'
    )
    (tmp_path / "research" / "ghost.md").write_text("This file never mentions the id.\n")
    problems = check(tmp_path)
    assert any("XX-D01" in p and "not found in source" in p for p in problems)


def test_check_reports_a_missing_source_file(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D02:\n'
        '  statement: "A statement."\n'
        '  source:    does_not_exist.md\n'
        '  status:    adopted\n'
    )
    problems = check(tmp_path)
    assert any("XX-D02" in p and "source file missing" in p for p in problems)


def test_check_reports_code_depending_on_a_superseded_decision(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D03:\n'
        '  statement: "An old statement."\n'
        '  source:    old.md\n'
        '  status:    superseded\n'
    )
    (tmp_path / "research" / "old.md").write_text("XX-D03 lives here.\n")
    (tmp_path / "src" / "thing.py").write_text("# implements XX-D03\nx = 1\n")
    problems = check(tmp_path)
    assert any("XX-D03" in p and "superseded" in p for p in problems)


def test_check_reports_a_code_reference_to_an_unknown_id(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D04:\n'
        '  statement: "A statement."\n'
        '  source:    real.md\n'
        '  status:    adopted\n'
    )
    (tmp_path / "research" / "real.md").write_text("XX-D04 lives here.\n")
    (tmp_path / "src" / "thing.py").write_text("# see XX-D99\ny = 2\n")
    problems = check(tmp_path)
    assert any("XX-D99" in p and "not in the registry" in p for p in problems)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_decisions_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_decisions'`.

- [ ] **Step 3: Implement the checker**

`tools/check_decisions.py`:

```python
"""Documentation consistency checker — PD-D06 layers 1 and 3.

Validates that every decision identifier resolves to its source document, that no code
depends on a superseded or retracted decision, and that no code cites an identifier the
registry does not know. Layer 2 (section content hashing) arrives at M1.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Identifier grammar shared by the research corpus: PREFIX-Dnn, PREFIX-Hnn, PREFIX-Qnn.
ID_PATTERN = re.compile(r"\b([A-Z]{2,4}-[DHQ]\d{2})\b")

DEPENDABLE_STATUSES = frozenset({"adopted", "hypothesis", "deferred"})
# tests/ is deliberately excluded: the checker's own tests contain fabricated ids.
SCANNED_DIRECTORIES = ("src", "tools")


@dataclass(frozen=True)
class Decision:
    id: str
    statement: str
    source: str
    status: str


def load_registry(path: Path) -> dict[str, Decision]:
    raw = yaml.safe_load(path.read_text()) or {}
    return {
        key: Decision(
            id=key,
            statement=value["statement"],
            source=value["source"],
            status=value["status"],
        )
        for key, value in raw.items()
    }


def _resolve_source(registry_path: Path, source: str) -> Path:
    return (registry_path.parent / source).resolve()


def check(repo_root: Path) -> list[str]:
    registry_path = repo_root / "research" / "decisions.yaml"
    registry = load_registry(registry_path)
    problems: list[str] = []

    for decision in registry.values():
        source_path = _resolve_source(registry_path, decision.source)
        if not source_path.is_file():
            problems.append(f"{decision.id}: source file missing — {decision.source}")
            continue
        if decision.id not in source_path.read_text():
            problems.append(f"{decision.id}: not found in source — {decision.source}")

    for directory in SCANNED_DIRECTORIES:
        root = repo_root / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            for cited in sorted(set(ID_PATTERN.findall(path.read_text()))):
                location = path.relative_to(repo_root)
                if cited not in registry:
                    problems.append(f"{location}: cites {cited}, which is not in the registry")
                elif registry[cited].status not in DEPENDABLE_STATUSES:
                    problems.append(
                        f"{location}: depends on {cited}, which is {registry[cited].status}"
                    )

    return problems


def main() -> int:
    problems = check(Path(__file__).resolve().parents[1])
    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} documentation consistency problem(s).")
        return 1
    print("Documentation consistency: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_decisions_registry.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the checker against the real repository**

Run: `uv run python tools/check_decisions.py`
Expected: `Documentation consistency: OK`

- [ ] **Step 6: Bring tools/ under mypy**

`tools/` now holds its first module, so add it to the type-check surface. In
`pyproject.toml`, change:

```toml
files = ["src"]
```

to:

```toml
files = ["src", "tools"]
```

and delete the comment above it explaining why `tools` was absent.

Run: `make type`
Expected: `Success: no issues found in 2 source files`

- [ ] **Step 7: Commit**

```bash
git add tools/check_decisions.py tests/test_decisions_registry.py pyproject.toml
git commit -m "feat(tools): add decision registry checker (PD-D06 layers 1 and 3)"
```

---

# Task 4: Core identifier types

**Files:**
- Create: `src/cadence/types.py`
- Create: `src/cadence/py.typed`
- Create: `tests/test_types.py`

**Interfaces:**
- Consumes: nothing
- Produces: `LaneId`, `EdgeId`, `JunctionId`, `IntersectionId`, `MovementId`, `PhaseId`,
  `VehicleId`, `ScenarioId`, `ControllerId`, `Seed` — all `NewType`

Only the identifiers M0 actually uses are defined plus the ones M1 will immediately need,
so that the naming is settled once rather than twice.

- [ ] **Step 1: Write the failing test**

`tests/test_types.py`:

```python
import subprocess
import sys
from pathlib import Path

from cadence.types import EdgeId, LaneId, ScenarioId, Seed

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_newtypes_are_transparent_at_runtime():
    lane = LaneId("e1_0")
    assert lane == "e1_0"
    assert isinstance(lane, str)


def test_seed_is_an_int_newtype():
    assert Seed(7) == 7


def test_mypy_rejects_passing_an_edge_id_where_a_lane_id_is_required(tmp_path):
    # This is the whole point of R2: "e1" and "e1_0" are both str in SUMO.
    snippet = tmp_path / "snippet.py"
    snippet.write_text(
        "from cadence.types import EdgeId, LaneId\n"
        "def takes_lane(lane: LaneId) -> None: ...\n"
        "takes_lane(EdgeId('e1'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(snippet)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "Argument 1" in result.stdout


def test_scenario_and_edge_ids_exist():
    assert ScenarioId("s0_single_intersection") == "s0_single_intersection"
    assert EdgeId("e1") == "e1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.types'`.

- [ ] **Step 3: Mark the package as typed**

Without a PEP 561 marker, mypy refuses to read type information from `cadence` when it is
imported from outside the package tree, and reports `import-untyped` instead of the
argument-type error Step 1's test asserts. The marker is correct regardless: CADENCE is a
typed library and `studies/` will consume it.

```bash
touch src/cadence/py.typed
```

Verify the marker is packaged — hatchling includes non-Python files inside the package
directory automatically:

```bash
uv sync && uv run python -c "import cadence, pathlib; print((pathlib.Path(cadence.__file__).parent / 'py.typed').is_file())"
```

Expected: `True`

- [ ] **Step 4: Implement the types**

`src/cadence/types.py`:

```python
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
MovementId = NewType("MovementId", str)
PhaseId = NewType("PhaseId", int)
VehicleId = NewType("VehicleId", str)
ScenarioId = NewType("ScenarioId", str)
ControllerId = NewType("ControllerId", str)
Seed = NewType("Seed", int)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_types.py -v`
Expected: 4 passed. The mypy test should report
`Argument 1 to "takes_lane" has incompatible type "EdgeId"; expected "LaneId"`.

- [ ] **Step 6: Commit**

```bash
git add src/cadence/types.py src/cadence/py.typed tests/test_types.py
git commit -m "feat(types): add distinct identifier NewTypes (PD-D04 R2)"
```

---

# Task 5: Scenario configuration, validation, and hashing

**Files:**
- Create: `src/cadence/simulation/__init__.py`, `src/cadence/simulation/scenario.py`
- Create: `tests/simulation/test_scenario.py`

**Interfaces:**
- Consumes: `cadence.types.ScenarioId`
- Produces:
  - `ScenarioConfig` (frozen Pydantic model) with fields `scenario_id: ScenarioId`,
    `scenario_version: int`, `description: str`, `network_file: str`, `demand_file: str`,
    `begin_s: float`, `end_s: float`, `step_length_s: float`, `time_to_teleport_s: float`,
    `default_seed: int`
  - `ScenarioPaths` with `root: Path`, `network: Path`, `demand: Path`
  - `load_scenario(root: Path) -> tuple[ScenarioConfig, ScenarioPaths]`
  - `sha256_file(path: Path) -> str`
  - `config_digest(config: ScenarioConfig) -> str`

- [ ] **Step 1: Write the failing test**

`tests/simulation/test_scenario.py`:

```python
import pytest
from pydantic import ValidationError

from cadence.simulation.scenario import (
    ScenarioConfig,
    config_digest,
    load_scenario,
    sha256_file,
)

VALID_YAML = """
scenario_id: s0_single_intersection
scenario_version: 1
description: Deterministic four-approach synthetic intersection.
network_file: network.net.xml
demand_file: demand.rou.xml
begin_s: 0.0
end_s: 600.0
step_length_s: 1.0
time_to_teleport_s: 300.0
default_seed: 1
"""


def _write_scenario(root, yaml_text=VALID_YAML):
    root.mkdir(parents=True, exist_ok=True)
    (root / "scenario.yaml").write_text(yaml_text)
    (root / "network.net.xml").write_text("<net/>")
    (root / "demand.rou.xml").write_text("<routes/>")
    return root


def test_loads_a_valid_scenario(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1")
    config, paths = load_scenario(root)
    assert config.scenario_id == "s0_single_intersection"
    assert config.end_s == 600.0
    assert paths.network.name == "network.net.xml"
    assert paths.network.is_file()


def test_rejects_an_unknown_key(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1", VALID_YAML + "typo_key: 3\n")
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_a_non_positive_step_length(tmp_path):
    bad = VALID_YAML.replace("step_length_s: 1.0", "step_length_s: 0.0")
    root = _write_scenario(tmp_path / "s0" / "v1", bad)
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_an_end_time_before_the_begin_time(tmp_path):
    bad = VALID_YAML.replace("end_s: 600.0", "end_s: -1.0")
    root = _write_scenario(tmp_path / "s0" / "v1", bad)
    with pytest.raises(ValidationError):
        load_scenario(root)


def test_rejects_a_missing_network_file(tmp_path):
    root = tmp_path / "s0" / "v1"
    root.mkdir(parents=True)
    (root / "scenario.yaml").write_text(VALID_YAML)
    (root / "demand.rou.xml").write_text("<routes/>")
    with pytest.raises(FileNotFoundError):
        load_scenario(root)


def test_the_config_is_frozen(tmp_path):
    root = _write_scenario(tmp_path / "s0" / "v1")
    config, _ = load_scenario(root)
    with pytest.raises(ValidationError):
        config.end_s = 1.0


def test_file_hash_is_stable_and_content_sensitive(tmp_path):
    a = tmp_path / "a.xml"
    a.write_text("<net/>")
    first = sha256_file(a)
    assert first == sha256_file(a)
    a.write_text("<net />")
    assert sha256_file(a) != first


def test_config_digest_ignores_field_order_but_not_values():
    reordered = "\n".join(reversed(VALID_YAML.strip().splitlines()))
    import yaml

    base = ScenarioConfig(**yaml.safe_load(VALID_YAML))
    same = ScenarioConfig(**yaml.safe_load(reordered))
    assert config_digest(base) == config_digest(same)

    changed = base.model_copy(update={"default_seed": 2})
    assert config_digest(changed) != config_digest(base)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/simulation/test_scenario.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation'`.

- [ ] **Step 3: Implement the scenario module**

Create `src/cadence/simulation/__init__.py` containing only:

```python
"""Simulation core: scenario definition, SUMO lifecycle, and raw event capture."""
```

`src/cadence/simulation/scenario.py`:

```python
"""Scenario definition, validation, and content hashing.

A scenario is an immutable, versioned input. Its identity is the pair (id, version) plus
the content hashes of its network and demand files, all of which enter the run manifest
(AP-06).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadence.types import ScenarioId

_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB; large enough that hashing a network file is one read.


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: ScenarioId
    scenario_version: int = Field(ge=1)
    description: str
    network_file: str
    demand_file: str
    begin_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    step_length_s: float = Field(gt=0.0)
    time_to_teleport_s: float
    default_seed: int = Field(ge=0)

    @model_validator(mode="after")
    def _end_follows_begin(self) -> Self:
        if self.end_s <= self.begin_s:
            raise ValueError(f"end_s ({self.end_s}) must be greater than begin_s ({self.begin_s})")
        return self


@dataclass(frozen=True)
class ScenarioPaths:
    root: Path
    network: Path
    demand: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def config_digest(config: ScenarioConfig) -> str:
    canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_scenario(root: Path) -> tuple[ScenarioConfig, ScenarioPaths]:
    config = ScenarioConfig(**yaml.safe_load((root / "scenario.yaml").read_text()))
    paths = ScenarioPaths(
        root=root,
        network=root / config.network_file,
        demand=root / config.demand_file,
    )
    for path in (paths.network, paths.demand):
        if not path.is_file():
            raise FileNotFoundError(f"scenario {config.scenario_id}: missing {path}")
    return config, paths
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/simulation/test_scenario.py -v`
Expected: 8 passed.

- [ ] **Step 5: Run the full gate**

Run: `make check`
Expected: all green. If mypy complains that `ScenarioId` is not a valid Pydantic field type,
it is: Pydantic v2 resolves `NewType` to its supertype.

- [ ] **Step 6: Commit**

```bash
git add src/cadence/simulation/__init__.py src/cadence/simulation/scenario.py tests/simulation/test_scenario.py
git commit -m "feat(simulation): add versioned scenario config with content hashing"
```

---

# Task 6: Generate the S0 scenario

**Files:**
- Create: `tools/build_s0_scenario.py`
- Create: `scenarios/s0_single_intersection/v1/scenario.yaml`
- Generate and commit: `scenarios/s0_single_intersection/v1/network.net.xml`,
  `scenarios/s0_single_intersection/v1/demand.rou.xml`
- Create: `tests/test_s0_scenario.py`

**Interfaces:**
- Consumes: `sumo.SUMO_HOME`, `sumolib`
- Produces: a loadable S0 scenario directory

S0 is a deterministic four-approach synthetic intersection used for integration testing,
action and safety validation, and metric verification. **It is not for research claims.**
The demand is generated from the network rather than hand-written, because `netgenerate`
chooses the edge identifiers and guessing them would be fragile.

- [ ] **Step 1: Write the generator**

`tools/build_s0_scenario.py`:

```python
"""Generates the S0 deterministic single-intersection scenario.

Routes are derived from the generated network rather than hand-written, because
netgenerate owns the edge identifiers. Re-running this script reproduces the committed
files byte for byte, on any machine.
"""

from __future__ import annotations

import functools
import math
import re
import subprocess
import sys
from pathlib import Path

# GOTCHA: importing sumo is what sets SUMO_HOME.
import sumo
import sumolib

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_ROOT = REPO_ROOT / "scenarios" / "s0_single_intersection" / "v1"

GRID_LENGTH_M = 200.0  # Approach length; long enough to hold a queue without spilling out.
ATTACH_LENGTH_M = 200.0  # Stub length on each of the four approaches.
LANES_PER_DIRECTION = 2  # Minimum that permits a separate turning movement later.

# One vehicle every 6 s per approach = 600 veh/h/approach, comfortably undersaturated for
# a two-lane approach (regime A). S0 exists to be predictable.
HEADWAY_S = 6.0
# Departures stop two minutes before the scenario horizon of 600 s so the network drains
# on its own; S0 should exercise the drain path, not the horizon cut-off.
DEPART_END_S = 480.0


def build_network(output: Path) -> None:
    binary = Path(sumo.SUMO_HOME) / "bin" / "netgenerate"
    # netgenerate records the output path it was given inside the file, so it is invoked
    # from the scenario directory with a relative name; an absolute path would embed the
    # generating machine's filesystem in a committed, publicly published artifact.
    subprocess.run(
        [
            str(binary),
            "--grid",
            "--grid.number=1",
            f"--grid.length={GRID_LENGTH_M}",
            f"--grid.attach-length={ATTACH_LENGTH_M}",
            f"--default.lanenumber={LANES_PER_DIRECTION}",
            "--tls.guess=true",
            "--tls.default-type=static",
            "--no-turnarounds=true",
            "--output-file",
            output.name,
        ],
        cwd=output.parent,
        check=True,
    )
    _strip_generation_timestamp(output)


def _strip_generation_timestamp(network: Path) -> None:
    """Remove the wall-clock stamp netgenerate writes into its header comment.

    A scenario's identity is the sha256 of its files, so the bytes must depend only on the
    generator's inputs. The option list in the header is kept: it is real provenance.
    """
    network.write_text(re.sub(r"generated on [^ ]+ by", "generated by", network.read_text()))


def _unit_direction(edge: sumolib.net.edge.Edge) -> tuple[float, float]:
    (x0, y0), (x1, y1) = edge.getShape()[0], edge.getShape()[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    return dx / norm, dy / norm


def _alignment(heading: tuple[float, float], edge: sumolib.net.edge.Edge) -> float:
    dx, dy = _unit_direction(edge)
    return heading[0] * dx + heading[1] * dy


def _approach_pairs(net: sumolib.net.Net) -> list[tuple[str, str]]:
    """Each incoming stub paired with its straight-through outgoing stub.

    The straight-through movement is the outgoing edge whose heading is closest to the
    incoming one, which is the one maximising the dot product of the unit directions.
    """
    junction = next(node for node in net.getNodes() if node.getType() == "traffic_light")
    outgoing = sorted(junction.getOutgoing(), key=lambda edge: edge.getID())
    pairs: list[tuple[str, str]] = []
    for in_edge in sorted(junction.getIncoming(), key=lambda edge: edge.getID()):
        best = max(outgoing, key=functools.partial(_alignment, _unit_direction(in_edge)))
        pairs.append((in_edge.getID(), best.getID()))
    return pairs


def build_demand(network: Path, output: Path) -> None:
    net = sumolib.net.readNet(str(network))
    pairs = _approach_pairs(net)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<routes>",
        '    <vType id="car" accel="2.6" decel="4.5" sigma="0.0" length="5.0" maxSpeed="13.9"/>',
    ]
    for index, (source, target) in enumerate(pairs):
        lines.append(f'    <route id="r{index}" edges="{source} {target}"/>')
    for index, _ in enumerate(pairs):
        lines.append(
            f'    <flow id="f{index}" route="r{index}" type="car" '
            f'begin="0.00" end="{DEPART_END_S:.2f}" period="{HEADWAY_S:.2f}" departLane="free"/>'
        )
    lines.append("</routes>")
    output.write_text("\n".join(lines) + "\n")


def main() -> int:
    SCENARIO_ROOT.mkdir(parents=True, exist_ok=True)
    network = SCENARIO_ROOT / "network.net.xml"
    build_network(network)
    build_demand(network, SCENARIO_ROOT / "demand.rou.xml")
    print(f"Wrote {network} and {SCENARIO_ROOT / 'demand.rou.xml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the generator**

```bash
uv run python tools/build_s0_scenario.py
```

Expected: two files written, `netgenerate` exits 0.

- [ ] **Step 3: Verify the network has exactly one traffic light**

```bash
uv run python -c "
import sumo, sumolib
net = sumolib.net.readNet('scenarios/s0_single_intersection/v1/network.net.xml')
tls = [n for n in net.getNodes() if n.getType() == 'traffic_light']
print('traffic lights:', len(tls))
print('incoming edges:', sorted(e.getID() for e in tls[0].getIncoming()))
"
```

This exact command was run before the task was written, and its output is known:

```
traffic lights: 1
incoming edges: ['bottom0A0', 'left0A0', 'right0A0', 'top0A0']
```

The generated network has five nodes — `A0` of type `traffic_light` with four incoming and
four outgoing edges, plus `top0`, `bottom0`, `left0`, `right0` as dead ends — and one
traffic-light program, `A0`. The straight-through pairing was verified against this
network and resolves as `bottom0A0 -> A0top0`, `left0A0 -> A0right0`,
`right0A0 -> A0left0`, `top0A0 -> A0bottom0`.

If your output differs from this, stop and report it rather than adapting: something about
the toolchain has changed since the plan was written.

- [ ] **Step 4: Write the scenario manifest**

`scenarios/s0_single_intersection/v1/scenario.yaml`:

```yaml
scenario_id: s0_single_intersection
scenario_version: 1
description: >
  Deterministic four-approach synthetic intersection, two lanes per direction, one
  static traffic light. Integration testing, action and safety validation, and metric
  verification only. Not for research claims.
network_file: network.net.xml
demand_file: demand.rou.xml
begin_s: 0.0
end_s: 600.0
step_length_s: 1.0
time_to_teleport_s: 300.0
default_seed: 1
```

- [ ] **Step 5: Write the failing test**

`tests/test_s0_scenario.py`:

```python
from pathlib import Path

import pytest

from cadence.simulation.scenario import load_scenario

S0_ROOT = Path(__file__).resolve().parents[1] / "scenarios" / "s0_single_intersection" / "v1"


def test_s0_loads():
    config, paths = load_scenario(S0_ROOT)
    assert config.scenario_id == "s0_single_intersection"
    assert config.scenario_version == 1
    assert paths.network.is_file()
    assert paths.demand.is_file()


def test_s0_network_is_machine_independent():
    # The committed bytes are the scenario's identity, so they must not carry the
    # generating machine's paths or clock.
    text = (S0_ROOT / "network.net.xml").read_text()
    assert "/Users/" not in text
    assert "/home/" not in text
    assert "generated on " not in text


def test_s0_has_exactly_one_traffic_light():
    import sumo  # noqa: F401
    import sumolib

    net = sumolib.net.readNet(str(S0_ROOT / "network.net.xml"))
    lights = [node for node in net.getNodes() if node.getType() == "traffic_light"]
    assert len(lights) == 1


def test_s0_traffic_light_has_four_approaches():
    import sumo  # noqa: F401
    import sumolib

    net = sumolib.net.readNet(str(S0_ROOT / "network.net.xml"))
    light = next(node for node in net.getNodes() if node.getType() == "traffic_light")
    assert len(light.getIncoming()) == 4
    assert len(light.getOutgoing()) == 4


@pytest.mark.sumo
def test_sumo_loads_s0_without_errors():
    import subprocess

    import sumo

    result = subprocess.run(
        [
            str(Path(sumo.SUMO_HOME) / "bin" / "sumo"),
            "--net-file", str(S0_ROOT / "network.net.xml"),
            "--route-files", str(S0_ROOT / "demand.rou.xml"),
            "--end", "10",
            "--no-step-log", "true",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Error" not in result.stderr
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_s0_scenario.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add tools/build_s0_scenario.py scenarios/s0_single_intersection/v1 tests/test_s0_scenario.py
git commit -m "feat(scenarios): add S0 deterministic single intersection"
```

---

# Task 7: Simulator binding selection

**Files:**
- Create: `src/cadence/simulation/sumo/__init__.py`, `src/cadence/simulation/sumo/binding.py`
- Create: `tests/simulation/sumo/test_binding.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `BindingKind` — a `StrEnum` with members `TRACI = "traci"` and `LIBSUMO = "libsumo"`.
    `StrEnum` rather than `(str, Enum)` because ruff `UP042` rejects the latter on 3.11+;
    it keeps `BindingKind("libsumo")` parsing, `.value`, and Typer option handling, all
    verified.
  - `load_binding(kind: BindingKind) -> ModuleType`
  - `sumo_home() -> Path`
  - `sumo_version() -> str`

This is the only module in `src/` allowed to import `traci` or `libsumo`, enforced by
`ARCH-D02`, ruff `TID251`, and `tests/test_architecture.py`.

- [ ] **Step 1: Write the failing test**

`tests/simulation/sumo/test_binding.py`:

```python
import pytest

from cadence.simulation.sumo.binding import BindingKind, load_binding, sumo_home, sumo_version

REQUIRED_FUNCTIONS = ("start", "simulationStep", "close")
REQUIRED_DOMAINS = ("simulation", "lane", "edge", "trafficlight", "vehicle")


def test_sumo_home_exists():
    assert (sumo_home() / "bin" / "sumo").is_file()


def test_sumo_version_is_pinned():
    assert sumo_version() == "1.27.1"


@pytest.mark.parametrize("kind", list(BindingKind))
def test_both_bindings_expose_the_functions_the_harness_uses(kind):
    binding = load_binding(kind)
    for name in REQUIRED_FUNCTIONS:
        assert callable(getattr(binding, name)), f"{kind.value} lacks {name}"


@pytest.mark.parametrize("kind", list(BindingKind))
def test_both_bindings_expose_the_domains_the_harness_uses(kind):
    binding = load_binding(kind)
    for name in REQUIRED_DOMAINS:
        assert hasattr(binding, name), f"{kind.value} lacks domain {name}"


def test_load_binding_is_idempotent():
    assert load_binding(BindingKind.TRACI) is load_binding(BindingKind.TRACI)


def test_binding_kind_parses_from_a_config_string():
    assert BindingKind("libsumo") is BindingKind.LIBSUMO
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/simulation/sumo/test_binding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation.sumo'`.

- [ ] **Step 3: Implement the binding module**

Create `src/cadence/simulation/sumo/__init__.py` containing only:

```python
"""SUMO-specific infrastructure. The rest of CADENCE speaks traffic, not TraCI."""
```

`src/cadence/simulation/sumo/binding.py`:

```python
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
    # GOTCHA: importing `sumo` is what sets SUMO_HOME. It must precede traci and sumolib.
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/simulation/sumo/test_binding.py -v`
Expected: 8 passed (two parametrised tests times two bindings, plus four).

- [ ] **Step 5: Verify the boundary is actually enforced**

```bash
uv run ruff check src/
echo "import traci" >> src/cadence/simulation/scenario.py
uv run ruff check src/cadence/simulation/scenario.py; echo "ruff exit: $?"
uv run pytest tests/test_architecture.py::test_only_the_binding_module_imports_the_simulator -q; echo "pytest exit: $?"
git checkout src/cadence/simulation/scenario.py
```

Expected: clean first, then **both** ruff and pytest report a failure, then clean again.
If either passes with the violation in place, the enforcement is broken — fix it before
continuing.

- [ ] **Step 6: Pin down the detector's relative-import filter**

This is the first task to add a module the ARCH-D02 detector must police, and its
`_imported_roots` helper ignores relative imports (`node.level == 0`). That filter is
deliberate — `traci`, `libsumo`, and `studies` are top-level absolute packages that
relative syntax cannot reach from inside `cadence` — but an unexplained filter reads as a
hole. Give it a test that says so.

Append to `tests/test_architecture.py`:

```python
def test_detector_ignores_relative_imports(tmp_path):
    # Relative imports cannot reach traci, libsumo, or studies from inside cadence, so
    # node.level == 0 is a deliberate filter rather than a gap.
    sibling = tmp_path / "sibling.py"
    sibling.write_text("from . import scenario\nfrom .sumo import binding\n")
    assert _imported_roots(sibling) == set()
```

Run: `uv run pytest tests/test_architecture.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add src/cadence/simulation/sumo/ tests/simulation/sumo/test_binding.py tests/test_architecture.py
git commit -m "feat(simulation): add switchable TraCI/libsumo binding (ARCH-D02)"
```

---

# Task 8: SUMO command construction

**Files:**
- Create: `src/cadence/simulation/sumo/command.py`
- Create: `tests/simulation/sumo/test_command.py`

**Interfaces:**
- Consumes: `ScenarioConfig`, `ScenarioPaths`, `sumo_home()`
- Produces: `build_sumo_command(config, paths, *, seed: int, use_gui: bool = False) -> list[str]`

Every determinism-relevant flag is set explicitly rather than left to a SUMO default, so
that a future SUMO upgrade cannot silently change experiment behaviour.

- [ ] **Step 1: Write the failing test**

`tests/simulation/sumo/test_command.py`:

```python
from pathlib import Path

import pytest

from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.sumo.command import build_sumo_command

CONFIG = ScenarioConfig(
    scenario_id="s0_single_intersection",
    scenario_version=1,
    description="test",
    network_file="network.net.xml",
    demand_file="demand.rou.xml",
    begin_s=0.0,
    end_s=600.0,
    step_length_s=1.0,
    time_to_teleport_s=300.0,
    default_seed=1,
)
PATHS = ScenarioPaths(
    root=Path("/scenario"),
    network=Path("/scenario/network.net.xml"),
    demand=Path("/scenario/demand.rou.xml"),
)


def _flag(command, name):
    return command[command.index(name) + 1]


def test_binary_is_sumo_by_default():
    command = build_sumo_command(CONFIG, PATHS, seed=7)
    assert command[0].endswith("/bin/sumo")


def test_binary_is_sumo_gui_when_requested():
    command = build_sumo_command(CONFIG, PATHS, seed=7, use_gui=True)
    assert command[0].endswith("/bin/sumo-gui")


def test_network_and_demand_are_passed():
    command = build_sumo_command(CONFIG, PATHS, seed=7)
    assert _flag(command, "--net-file") == "/scenario/network.net.xml"
    assert _flag(command, "--route-files") == "/scenario/demand.rou.xml"


def test_seed_overrides_the_scenario_default():
    command = build_sumo_command(CONFIG, PATHS, seed=7)
    assert _flag(command, "--seed") == "7"


def test_timing_flags_come_from_the_scenario():
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert _flag(command, "--begin") == "0.0"
    assert _flag(command, "--end") == "600.0"
    assert _flag(command, "--step-length") == "1.0"


def test_waiting_time_memory_is_the_episode_duration_not_the_end_time():
    # SUMO documents --waiting-time-memory as a length of interval. Passing end_s would
    # be wrong for any scenario that does not begin at zero.
    offset = CONFIG.model_copy(update={"begin_s": 100.0, "end_s": 700.0})
    command = build_sumo_command(offset, PATHS, seed=1)
    assert _flag(command, "--waiting-time-memory") == "600.0"


def test_teleport_threshold_is_explicit():
    # The definition of done requires teleportation to be configured, not defaulted.
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert _flag(command, "--time-to-teleport") == "300.0"


def test_random_is_disabled_so_the_seed_governs():
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert _flag(command, "--random") == "false"


def test_command_is_deterministic():
    assert build_sumo_command(CONFIG, PATHS, seed=3) == build_sumo_command(CONFIG, PATHS, seed=3)


def test_a_negative_seed_is_rejected():
    with pytest.raises(ValueError, match="seed"):
        build_sumo_command(CONFIG, PATHS, seed=-1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/simulation/sumo/test_command.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation.sumo.command'`.

- [ ] **Step 3: Implement command construction**

`src/cadence/simulation/sumo/command.py`:

```python
"""Builds the SUMO argument vector for a scenario run.

Every flag that affects determinism or failure behaviour is set explicitly, so that a SUMO
upgrade cannot change experiment semantics through a changed default (AP-06).
"""

from __future__ import annotations

from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths
from cadence.simulation.sumo.binding import sumo_home


def build_sumo_command(
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    use_gui: bool = False,
) -> list[str]:
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")

    binary = sumo_home() / "bin" / ("sumo-gui" if use_gui else "sumo")
    return [
        str(binary),
        "--net-file", str(paths.network),
        "--route-files", str(paths.demand),
        "--begin", str(config.begin_s),
        "--end", str(config.end_s),
        "--step-length", str(config.step_length_s),
        "--seed", str(seed),
        "--random", "false",
        "--time-to-teleport", str(config.time_to_teleport_s),
        "--no-step-log", "true",
        "--duration-log.disable", "true",
        # SUMO documents this as "length of time interval", i.e. a duration, not an
        # absolute time. Its 100 s default would truncate waiting metrics on a longer run.
        "--waiting-time-memory", str(config.end_s - config.begin_s),
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/simulation/sumo/test_command.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cadence/simulation/sumo/command.py tests/simulation/sumo/test_command.py
git commit -m "feat(simulation): build SUMO command with explicit determinism flags"
```

---

# Task 9: Connection lifecycle and event capture

**Files:**
- Create: `src/cadence/simulation/events.py`
- Create: `src/cadence/simulation/sumo/connection.py`
- Create: `tests/simulation/test_events.py`
- Create: `tests/simulation/sumo/test_connection.py`

**Interfaces:**
- Consumes: `BindingKind`, `load_binding`, `build_sumo_command`, `ScenarioConfig`,
  `ScenarioPaths`, `VehicleId`
- Produces:
  - `EventKind` — `str` `Enum`: `DEPARTED`, `ARRIVED`, `TELEPORT_STARTED`,
    `TELEPORT_ENDED`, `COLLISION`
  - `SimulationEvent` — frozen dataclass `(time_s: float, kind: EventKind, vehicle_id: VehicleId)`
  - `StepResult` — frozen dataclass `(time_s: float, events: tuple[SimulationEvent, ...],
    expected_remaining_veh: int)`
  - `EventLog` with `append_step(result) -> None`, `events: tuple[SimulationEvent, ...]`,
    `count(kind) -> int`, `to_parquet(path) -> None`
  - `SumoConnection(config, paths, *, seed, binding, use_gui=False)` as a context manager
    with `step() -> StepResult` and `is_finished() -> bool`

- [ ] **Step 1: Write the failing event test**

`tests/simulation/test_events.py`:

```python
import polars as pl

from cadence.simulation.events import EventKind, EventLog, SimulationEvent, StepResult


def _step(time_s, kinds):
    events = tuple(
        SimulationEvent(time_s=time_s, kind=kind, vehicle_id=f"v{index}")
        for index, kind in enumerate(kinds)
    )
    return StepResult(time_s=time_s, events=events, expected_remaining_veh=len(kinds))


def test_event_is_frozen():
    event = SimulationEvent(time_s=1.0, kind=EventKind.DEPARTED, vehicle_id="v0")
    try:
        event.time_s = 2.0
    except Exception as error:
        # CPython's FrozenInstanceError message is "cannot assign to field 'x'" on every
        # 3.7+ release; it contains neither "frozen" nor "attribute" despite the type
        # subclassing AttributeError.
        message = str(error).lower()
        assert "frozen" in message or "attribute" in message or "cannot assign" in message
    else:
        raise AssertionError("SimulationEvent must be immutable")


def test_log_accumulates_events_in_order():
    log = EventLog()
    log.append_step(_step(1.0, [EventKind.DEPARTED]))
    log.append_step(_step(2.0, [EventKind.ARRIVED, EventKind.TELEPORT_STARTED]))
    assert [event.time_s for event in log.events] == [1.0, 2.0, 2.0]


def test_log_counts_by_kind():
    log = EventLog()
    log.append_step(_step(1.0, [EventKind.DEPARTED, EventKind.DEPARTED]))
    log.append_step(_step(2.0, [EventKind.ARRIVED]))
    assert log.count(EventKind.DEPARTED) == 2
    assert log.count(EventKind.ARRIVED) == 1
    assert log.count(EventKind.COLLISION) == 0


def test_log_writes_readable_parquet(tmp_path):
    log = EventLog()
    log.append_step(_step(1.0, [EventKind.DEPARTED]))
    log.append_step(_step(2.0, [EventKind.TELEPORT_STARTED]))
    output = tmp_path / "events.parquet"
    log.to_parquet(output)

    frame = pl.read_parquet(output)
    assert frame.columns == ["time_s", "kind", "vehicle_id"]
    assert frame.height == 2
    assert frame["kind"].to_list() == ["departed", "teleport_started"]


def test_empty_log_still_writes_a_valid_file(tmp_path):
    output = tmp_path / "events.parquet"
    EventLog().to_parquet(output)
    assert pl.read_parquet(output).height == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/simulation/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation.events'`.

- [ ] **Step 3: Implement events**

`src/cadence/simulation/events.py`:

```python
"""Raw simulation events captured per step.

The event stream is the harness's primary output and the basis of the reproducibility
check. It is controller-independent by construction (ARCH-D05).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import polars as pl

from cadence.types import VehicleId


class EventKind(StrEnum):
    DEPARTED = "departed"
    ARRIVED = "arrived"
    TELEPORT_STARTED = "teleport_started"
    TELEPORT_ENDED = "teleport_ended"
    COLLISION = "collision"


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    time_s: float
    kind: EventKind
    vehicle_id: VehicleId


@dataclass(frozen=True, slots=True)
class StepResult:
    time_s: float
    events: tuple[SimulationEvent, ...]
    expected_remaining_veh: int


@dataclass
class EventLog:
    _events: list[SimulationEvent] = field(default_factory=list)

    @property
    def events(self) -> tuple[SimulationEvent, ...]:
        return tuple(self._events)

    def append_step(self, result: StepResult) -> None:
        self._events.extend(result.events)

    def extend(self, events: Iterable[SimulationEvent]) -> None:
        self._events.extend(events)

    def count(self, kind: EventKind) -> int:
        return sum(1 for event in self._events if event.kind is kind)

    def to_parquet(self, path: Path) -> None:
        frame = pl.DataFrame(
            {
                "time_s": [event.time_s for event in self._events],
                "kind": [event.kind.value for event in self._events],
                "vehicle_id": [str(event.vehicle_id) for event in self._events],
            },
            schema={"time_s": pl.Float64, "kind": pl.Utf8, "vehicle_id": pl.Utf8},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
```

- [ ] **Step 4: Run the event tests to verify they pass**

Run: `uv run pytest tests/simulation/test_events.py -v`
Expected: 5 passed.

- [ ] **Step 5: Write the failing connection test**

`tests/simulation/sumo/test_connection.py`:

```python
from pathlib import Path

import pytest

from cadence.simulation.events import EventKind, EventLog
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"

pytestmark = pytest.mark.sumo


@pytest.fixture
def s0():
    return load_scenario(S0_ROOT)


def test_connection_starts_and_closes_cleanly(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        assert connection.step().time_s > 0.0


def test_time_advances_by_the_step_length(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        first = connection.step().time_s
        second = connection.step().time_s
    assert second - first == pytest.approx(config.step_length_s)


def test_vehicles_depart_and_arrive(s0):
    config, paths = s0
    log = EventLog()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            log.append_step(connection.step())
    assert log.count(EventKind.DEPARTED) > 0
    assert log.count(EventKind.ARRIVED) > 0


def test_every_arrival_follows_its_own_departure(s0):
    config, paths = s0
    log = EventLog()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            log.append_step(connection.step())

    departed: set[str] = set()
    for event in log.events:
        if event.kind is EventKind.DEPARTED:
            departed.add(event.vehicle_id)
        elif event.kind is EventKind.ARRIVED:
            assert event.vehicle_id in departed, f"{event.vehicle_id} arrived without departing"


def test_connection_closes_even_when_the_body_raises(s0):
    config, paths = s0
    connection = SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI)
    with pytest.raises(RuntimeError), connection:
        connection.step()
        raise RuntimeError("boom")
    assert connection.is_closed


def test_stepping_a_closed_connection_is_an_error(s0):
    config, paths = s0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI) as connection:
        connection.step()
    with pytest.raises(RuntimeError, match="closed"):
        connection.step()


def test_the_run_stops_at_the_scenario_horizon(s0):
    config, paths = s0
    # S0 drains at roughly 500 s, so a 60 s horizon forces the cut-off path rather than
    # the drain path. Without the horizon check the loop would never terminate.
    short = config.model_copy(update={"end_s": 60.0})
    last_time_s, steps = 0.0, 0
    with SumoConnection(short, paths, seed=1, binding=BindingKind.TRACI) as connection:
        while not connection.is_finished():
            last_time_s = connection.step().time_s
            steps += 1
            assert steps < 1000, "is_finished never became true; the horizon is not enforced"
    assert last_time_s <= 60.0


def test_libsumo_produces_the_same_event_stream_as_traci(s0):
    config, paths = s0

    def run(binding):
        log = EventLog()
        with SumoConnection(config, paths, seed=1, binding=binding) as connection:
            while not connection.is_finished():
                log.append_step(connection.step())
        return [(event.time_s, event.kind, event.vehicle_id) for event in log.events]

    assert run(BindingKind.TRACI) == run(BindingKind.LIBSUMO)
```

- [ ] **Step 6: Run the connection test to verify it fails**

Run: `uv run pytest tests/simulation/sumo/test_connection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation.sumo.connection'`.

- [ ] **Step 7: Implement the connection**

`src/cadence/simulation/sumo/connection.py`:

```python
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
```

- [ ] **Step 8: Run the connection tests to verify they pass**

Run: `uv run pytest tests/simulation/sumo/test_connection.py -v`
Expected: 8 passed.

If `test_libsumo_produces_the_same_event_stream_as_traci` fails, **do not weaken the
test.** A behavioural difference between the two bindings is exactly the risk `PD-D03`
accepted when it made the binding switchable. Record the difference, open a `SIM-D`
decision in `research/decisions.yaml` describing it, and reference that decision from a
GOTCHA comment in `binding.py`.

- [ ] **Step 9: Test the lifecycle without starting SUMO**

`tests/simulation/sumo/test_connection.py` carries a module-level `pytest.mark.sumo`, and
every test in it launches a real process. The failure this step covers needs no simulator,
so it lives in its own unmarked file and stays available to a fast `-m "not sumo"` run.

Create `tests/simulation/sumo/test_connection_lifecycle.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"


def _connection_with(binding):
    config, paths = load_scenario(S0_ROOT)
    connection = SumoConnection(config, paths, seed=1, binding=BindingKind.TRACI)
    connection._binding = binding
    return connection


def test_a_failing_close_still_marks_the_connection_closed():
    # SUMO dying mid-run makes traci's close() raise. If is_closed stayed False the
    # object would keep accepting steps against a dead process.
    binding = MagicMock()
    binding.close.side_effect = RuntimeError("socket already dead")
    connection = _connection_with(binding)

    with pytest.raises(RuntimeError, match="socket already dead"):
        connection.close()

    assert connection.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        connection.step()


def test_close_is_idempotent():
    binding = MagicMock()
    connection = _connection_with(binding)
    connection.close()
    connection.close()
    assert binding.close.call_count == 1
```

Run: `uv run pytest tests/simulation/sumo/test_connection_lifecycle.py -v`
Expected: 2 passed. Confirm the first fails before the `try/finally` change.

- [ ] **Step 10: Commit**

```bash
git add src/cadence/simulation/events.py src/cadence/simulation/sumo/connection.py tests/simulation/test_events.py tests/simulation/sumo/test_connection.py tests/simulation/sumo/test_connection_lifecycle.py
git commit -m "feat(simulation): add SUMO connection lifecycle and event capture"
```

---

# Task 10: Run manifest, CLI, and the reproducibility proof

**Files:**
- Create: `src/cadence/simulation/manifest.py`
- Create: `src/cadence/cli.py`
- Create: `tests/simulation/test_manifest.py`
- Create: `tests/simulation/sumo/test_reproducibility.py`
- Modify: `pyproject.toml` — add the console script

**Interfaces:**
- Consumes: everything from Tasks 4-9
- Produces:
  - `RunManifest` (frozen Pydantic model)
  - `build_manifest(...) -> RunManifest`
  - `git_commit(repo_root) -> tuple[str, bool]` returning `(sha, is_dirty)`
  - `run_scenario(scenario_root, output_root, *, seed, binding) -> Path` returning the run
    directory
  - console script `cadence` with subcommands `run` and `validate-scenario`

- [ ] **Step 1: Write the failing manifest test**

`tests/simulation/test_manifest.py`:

```python
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadence.simulation.manifest import NON_REPRODUCIBLE_FIELDS, RunManifest, git_commit

REPO_ROOT = Path(__file__).resolve().parents[2]

FIELDS = {
    "cadence_commit",
    "cadence_dirty",
    "cadence_version",
    "sumo_version",
    "python_version",
    "platform_tag",
    "binding",
    "scenario_id",
    "scenario_version",
    "network_sha256",
    "demand_sha256",
    "config_sha256",
    "seed",
    "begin_s",
    "end_s",
    "step_length_s",
    "time_to_teleport_s",
    "started_at_utc",
    "finished_at_utc",
}


def test_manifest_declares_every_reproducibility_field():
    assert set(RunManifest.model_fields) == FIELDS


def test_manifest_is_frozen(manifest_fixture):
    with pytest.raises(ValidationError):
        manifest_fixture.seed = 99


def test_manifest_round_trips_through_json(tmp_path, manifest_fixture):
    path = tmp_path / "manifest.json"
    path.write_text(manifest_fixture.model_dump_json(indent=2))
    assert RunManifest(**json.loads(path.read_text())) == manifest_fixture


def test_the_exclusion_set_names_only_real_fields():
    # A stale name already fails loudly when reproducible_fields() drops it, but adding a
    # real field here would silently remove it from every comparison, with nothing to catch
    # that. Lives here rather than beside the reproducibility tests because it needs no
    # simulator and must stay reachable under `-m "not sumo"`.
    assert set(RunManifest.model_fields) >= NON_REPRODUCIBLE_FIELDS
    assert set(RunManifest.model_fields) - NON_REPRODUCIBLE_FIELDS


def test_git_commit_reports_the_repository_head():
    sha, dirty = git_commit(REPO_ROOT)
    assert len(sha) == 40
    assert isinstance(dirty, bool)


@pytest.fixture
def manifest_fixture():
    return RunManifest(
        cadence_commit="0" * 40,
        cadence_dirty=False,
        cadence_version="0.0.0",
        sumo_version="1.27.1",
        python_version="3.12.0",
        platform_tag="Darwin-arm64",
        binding="traci",
        scenario_id="s0_single_intersection",
        scenario_version=1,
        network_sha256="a" * 64,
        demand_sha256="b" * 64,
        config_sha256="c" * 64,
        seed=1,
        begin_s=0.0,
        end_s=600.0,
        step_length_s=1.0,
        time_to_teleport_s=300.0,
        started_at_utc="2026-08-23T00:00:00+00:00",
        finished_at_utc="2026-08-23T00:00:10+00:00",
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/simulation/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cadence.simulation.manifest'`.

- [ ] **Step 3: Implement the manifest**

`src/cadence/simulation/manifest.py`:

```python
"""Run manifest — everything required to reproduce a run (AP-06).

Timestamps are recorded for provenance but are excluded from any reproducibility
comparison, since they differ between two runs that are otherwise identical.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from cadence import __version__ as cadence_version
from cadence.simulation.scenario import ScenarioConfig, ScenarioPaths, config_digest, sha256_file
from cadence.simulation.sumo.binding import BindingKind, sumo_version

# Fields that legitimately differ between two identical runs.
NON_REPRODUCIBLE_FIELDS = frozenset({"started_at_utc", "finished_at_utc"})


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cadence_commit: str
    cadence_dirty: bool
    cadence_version: str
    sumo_version: str
    python_version: str
    platform_tag: str
    binding: str
    scenario_id: str
    scenario_version: int
    network_sha256: str
    demand_sha256: str
    config_sha256: str
    seed: int
    begin_s: float
    end_s: float
    step_length_s: float
    time_to_teleport_s: float
    started_at_utc: str
    finished_at_utc: str

    def reproducible_fields(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump().items()
            if key not in NON_REPRODUCIBLE_FIELDS
        }


def git_commit(repo_root: Path) -> tuple[str, bool]:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return sha, bool(status)


def build_manifest(
    repo_root: Path,
    config: ScenarioConfig,
    paths: ScenarioPaths,
    *,
    seed: int,
    binding: BindingKind,
    started_at_utc: str,
    finished_at_utc: str,
) -> RunManifest:
    sha, dirty = git_commit(repo_root)
    return RunManifest(
        cadence_commit=sha,
        cadence_dirty=dirty,
        cadence_version=cadence_version,
        sumo_version=sumo_version(),
        python_version=platform.python_version(),
        # eclipse-sumo ships platform-specific binary wheels and SUMO's floating-point
        # results are not guaranteed identical across builds, so the OS and architecture
        # are part of what determines a run's output.
        platform_tag=f"{platform.system()}-{platform.machine()}",
        binding=binding.value,
        scenario_id=str(config.scenario_id),
        scenario_version=config.scenario_version,
        network_sha256=sha256_file(paths.network),
        demand_sha256=sha256_file(paths.demand),
        config_sha256=config_digest(config),
        seed=seed,
        begin_s=config.begin_s,
        end_s=config.end_s,
        step_length_s=config.step_length_s,
        time_to_teleport_s=config.time_to_teleport_s,
        started_at_utc=started_at_utc,
        finished_at_utc=finished_at_utc,
    )
```

- [ ] **Step 4: Run the manifest tests**

Run: `uv run pytest tests/simulation/test_manifest.py -v`
Expected: 5 passed.

- [ ] **Step 5: Implement the CLI**

`src/cadence/cli.py`:

```python
"""CADENCE command line interface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from cadence.simulation.events import EventLog
from cadence.simulation.manifest import build_manifest
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

app = typer.Typer(help="CADENCE traffic control experimentation platform.")
REPO_ROOT = Path(__file__).resolve().parents[2]


def run_scenario(
    scenario_root: Path,
    output_root: Path,
    *,
    seed: int,
    binding: BindingKind,
) -> Path:
    config, paths = load_scenario(scenario_root)
    started = datetime.now(UTC).isoformat()

    log = EventLog()
    with SumoConnection(config, paths, seed=seed, binding=binding) as connection:
        while not connection.is_finished():
            log.append_step(connection.step())

    finished = datetime.now(UTC).isoformat()
    manifest = build_manifest(
        REPO_ROOT, config, paths,
        seed=seed, binding=binding,
        started_at_utc=started, finished_at_utc=finished,
    )

    stamp = started.replace(":", "").replace("-", "")[:15]
    run_dir = output_root / (
        f"{stamp}__{config.scenario_id}-v{config.scenario_version}__none-v1__seed{seed}"
    )
    # exist_ok=False on purpose: the stamp is second-resolution, so two runs of the same
    # scenario and seed starting in the same second would otherwise clobber the first's
    # manifest and events. Losing an artifact silently is worse than failing loudly.
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    log.to_parquet(run_dir / "events.parquet")
    return run_dir


@app.command()
def run(
    scenario: Path = typer.Option(..., help="Path to a scenario version directory."),
    output: Path = typer.Option(Path("studies/00-harness/runs"), help="Run output root."),
    seed: int = typer.Option(1, min=0),
    binding: BindingKind = typer.Option(BindingKind.LIBSUMO),
) -> None:
    run_dir = run_scenario(scenario, output, seed=seed, binding=binding)
    typer.echo(f"Run written to {run_dir}")


@app.command("validate-scenario")
def validate_scenario(
    scenario: Path = typer.Option(..., help="Path to a scenario version directory."),
) -> None:
    config, paths = load_scenario(scenario)
    problems = validate_network(paths)
    for problem in problems:
        typer.echo(f"FAIL  {problem}")
    if problems:
        raise typer.Exit(code=1)
    typer.echo(f"{config.scenario_id} v{config.scenario_version}: OK")
    typer.echo(f"  network: {paths.network}")
    typer.echo(f"  demand:  {paths.demand}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Implement network validation**

`docs/specs/2026-08-22-project-direction.md` §10 places `cadence validate-scenario` at M0.
Implement the checks that are meaningful for a generated network; the OSM-specific ones
(lane counts, turn restrictions, signal tagging) arrive with M7 and are not guessed at now.

Create `src/cadence/simulation/validation.py`:

```python
"""Scenario network validation.

Covers defects that make a scenario unusable regardless of provenance. Checks specific to
OSM-derived networks arrive at M7, when there is a real imported network to fail against.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

import sumolib

from cadence.simulation.scenario import ScenarioPaths


def _route_edge_ids(demand_path: str) -> set[str]:
    """Every edge the demand file names, however it names it.

    Declared routes cover S0, but generated demand often uses <trip> or <flow> with
    from/to/via instead, and a validator that only reads <route> would pass those blind.
    """
    root = ElementTree.parse(demand_path).getroot()
    edges: set[str] = set()
    for route in root.iter("route"):
        edges.update((route.get("edges") or "").split())
    for tag in ("flow", "trip"):
        for element in root.iter(tag):
            edges.update(
                value for value in (element.get("from"), element.get("to")) if value
            )
            edges.update((element.get("via") or "").split())
    return edges


def validate_network(paths: ScenarioPaths) -> list[str]:
    problems: list[str] = []
    net = sumolib.net.readNet(str(paths.network))

    signalised = [node for node in net.getNodes() if node.getType() == "traffic_light"]
    if not signalised:
        problems.append("network contains no signalised junction")

    for node in signalised:
        if not node.getIncoming():
            problems.append(f"signalised junction {node.getID()} has no incoming edge")
        if not node.getOutgoing():
            problems.append(f"signalised junction {node.getID()} has no outgoing edge")

    for edge in net.getEdges():
        # A stub ending at a dead end is the network boundary, not a defect. An edge that
        # arrives at a real junction with no permitted onward movement strands its traffic.
        if edge.getToNode().getType() != "dead_end" and not edge.getOutgoing():
            problems.append(
                f"edge {edge.getID()} arrives at junction "
                f"{edge.getToNode().getID()} with no onward movement"
            )

    known = {edge.getID() for edge in net.getEdges()}
    for edge_id in sorted(_route_edge_ids(str(paths.demand)) - known):
        problems.append(f"route references edge {edge_id}, which is not in the network")

    return problems
```

Add the import to `src/cadence/cli.py`:

```python
from cadence.simulation.validation import validate_network
```

- [ ] **Step 7: Write the validation test**

`tests/simulation/test_validation.py`:

```python
from pathlib import Path

from cadence.simulation.scenario import ScenarioPaths, load_scenario
from cadence.simulation.validation import validate_network

S0_ROOT = Path(__file__).resolve().parents[2] / "scenarios" / "s0_single_intersection" / "v1"


def test_s0_is_valid():
    _, paths = load_scenario(S0_ROOT)
    assert validate_network(paths) == []


def test_a_route_referencing_an_unknown_edge_is_reported(tmp_path):
    _, real = load_scenario(S0_ROOT)
    demand = tmp_path / "demand.rou.xml"
    demand.write_text('<routes><route id="r" edges="ghost_edge"/></routes>')
    problems = validate_network(ScenarioPaths(root=tmp_path, network=real.network, demand=demand))
    assert any("ghost_edge" in problem for problem in problems)


def test_a_trip_referencing_an_unknown_edge_is_reported(tmp_path):
    # Generated demand often uses <trip> rather than declared routes.
    _, real = load_scenario(S0_ROOT)
    demand = tmp_path / "demand.rou.xml"
    demand.write_text('<routes><trip id="t" from="phantom_edge" to="A0top0"/></routes>')
    problems = validate_network(ScenarioPaths(root=tmp_path, network=real.network, demand=demand))
    assert any("phantom_edge" in problem for problem in problems)
```

Run: `uv run pytest tests/simulation/test_validation.py -v`
Expected: 3 passed.

- [ ] **Step 8: Register the console script**

Add to `pyproject.toml`:

```toml
[project.scripts]
cadence = "cadence.cli:app"
```

Then: `uv sync`

- [ ] **Step 9: Write the failing reproducibility test**

`tests/simulation/sumo/test_reproducibility.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from cadence.cli import run_scenario
from cadence.simulation.manifest import NON_REPRODUCIBLE_FIELDS, RunManifest
from cadence.simulation.sumo.binding import BindingKind

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"

pytestmark = pytest.mark.sumo


def _run(tmp_path, name, seed):
    return run_scenario(S0_ROOT, tmp_path / name, seed=seed, binding=BindingKind.TRACI)


def test_the_same_seed_produces_an_identical_event_stream(tmp_path):
    first = pl.read_parquet(_run(tmp_path, "a", 1) / "events.parquet")
    second = pl.read_parquet(_run(tmp_path, "b", 1) / "events.parquet")
    # Two empty frames compare equal, which would make the assertion below vacuous.
    assert first.height > 0
    assert first.equals(second)


def test_a_different_seed_still_completes(tmp_path):
    # Deliberately asserts nothing about the contents: S0 uses sigma=0.0 and fixed flows,
    # so a seed change may legitimately change nothing. This guards only against a crash.
    assert pl.read_parquet(_run(tmp_path, "c", 2) / "events.parquet").height > 0


def test_manifests_match_except_for_timestamps(tmp_path):
    first = RunManifest(**json.loads((_run(tmp_path, "d", 1) / "manifest.json").read_text()))
    second = RunManifest(**json.loads((_run(tmp_path, "e", 1) / "manifest.json").read_text()))
    assert first.reproducible_fields() == second.reproducible_fields()


def test_a_same_second_run_refuses_to_overwrite(tmp_path, monkeypatch):
    # A real run takes over a second, so the second-resolution stamp differs on its own
    # and the collision path is never reached by accident. Freeze the clock to reach it.
    import cadence.cli as cli

    frozen = datetime(2026, 8, 23, 3, 0, 0, tzinfo=UTC)

    class FrozenClock:
        @staticmethod
        def now(tz: object = None) -> datetime:
            return frozen

    monkeypatch.setattr(cli, "datetime", FrozenClock)
    first = _run(tmp_path, "g", 1)
    assert (first / "manifest.json").is_file()
    with pytest.raises(FileExistsError):
        _run(tmp_path, "g", 1)


def test_the_manifest_records_the_scenario_content_hashes(tmp_path):
    manifest = json.loads((_run(tmp_path, "f", 1) / "manifest.json").read_text())
    assert len(manifest["network_sha256"]) == 64
    assert len(manifest["demand_sha256"]) == 64
    assert manifest["sumo_version"] == "1.27.1"
    assert manifest["seed"] == 1
```

- [ ] **Step 10: Run the reproducibility tests**

Run: `uv run pytest tests/simulation/sumo/test_reproducibility.py -v`
Expected: 4 passed. `_run` must be called with a distinct name per run, since a run
directory can no longer be reused.

- [ ] **Step 11: Exercise the CLI end to end**

```bash
uv run cadence validate-scenario --scenario scenarios/s0_single_intersection/v1
uv run cadence run --scenario scenarios/s0_single_intersection/v1 --seed 1 --binding traci
```

Expected: validation prints `OK`, and the run prints a path containing `manifest.json` and
`events.parquet`.

- [ ] **Step 12: Run the whole gate**

Run: `make check`
Expected: ruff, mypy, the documentation checker, and every test green. **Paste the real
output.** Do not report success without it.

- [ ] **Step 13: Commit**

```bash
git add src/cadence/simulation/manifest.py src/cadence/simulation/validation.py src/cadence/cli.py pyproject.toml uv.lock tests/simulation/test_manifest.py tests/simulation/test_validation.py tests/simulation/sumo/test_reproducibility.py
git commit -m "feat: add run manifest, CLI, and reproducibility proof (AP-06)"
```

---

# Task 11: Wire the pre-commit hook and close M0

**Files:**
- Create: `.pre-commit-config.yaml`
- Modify: `docs/DIRECTION.md` — mark M0 complete, set M1 current

**Interfaces:**
- Consumes: `make check`
- Produces: a repository where the gate runs before every commit

- [ ] **Step 1: Write the pre-commit configuration**

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy --strict
        entry: uv run mypy
        language: system
        pass_filenames: false
        types: [python]
      - id: architecture
        name: architecture boundaries
        entry: uv run pytest tests/test_architecture.py -q
        language: system
        pass_filenames: false
        types: [python]
      - id: decisions
        name: decision registry
        entry: uv run python tools/check_decisions.py
        language: system
        pass_filenames: false
```

The SUMO integration tests are deliberately absent: they start real processes and are too
slow for a commit hook. `make check` runs them.

- [ ] **Step 2: Install and verify the hook**

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Expected: every hook passes.

- [ ] **Step 3: Prove the hook blocks a boundary violation**

```bash
printf '\nimport traci\n\nTRACI_PATH = traci.__file__\n' >> src/cadence/simulation/scenario.py
git add src/cadence/simulation/scenario.py
git commit -m "test: this commit must be rejected" ; echo "commit exit: $?"
git restore --staged src/cadence/simulation/scenario.py
git checkout src/cadence/simulation/scenario.py
```

Expected: a non-zero exit and no new commit, with `TID251` named in the output.

The injected import is *used* on purpose. A bare `import traci` is an unused import, and
the hook's `ruff check --fix` would silently delete it before `TID251` or the architecture
test ever saw it — the commit would still be rejected, but for the wrong reason, and the
demonstration would prove nothing.

- [ ] **Step 4: Update the direction document**

In `docs/DIRECTION.md` §1, change `Current milestone` to `M1 — Canonical State + Metrics`.
In the §2 table, change the M0 `State` cell from `current` to `done` and set M1 to
`current`.

- [ ] **Step 5: Run the gate one final time**

Run: `make check`
Expected: green. Paste the output.

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml docs/DIRECTION.md
git commit -m "chore: install pre-commit gate and close M0"
```

---

# Acceptance for M-1 + M0

From the spec, `PD-D02` M0 and the definition of done in
`research/CADENCE_SUMO_SIMULATION_RESEARCH.md` §9. M0 covers the harness items only; the
network-quality and controller items belong to M1 and M3.

| Criterion | Evidence |
|---|---|
| Deterministic SUMO launch and shutdown | `test_connection_starts_and_closes_cleanly`, `test_connection_closes_even_when_the_body_raises` |
| TraCI wrapper with no direct TraCI outside it | `test_only_the_binding_module_imports_the_simulator`, ruff `TID251` |
| Both bindings behave identically | `test_libsumo_produces_the_same_event_stream_as_traci` |
| Scenario config loader | `tests/simulation/test_scenario.py` |
| Seed wiring | `test_seed_overrides_the_scenario_default`, `test_the_same_seed_produces_an_identical_event_stream` |
| Raw state and event capture | `tests/simulation/test_events.py`, `test_vehicles_depart_and_arrive` |
| Teleport explicitly configured and logged | `test_teleport_threshold_is_explicit`, `EventKind.TELEPORT_STARTED` |
| Software and version metadata | `tests/simulation/test_manifest.py`, `tests/test_toolchain.py` |
| Same scenario runs repeatedly and reproducibly | `tests/simulation/sumo/test_reproducibility.py` |
| Scenario network validation available | `cadence validate-scenario`, `tests/simulation/test_validation.py` |
| No controller intelligence present | no `control/` package exists; `docs/DIRECTION.md` M2 and M3 are unstarted |

## Explicitly out of scope

`LaneState`, `MovementState`, `IntersectionState`, `NetworkState`, the metric registry,
queue metrics, the controller contract, the signal safety layer, OSM import, and any
controller. M1 and M2 are planned separately once the raw state that SUMO actually returns
has been observed rather than assumed.
