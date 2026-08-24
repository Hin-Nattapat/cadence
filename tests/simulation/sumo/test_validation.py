from pathlib import Path

from cadence.simulation.scenario import ScenarioPaths, load_scenario
from cadence.simulation.sumo.validation import validate_network

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"


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
