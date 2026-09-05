import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from cadence.simulation.scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
S0_ROOT = REPO_ROOT / "scenarios" / "s0_single_intersection" / "v1"
TURNING_ROOT = REPO_ROOT / "scenarios" / "s0_turning" / "v1"
OVERSATURATED_ROOT = REPO_ROOT / "scenarios" / "s0_turning_oversaturated" / "v1"

sys.path.insert(0, str(REPO_ROOT / "tools"))

from build_s0_scenario import (  # noqa: E402
    OVERSATURATED_END_S,
    OVERSATURATED_PERIODS_S,
    OVERSATURATED_SCENARIO_YAML,
    OVERSATURATED_TIME_TO_TELEPORT_S,
    TURNING_PERIODS_S,
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


def test_all_scenarios_share_a_byte_identical_network():
    straight = (REPO_ROOT / "scenarios/s0_single_intersection/v1/network.net.xml").read_bytes()
    turning = (TURNING_ROOT / "network.net.xml").read_bytes()
    oversaturated = (OVERSATURATED_ROOT / "network.net.xml").read_bytes()
    assert straight == turning == oversaturated


def test_the_turning_scenario_loads():
    config, paths = load_scenario(TURNING_ROOT)
    assert config.scenario_id == "s0_turning"
    assert paths.network.is_file() and paths.demand.is_file()


def test_the_oversaturated_scenario_loads():
    config, paths = load_scenario(OVERSATURATED_ROOT)
    # TC-D01: a regime is a parameterised variant of s0_turning, not a separate network, so
    # the id keeps the network's defining prefix rather than becoming "s0_oversaturated".
    assert config.scenario_id == "s0_turning_oversaturated"
    assert "regime" in config.description
    assert paths.network.is_file() and paths.demand.is_file()


def test_the_oversaturated_scenario_makes_a_teleport_possible_before_the_horizon():
    # Inheriting time_to_teleport_s=300.0 against a 180 s horizon would make a teleport
    # structurally impossible (spec docs/specs/2026-08-27-m1b-metrics.md section 10.2).
    assert OVERSATURATED_TIME_TO_TELEPORT_S < OVERSATURATED_END_S


def test_the_oversaturated_periods_are_scaled_not_flattened():
    # Scaling keeps the ratios between TURNING_PERIODS_S entries -- a flattened demand would
    # destroy the asymmetry section 8's mutation-detection test relies on.
    scales = {
        TURNING_PERIODS_S[source][target] / period
        for source, targets in OVERSATURATED_PERIODS_S.items()
        for target, period in targets.items()
    }
    assert len(scales) == 1


def test_the_oversaturated_demand_keeps_the_design_asymmetry():
    # The comment beside TURNING_PERIODS_S: no two approaches share a total volume, and no
    # two movements within one approach share a period. Scaling every entry by the same
    # constant preserves both, and this is what makes a movement-mapping error detectable.
    for targets in OVERSATURATED_PERIODS_S.values():
        periods = list(targets.values())
        assert len(periods) == len(set(periods))
    approach_rates = {
        source: sum(1.0 / period for period in targets.values())
        for source, targets in OVERSATURATED_PERIODS_S.items()
    }
    assert len(approach_rates) == len(set(approach_rates.values()))


@pytest.mark.sumo
def test_the_generator_reproduces_the_committed_scenarios_byte_for_byte(tmp_path):
    # Spec §10.3 claims this; the only prior test compared two committed files to each
    # other and never invoked the generator. This actually runs it.
    straight_root = tmp_path / "s0_single_intersection" / "v1"
    turning_root = tmp_path / "s0_turning" / "v1"
    oversaturated_root = tmp_path / "s0_turning_oversaturated" / "v1"
    straight_root.mkdir(parents=True)
    turning_root.mkdir(parents=True)
    oversaturated_root.mkdir(parents=True)

    build_network(straight_root / "network.net.xml")
    build_network(turning_root / "network.net.xml")
    build_network(oversaturated_root / "network.net.xml")
    build_demand(straight_root / "network.net.xml", straight_root / "demand.rou.xml")
    build_turning_demand(turning_root / "demand.rou.xml")
    (turning_root / "scenario.yaml").write_text(TURNING_SCENARIO_YAML)
    build_turning_demand(
        oversaturated_root / "demand.rou.xml",
        periods_s=OVERSATURATED_PERIODS_S,
        depart_end_s=OVERSATURATED_END_S,
    )
    (oversaturated_root / "scenario.yaml").write_text(OVERSATURATED_SCENARIO_YAML)

    for relative in ("network.net.xml", "demand.rou.xml"):
        generated = (straight_root / relative).read_bytes()
        committed = (S0_ROOT / relative).read_bytes()
        assert generated == committed, relative

    for relative in ("network.net.xml", "demand.rou.xml", "scenario.yaml"):
        generated = (turning_root / relative).read_bytes()
        committed = (TURNING_ROOT / relative).read_bytes()
        assert generated == committed, relative

    for relative in ("network.net.xml", "demand.rou.xml", "scenario.yaml"):
        generated = (oversaturated_root / relative).read_bytes()
        committed = (OVERSATURATED_ROOT / relative).read_bytes()
        assert generated == committed, relative


def test_the_turning_demand_uses_every_movement():
    routes = ElementTree.parse(TURNING_ROOT / "demand.rou.xml").getroot()
    pairs = {tuple((route.get("edges") or "").split()) for route in routes.iter("route")}
    assert len(pairs) == 12, "four approaches times three movements"
    assert len({source for source, _target in pairs}) == 4


def test_the_oversaturated_demand_uses_every_movement():
    routes = ElementTree.parse(OVERSATURATED_ROOT / "demand.rou.xml").getroot()
    pairs = {tuple((route.get("edges") or "").split()) for route in routes.iter("route")}
    assert len(pairs) == 12, "four approaches times three movements"
    assert len({source for source, _target in pairs}) == 4


@pytest.mark.sumo
def test_the_oversaturated_fixture_behaves_the_way_m1b_measured_it(tmp_path):
    # Everything M1b's metrics are specified against was measured on this fixture, and until
    # now those numbers lived only in a provenance comment. A comment rots silently
    # (`CLAUDE.md` section 6); this is the same claim as a test.
    import polars as pl

    from cadence.cli import run_scenario
    from cadence.simulation.sumo.binding import BindingKind

    run_dir = run_scenario(
        REPO_ROOT / "scenarios" / "s0_turning_oversaturated" / "v1",
        tmp_path,
        seed=1,
        binding=BindingKind.LIBSUMO,
    )
    network = pl.read_parquet(run_dir / "state" / "network.parquet").sort("time_s")
    horizon = network.tail(1)
    trips = pl.read_parquet(run_dir / "evaluation" / "tripinfo.parquet")
    arrival = trips["arrival"].cast(pl.Float64)

    assert horizon["departed_total_veh"][0] == 361
    assert horizon["arrived_total_veh"][0] == 183
    assert horizon["active_veh"][0] == 178
    assert horizon["pending_insertion_veh"][0] == 349
    assert trips.height == 361
    assert (arrival >= 0).sum() == 183

    # ST-D26: the identity at every step, not only at the horizon, because a mid-run
    # divergence that closes again by the end is exactly what a horizon check cannot see.
    departed = network["departed_total_veh"]
    assert (departed - network["arrived_total_veh"] - network["active_veh"]).abs().max() == 0

    # It must not drain, or it exercises none of the censoring this milestone is about.
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["termination_reason"] == "horizon"

    teleports = pl.read_parquet(run_dir / "state" / "teleport.parquet")
    assert teleports.height == 13
    assert teleports["vehicle_id"].n_unique() == 13
    # --time-to-teleport.remove is pinned false, so every teleport returns its vehicle to the
    # network rather than deleting it. Unequal counts would break the identity above.
    events = pl.read_parquet(run_dir / "events.parquet")
    kinds = dict(events["kind"].value_counts().rows())
    assert kinds["teleport_started"] == kinds["teleport_ended"] == 13
