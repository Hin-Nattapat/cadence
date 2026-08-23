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
