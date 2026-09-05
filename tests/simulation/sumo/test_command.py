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


def test_a_vehicle_can_only_leave_by_arriving():
    # M1b's accounting is departed = arrived + still-active. Removal on collision or on a
    # long wait is a fourth outcome the identity has no term for, so neither is left to a
    # SUMO default. Both values here are SUMO's current defaults, so no run changes.
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert _flag(command, "--collision.action") == "teleport"
    assert _flag(command, "--time-to-teleport.remove") == "false"


def test_random_is_disabled_so_the_seed_governs():
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert _flag(command, "--random") == "false"


def test_command_is_deterministic():
    assert build_sumo_command(CONFIG, PATHS, seed=3) == build_sumo_command(CONFIG, PATHS, seed=3)


def test_a_negative_seed_is_rejected():
    with pytest.raises(ValueError, match="seed"):
        build_sumo_command(CONFIG, PATHS, seed=-1)


def test_the_command_asks_sumo_for_tripinfo(tmp_path):
    # ST-D18: M1b's trip metrics have no other source, and the flag was absent since M0.
    tripinfo_path = tmp_path / "tripinfo.xml"
    command = build_sumo_command(CONFIG, PATHS, seed=1, use_gui=False, tripinfo_path=tripinfo_path)
    assert "--tripinfo-output" in command
    assert str(tripinfo_path) in command
    # Without this SUMO writes no row for a vehicle still in the network when the run ends,
    # and under oversaturation that is exactly the most delayed trips.
    assert "--tripinfo-output.write-unfinished" in command


def test_tripinfo_is_omitted_when_no_path_is_given():
    command = build_sumo_command(CONFIG, PATHS, seed=1)
    assert "--tripinfo-output" not in command
