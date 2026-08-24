"""The one place SUMO's lamp alphabet exists.

CONTRACT: a lamp character enters here and a SignalState leaves. Nothing downstream, in
code or in an artifact, ever holds a raw lamp string (ST-D04, ARCH section 13).
"""

from __future__ import annotations

from cadence.simulation.state import SignalState
from cadence.types import ConnectionId, LaneId

# Meanings from SUMO's Traffic Lights documentation. The permitted character
# set is fixed by SUMO's own data/xsd/types/base.xsd, which restricts a phase state to
# [ruyYgGoOs].
_BY_CHARACTER: dict[str, SignalState] = {
    "r": SignalState.RED,
    "y": SignalState.YELLOW,
    "u": SignalState.RED_YELLOW,
    "G": SignalState.GREEN_PROTECTED,
    "g": SignalState.GREEN_PERMISSIVE,
    "s": SignalState.GREEN_STOP_THEN_GO,
    "o": SignalState.OFF_YIELDING,
    "O": SignalState.OFF_PRIORITY,
}
DOCUMENTED_LAMP_CHARACTERS = frozenset(_BY_CHARACTER)


def decode_signal(character: str) -> SignalState:
    # GOTCHA: the XSD permits a ninth character, Y, that the documented table does not
    # describe. Raising is deliberate. The M2 safety layer acts on whatever this returns,
    # so a guess here becomes a signal decision nobody checked.
    try:
        return _BY_CHARACTER[character]
    except KeyError:
        raise ValueError(f"unknown SUMO lamp character: {character!r}") from None


def connection_id(from_lane: LaneId, to_lane: LaneId) -> ConnectionId:
    return ConnectionId(f"{from_lane}|{to_lane}")
