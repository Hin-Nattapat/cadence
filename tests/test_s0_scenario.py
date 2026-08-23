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
