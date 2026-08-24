import pytest

from cadence.simulation.state import SignalState
from cadence.simulation.sumo.signals import DOCUMENTED_LAMP_CHARACTERS, connection_id, decode_signal
from cadence.types import LaneId


@pytest.mark.parametrize(
    ("character", "expected"),
    [
        ("r", SignalState.RED),
        ("y", SignalState.YELLOW),
        ("u", SignalState.RED_YELLOW),
        ("G", SignalState.GREEN_PROTECTED),
        ("g", SignalState.GREEN_PERMISSIVE),
        ("s", SignalState.GREEN_STOP_THEN_GO),
        ("o", SignalState.OFF_YIELDING),
        ("O", SignalState.OFF_PRIORITY),
    ],
)
def test_every_documented_character_decodes(character, expected):
    assert decode_signal(character) == expected


def test_the_schema_permitted_but_undocumented_character_raises():
    # SUMO's XSD allows Y; its documented table does not describe it. Guessing here would
    # hand the M2 safety layer a value nobody verified.
    with pytest.raises(ValueError, match="Y"):
        decode_signal("Y")


def test_an_unknown_character_raises():
    with pytest.raises(ValueError):
        decode_signal("z")


def test_the_documented_alphabet_is_exactly_what_we_decode():
    assert set(DOCUMENTED_LAMP_CHARACTERS) == {"r", "y", "u", "G", "g", "s", "o", "O"}


def test_connection_id_is_the_ordered_lane_pair():
    made = connection_id(LaneId("top0A0_0"), LaneId("A0bottom0_0"))
    assert made == "top0A0_0|A0bottom0_0"


def test_connection_id_is_direction_sensitive():
    forward = connection_id(LaneId("a_0"), LaneId("b_0"))
    reverse = connection_id(LaneId("b_0"), LaneId("a_0"))
    assert forward != reverse


def test_only_the_three_green_states_permit_movement():
    permitting = {state for state in SignalState if state.permits_movement}
    assert permitting == {
        SignalState.GREEN_PROTECTED,
        SignalState.GREEN_PERMISSIVE,
        SignalState.GREEN_STOP_THEN_GO,
    }


def test_red_yellow_does_not_permit_movement():
    # u means "about to turn green". A controller reading it as green acts a phase early.
    assert not SignalState.RED_YELLOW.permits_movement
