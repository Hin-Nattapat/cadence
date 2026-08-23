from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "cadence"

# The single module permitted to import the simulator bindings (ARCH-D02).
BINDING_MODULE = SRC_ROOT / "simulation" / "sumo" / "binding.py"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
