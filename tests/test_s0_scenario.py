import math
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from cadence.simulation.scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
S0_ROOT = REPO_ROOT / "scenarios" / "s0_single_intersection" / "v1"
TURNING_ROOT = REPO_ROOT / "scenarios" / "s0_turning" / "v1"

sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_s0_scenario import (  # noqa: E402
    TURNING_SCENARIO_YAML,
    _alignment,
    _unit_direction,
    approach_pairs,
    build_demand,
    build_network,
    build_turning_demand,
)


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
            "--net-file",
            str(S0_ROOT / "network.net.xml"),
            "--route-files",
            str(S0_ROOT / "demand.rou.xml"),
            "--end",
            "10",
            "--no-step-log",
            "true",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Error" not in result.stderr


class _FakeEdge:
    # Method names mirror sumolib.net.edge.Edge's own camelCase API: approach_pairs takes
    # this duck-typed, so the fake must match the real interface it stands in for.
    def __init__(self, edge_id: str, start: tuple[float, float], end: tuple[float, float]):
        self._id = edge_id
        self._shape = [start, end]

    def getID(self):  # noqa: N802
        return self._id

    def getShape(self):  # noqa: N802
        return self._shape


def test_unit_direction_rejects_a_zero_length_edge():
    with pytest.raises(ValueError, match="zero-length"):
        _unit_direction(_FakeEdge("e", (0.0, 0.0), (0.0, 0.0)))


def test_alignment_of_identical_headings_is_one():
    # _alignment is exercised indirectly by every approach_pairs test below; this pins its
    # own contract, the cosine of the angle between two edges' directions.
    edge = _FakeEdge("e", (0.0, 0.0), (10.0, 0.0))
    assert _alignment(_unit_direction(edge), edge) == pytest.approx(1.0)


def test_approach_pairs_rejects_an_alignment_below_the_minimum():
    # Incoming heads east; the only outgoing heads north. cos 90 deg = 0, far below the
    # straight-through threshold, so calling it straight-through would be a silent lie.
    incoming = _FakeEdge("in", (0.0, 0.0), (10.0, 0.0))
    outgoing = _FakeEdge("out", (10.0, 0.0), (10.0, 10.0))
    with pytest.raises(ValueError, match="no straight-through"):
        approach_pairs([incoming], [outgoing])


def test_approach_pairs_rejects_an_ambiguous_winner():
    # Two outgoing edges at plus and minus 20 degrees: both plausible, neither clearly the
    # straight-through one. Choosing either silently is the defect this guards.
    incoming = _FakeEdge("in", (0.0, 0.0), (10.0, 0.0))
    left = _FakeEdge(
        "l", (10.0, 0.0), (10.0 + math.cos(math.radians(20)), math.sin(math.radians(20)))
    )
    right = _FakeEdge(
        "r", (10.0, 0.0), (10.0 + math.cos(math.radians(-20)), math.sin(math.radians(-20)))
    )
    with pytest.raises(ValueError, match="ambiguous"):
        approach_pairs([incoming], [left, right])


def test_approach_pairs_accepts_a_clean_orthogonal_cross():
    incoming = _FakeEdge("in", (0.0, 0.0), (10.0, 0.0))
    straight = _FakeEdge("s", (10.0, 0.0), (20.0, 0.0))
    turn = _FakeEdge("t", (10.0, 0.0), (10.0, 10.0))
    assert approach_pairs([incoming], [straight, turn]) == [("in", "s")]


def test_approach_pairs_tolerates_mildly_noisy_geometry():
    # A real OSM approach is never exactly axis-aligned. Five degrees must still pair.
    incoming = _FakeEdge("in", (0.0, 0.0), (10.0, 0.0))
    straight = _FakeEdge(
        "s", (10.0, 0.0), (10.0 + math.cos(math.radians(5)), math.sin(math.radians(5)))
    )
    turn = _FakeEdge("t", (10.0, 0.0), (10.0, 10.0))
    assert approach_pairs([incoming], [straight, turn]) == [("in", "s")]


def test_both_scenarios_share_a_byte_identical_network():
    straight = (REPO_ROOT / "scenarios/s0_single_intersection/v1/network.net.xml").read_bytes()
    turning = (TURNING_ROOT / "network.net.xml").read_bytes()
    assert straight == turning


def test_the_turning_scenario_loads():
    config, paths = load_scenario(TURNING_ROOT)
    assert config.scenario_id == "s0_turning"
    assert paths.network.is_file() and paths.demand.is_file()


@pytest.mark.sumo
def test_the_generator_reproduces_the_committed_scenarios_byte_for_byte(tmp_path):
    # Spec §10.3 claims this; the only prior test compared two committed files to each
    # other and never invoked the generator. This actually runs it.
    straight_root = tmp_path / "s0_single_intersection" / "v1"
    turning_root = tmp_path / "s0_turning" / "v1"
    straight_root.mkdir(parents=True)
    turning_root.mkdir(parents=True)

    build_network(straight_root / "network.net.xml")
    build_network(turning_root / "network.net.xml")
    build_demand(straight_root / "network.net.xml", straight_root / "demand.rou.xml")
    build_turning_demand(turning_root / "demand.rou.xml")
    (turning_root / "scenario.yaml").write_text(TURNING_SCENARIO_YAML)

    for relative in ("network.net.xml", "demand.rou.xml"):
        generated = (straight_root / relative).read_bytes()
        committed = (S0_ROOT / relative).read_bytes()
        assert generated == committed, relative

    for relative in ("network.net.xml", "demand.rou.xml", "scenario.yaml"):
        generated = (turning_root / relative).read_bytes()
        committed = (TURNING_ROOT / relative).read_bytes()
        assert generated == committed, relative


def test_the_turning_demand_uses_every_movement():
    routes = ElementTree.parse(TURNING_ROOT / "demand.rou.xml").getroot()
    pairs = {tuple((route.get("edges") or "").split()) for route in routes.iter("route")}
    assert len(pairs) == 12, "four approaches times three movements"
    assert len({source for source, _target in pairs}) == 4
