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
