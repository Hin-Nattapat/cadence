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
