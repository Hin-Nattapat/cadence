from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "cadence"
METRICS_ROOT = SRC_ROOT / "metrics"

# The single module permitted to import the simulator bindings (ARCH-D02).
BINDING_MODULE = SRC_ROOT / "simulation" / "sumo" / "binding.py"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def expected_movement_traversals() -> dict[str, int]:
    # The twelve integers the turning demand was built from (spec §10.3).
    # The total of 315 is invariant under every possible movement-mapping error; these are
    # not, and they are the only check that catches a swapped MovementId derivation.
    return {
        "top0A0->A0left0": 10,
        "top0A0->A0bottom0": 60,
        "top0A0->A0right0": 20,
        "right0A0->A0top0": 30,
        "right0A0->A0left0": 40,
        "right0A0->A0bottom0": 12,
        "bottom0A0->A0right0": 15,
        "bottom0A0->A0top0": 32,
        "bottom0A0->A0left0": 24,
        "left0A0->A0bottom0": 40,
        "left0A0->A0right0": 24,
        "left0A0->A0top0": 8,
    }


@pytest.fixture(scope="session")
def turning_topology(repo_root):
    from cadence.simulation.scenario import load_scenario
    from cadence.simulation.sumo.binding import BindingKind
    from cadence.simulation.sumo.connection import SumoConnection

    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        return connection.topology


# GOTCHA: this is the only conftest.py this repo can have. Tests import it as a plain module
# (`from conftest import SRC_ROOT`) via pythonpath=["tests"], so a second conftest.py anywhere
# under tests/ takes the name `conftest` at collection time and those imports break -- verified.
# Fixtures that would live in a per-directory conftest go here instead.
def _run_scenario_fixture(repo_root: Path, tmp_path_factory, scenario_id: str) -> Path:
    from cadence.cli import run_scenario
    from cadence.simulation.sumo.binding import BindingKind

    output_root = tmp_path_factory.mktemp(f"{scenario_id}_run")
    return run_scenario(
        repo_root / "scenarios" / scenario_id / "v1",
        output_root,
        seed=1,
        binding=BindingKind.LIBSUMO,
    )


@pytest.fixture(scope="session")
def turning_run_dir(repo_root, tmp_path_factory):
    return _run_scenario_fixture(repo_root, tmp_path_factory, "s0_turning")


@pytest.fixture(scope="session")
def oversaturated_run_dir(repo_root, tmp_path_factory):
    return _run_scenario_fixture(repo_root, tmp_path_factory, "s0_turning_oversaturated")
