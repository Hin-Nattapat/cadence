# M1a Canonical State and Ground-Truth Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CADENCE a canonical traffic state that controllers may consume, a privileged ground-truth stream they may not, and a run directory that records both so M1b can compute metrics offline without re-simulating.

**Architecture:** One extractor inside `simulation/sumo/` reads the live binding once per step and produces observable state; privileged turn intent is fetched by a separately named call. Domain types live outside `sumo/` and carry no simulator concepts. Everything reaches disk as Parquet under `topology/`, `state/`, and `ground_truth/`, partitioned along the same line as the type space.

**Tech Stack:** Python 3.12, frozen slotted dataclasses, `StrEnum`, polars, libsumo/traci via `simulation.sumo.binding`, pytest + hypothesis.

**Spec:** `docs/specs/2026-08-23-m1a-canonical-state.md` — read it before Task 1, **including §14**. That section lists thirteen defects two reviews found in an earlier draft of the spec, and this plan was rewritten from the revision. Two of the thirteen were invisible to reasoning and surfaced only by running something; §3 records the measurements every decision rests on.

## Global Constraints

- Units are part of the name: `length_m`, `time_s`, `speed_mps`, `queue_count_veh`, `occupancy_ratio` (0-1). Bare `length`, `speed`, `time`, `queue` are rejected (`PD-D04`).
- Identifiers are distinct types via `NewType`: `LaneId`, `EdgeId`, `MovementId`, `IntersectionId`, `PhaseId`, `ConnectionId`.
- Temporal scope is explicit: `halting_count_now`, `waiting_total_now_s`, `arrived_total_veh`.
- No `traci` or `libsumo` import outside `simulation/sumo/` (`ARCH-D02`). After Task 6, no `sumolib` either (`ST-D12`).
- No raw lamp string outside `simulation/sumo/` — in code or in an artifact (`ST-D04`, `ARCH §13`).
- Canonical state carries only quantities the simulator reports directly. Every derived **interpretive** quantity belongs to M1b; topology identity and observable traversal are derivations M1a owns (`ST-D17`, superseding `ST-D03`).
- No RL concepts, no controller, no reward anywhere in this plan (`AP-02`).
- Determinism: no wall-clock, no unseeded randomness, no dict-ordering dependence in Zone A (`AP-06`).
- Every numeric constant is a named constant with a provenance comment. No magic numbers.
- Comments default to none. A comment earns its place only as provenance, gotcha, decision, or module/interface contract. `Args:`/`Returns:` blocks are forbidden. A comment restating the code is a defect (`PD-D05`).
- `mypy --strict` covers `src` and `tools`. Ruff selects `E,F,W,I,N,UP,B,SIM,TID,ANN,RUF`, `line-length = 100`; `tools/**` is exempt only from `TID251`, `tests/**` from `ANN` and `TID251`. `RUF100` is on, so a `noqa` for an unselected rule fails.
- Write the failing test first, run it, watch it fail, then implement. A regression test that passes before the fix is worthless; say so in your report if you find one.
- `make check` must be green before every commit.

## File Structure

| File | Responsibility |
|---|---|
| `src/cadence/types.py` | modify: add `ConnectionId`, `MovementId` |
| `src/cadence/simulation/state.py` | new: `SignalState`, `LaneState`, `ConnectionState`, `MovementState`, `IntersectionState`, `NetworkState`, `Traversal`, `TeleportEvent`, `CanonicalTrafficState`. **`Traversal` and `TeleportEvent` live here, not in `events.py`**: a traversal is part of canonical state, `StepResult` needs `CanonicalTrafficState`, and defining them the other way round makes `state.py` and `events.py` import each other. Imports run one direction only, `events.py` → `state.py`. |
| `src/cadence/simulation/topology.py` | new: `TurnDirection`, `LaneInfo`, `ConnectionInfo`, `MovementDefinition`, `PhaseInfo`, `NetworkTopology` |
| `src/cadence/simulation/ground_truth.py` | new: `LaneTurnCount`, `SimulationGroundTruth` — the privileged space |
| `src/cadence/simulation/artifacts.py` | new: Parquet writers for `topology/`, `state/`, `ground_truth/` |
| `src/cadence/simulation/events.py` | modify: `Traversal`, `StepResult` grows |
| `src/cadence/simulation/manifest.py` | modify: run outcome, dirty digest |
| `src/cadence/simulation/sumo/signals.py` | new: the only decoder of SUMO's lamp alphabet |
| `src/cadence/simulation/sumo/topology_reader.py` | new: builds `NetworkTopology` from a live binding |
| `src/cadence/simulation/sumo/extract.py` | new: per-step state, traversals, ground truth |
| `src/cadence/simulation/sumo/validation.py` | moved from `simulation/validation.py` |
| `src/cadence/simulation/sumo/connection.py` | modify: `step()` carries state, `read_ground_truth()`, termination reason |
| `src/cadence/cli.py` | modify: write the new artifacts |
| `tools/build_s0_scenario.py` | modify: fix `_approach_pairs`, build both scenarios |
| `scenarios/s0_turning/v1/` | new: the turning fixture |

Ten tasks. Task 1 produces the fixture every later integration test needs, so it comes first even though it touches no `src/`. Task 6a is new: it records the three things the reviews found missing, without which M1b through M9 would have to re-run the simulation to answer questions the run directory is supposed to answer.

---

### Task 1: Fix `_approach_pairs` and generate `s0_turning/v1`

**Files:**
- Modify: `tools/build_s0_scenario.py`
- Create: `scenarios/s0_turning/v1/scenario.yaml`, `network.net.xml`, `demand.rou.xml` (generated)
- Test: `tests/test_s0_scenario.py`

**Interfaces:**
- Produces: a second scenario directory loadable by `load_scenario(Path("scenarios/s0_turning/v1"))`, with `scenario_id == "s0_turning"` and a `network.net.xml` byte-identical to `s0_single_intersection/v1`'s.

`docs/specs/2026-08-23-m1a-canonical-state.md` §10.2 and §10.3 govern this task. `docs/DIRECTION.md` §7 records `_approach_pairs` in bold as something that must be fixed before it is reused; generating this fixture reuses it.

- [ ] **Step 1: Write the failing tests for the geometry guards**

Add to `tests/test_s0_scenario.py`:

```python
import math

import pytest

from build_s0_scenario import _alignment, _unit_direction, approach_pairs


class _FakeEdge:
    def __init__(self, edge_id: str, start: tuple[float, float], end: tuple[float, float]):
        self._id = edge_id
        self._shape = [start, end]

    def getID(self):
        return self._id

    def getShape(self):
        return self._shape


def test_unit_direction_rejects_a_zero_length_edge():
    with pytest.raises(ValueError, match="zero-length"):
        _unit_direction(_FakeEdge("e", (0.0, 0.0), (0.0, 0.0)))


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
    left = _FakeEdge("l", (10.0, 0.0), (10.0 + math.cos(math.radians(20)), math.sin(math.radians(20))))
    right = _FakeEdge("r", (10.0, 0.0), (10.0 + math.cos(math.radians(-20)), math.sin(math.radians(-20))))
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
    straight = _FakeEdge("s", (10.0, 0.0), (10.0 + math.cos(math.radians(5)), math.sin(math.radians(5))))
    turn = _FakeEdge("t", (10.0, 0.0), (10.0, 10.0))
    assert approach_pairs([incoming], [straight, turn]) == [("in", "s")]
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_s0_scenario.py -q`
Expected: `ImportError` for `approach_pairs` — the current helper is `_approach_pairs` and takes a `sumolib.net.Net`.

- [ ] **Step 3: Rewrite the geometry helpers**

In `tools/build_s0_scenario.py`, replace `_unit_direction`, `_alignment`, and `_approach_pairs` with:

```python
# A straight-through movement must align with its approach to within 30 degrees. Anything
# looser starts labelling turns as through movements on an irregular junction.
MIN_STRAIGHT_ALIGNMENT = math.cos(math.radians(30.0))
# The winner must beat the runner-up by this much in cosine terms, or the pairing is a coin
# toss. 0.05 separates the 5-degree noise of a real approach from a genuine fork.
MIN_ALIGNMENT_MARGIN = 0.05


def _unit_direction(edge: sumolib.net.edge.Edge) -> tuple[float, float]:
    shape = edge.getShape()
    (start_x, start_y), (end_x, end_y) = shape[0], shape[-1]
    dx, dy = end_x - start_x, end_y - start_y
    norm = math.hypot(dx, dy)
    if norm == 0.0:
        raise ValueError(f"edge {edge.getID()} has zero-length geometry")
    return dx / norm, dy / norm


def _alignment(heading: tuple[float, float], edge: sumolib.net.edge.Edge) -> float:
    other = _unit_direction(edge)
    return heading[0] * other[0] + heading[1] * other[1]


def approach_pairs(
    incoming: list[sumolib.net.edge.Edge], outgoing: list[sumolib.net.edge.Edge]
) -> list[tuple[str, str]]:
    """Each incoming edge paired with its straight-through outgoing edge.

    Raises rather than guessing. A silently mislabelled through movement produces demand
    that looks correct and measures the wrong thing.
    """
    pairs: list[tuple[str, str]] = []
    for in_edge in sorted(incoming, key=lambda edge: edge.getID()):
        heading = _unit_direction(in_edge)
        scored = sorted(
            ((_alignment(heading, out), out.getID()) for out in outgoing), reverse=True
        )
        best_score, best_id = scored[0]
        if best_score < MIN_STRAIGHT_ALIGNMENT:
            raise ValueError(
                f"edge {in_edge.getID()} has no straight-through outgoing edge: "
                f"best alignment {best_score:.3f} < {MIN_STRAIGHT_ALIGNMENT:.3f}"
            )
        if len(scored) > 1 and best_score - scored[1][0] < MIN_ALIGNMENT_MARGIN:
            raise ValueError(
                f"edge {in_edge.getID()} has an ambiguous straight-through pairing: "
                f"{best_id} at {best_score:.3f} versus {scored[1][1]} at {scored[1][0]:.3f}"
            )
        pairs.append((in_edge.getID(), best_id))
    return pairs
```

Update the caller to pass the junction's edge lists:

```python
def _junction_pairs(net: sumolib.net.Net) -> list[tuple[str, str]]:
    junction = next(node for node in net.getNodes() if node.getType() == "traffic_light")
    return approach_pairs(list(junction.getIncoming()), list(junction.getOutgoing()))
```

Replace the `_approach_pairs(net)` call in `build_demand` with `_junction_pairs(net)`. Remove the now-unused `functools` import if Ruff reports it.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_s0_scenario.py -q`
Expected: all pass, including the four new geometry tests.

- [ ] **Step 5: Add the turning demand generator**

Add to `tools/build_s0_scenario.py`:

```python
TURNING_SCENARIO_ROOT = REPO_ROOT / "scenarios" / "s0_turning" / "v1"

# Departure period in seconds per (approach, outgoing) movement. Deliberately asymmetric:
# no two approaches share a volume and no two movements within an approach share a share,
# so a movement-mapping error cannot hide behind symmetry. Measured behaviour of this mix
# is recorded in the M1a spec section 10.3.
TURNING_PERIODS_S: dict[str, dict[str, float]] = {
    "top0A0": {"A0left0": 48.0, "A0bottom0": 8.0, "A0right0": 24.0},
    "right0A0": {"A0top0": 16.0, "A0left0": 12.0, "A0bottom0": 40.0},
    "bottom0A0": {"A0right0": 32.0, "A0top0": 15.0, "A0left0": 20.0},
    "left0A0": {"A0bottom0": 12.0, "A0right0": 20.0, "A0top0": 60.0},
}


def build_turning_demand(output: Path) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<routes>",
        f'    <vType id="car" accel="{CAR_ACCEL_MPS2}" decel="{CAR_DECEL_MPS2}" sigma="0.0" '
        f'length="{CAR_LENGTH_M}" maxSpeed="{CAR_MAX_SPEED_MPS}"/>',
    ]
    flows = [
        (source, target, period)
        for source, targets in TURNING_PERIODS_S.items()
        for target, period in targets.items()
    ]
    for index, (source, target, _period) in enumerate(flows):
        lines.append(f'    <route id="r{index}" edges="{source} {target}"/>')
    for index, (_source, _target, period) in enumerate(flows):
        lines.append(
            f'    <flow id="f{index}" route="r{index}" type="car" '
            f'begin="0.00" end="{DEPART_END_S:.2f}" period="{period:.2f}" departLane="free"/>'
        )
    lines.append("</routes>")
    output.write_text("\n".join(lines) + "\n")
```

Write the scenario descriptor as a literal so the two scenarios cannot drift apart by accident:

```python
TURNING_SCENARIO_YAML = """scenario_id: s0_turning
scenario_version: 1
description: >
  The s0_cross network under an asymmetric turning demand. Every controlled link carries
  traffic, and every approach lane serves two movements, so shared-lane queue attribution
  and turn-ratio estimation have something to measure. Integration testing only.
  Not for research claims.
network_file: network.net.xml
demand_file: demand.rou.xml
begin_s: 0.0
end_s: 600.0
step_length_s: 1.0
time_to_teleport_s: 300.0
default_seed: 1
"""
```

Extend `main()` to build both:

```python
def main() -> int:
    for root in (SCENARIO_ROOT, TURNING_SCENARIO_ROOT):
        root.mkdir(parents=True, exist_ok=True)
        build_network(root / "network.net.xml")
    build_demand(SCENARIO_ROOT / "network.net.xml", SCENARIO_ROOT / "demand.rou.xml")
    build_turning_demand(TURNING_SCENARIO_ROOT / "demand.rou.xml")
    (TURNING_SCENARIO_ROOT / "scenario.yaml").write_text(TURNING_SCENARIO_YAML)
    print(f"Wrote {SCENARIO_ROOT} and {TURNING_SCENARIO_ROOT}")
    return 0
```

- [ ] **Step 6: Generate the fixture and write its tests**

Run: `uv run python tools/build_s0_scenario.py`

Then add to `tests/test_s0_scenario.py`:

```python
TURNING_ROOT = REPO_ROOT / "scenarios" / "s0_turning" / "v1"


def test_both_scenarios_share_a_byte_identical_network():
    straight = (REPO_ROOT / "scenarios/s0_single_intersection/v1/network.net.xml").read_bytes()
    turning = (TURNING_ROOT / "network.net.xml").read_bytes()
    assert straight == turning


def test_the_turning_scenario_loads():
    config, paths = load_scenario(TURNING_ROOT)
    assert config.scenario_id == "s0_turning"
    assert paths.network.is_file() and paths.demand.is_file()


def test_the_turning_demand_uses_every_movement():
    routes = ElementTree.parse(TURNING_ROOT / "demand.rou.xml").getroot()
    pairs = {tuple((route.get("edges") or "").split()) for route in routes.iter("route")}
    assert len(pairs) == 12, "four approaches times three movements"
    assert len({source for source, _target in pairs}) == 4
```

Use whichever import names `tests/test_s0_scenario.py` already has for `REPO_ROOT`, `load_scenario`, and `ElementTree`; add only what is missing.

- [ ] **Step 7: Prove the generator is reproducible**

```bash
uv run python tools/build_s0_scenario.py
git status --short scenarios/
```

Expected: no modification to either scenario directory on a second run. If either file changes, the generator is not deterministic and that is a blocker — report it rather than committing.

- [ ] **Step 8: Run the full gate and commit**

```bash
make check
git add tools/build_s0_scenario.py tests/test_s0_scenario.py scenarios/s0_turning
git commit -m "feat(scenarios): add the s0_turning fixture and make its generator refuse to guess"
```

---

### Task 2: Identifiers and signal decoding

**Files:**
- Modify: `src/cadence/types.py`
- Create: `src/cadence/simulation/sumo/signals.py`
- Test: `tests/test_types.py`, `tests/simulation/sumo/test_signals.py`

**Interfaces:**
- Produces: `ConnectionId`, `MovementId` in `cadence.types`; `SignalState` in `cadence.simulation.state`; `decode_signal(character: str) -> SignalState` and `connection_id(from_lane: LaneId, to_lane: LaneId) -> ConnectionId` in `cadence.simulation.sumo.signals`.

`SignalState` lives in `simulation/state.py` because it is a domain type controllers consume. The decoder lives under `simulation/sumo/` because it is the only place a lamp character exists (`ST-D04`).

- [ ] **Step 1: Write the failing tests**

Create `tests/simulation/sumo/test_signals.py`:

```python
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
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/simulation/sumo/test_signals.py -q`
Expected: `ModuleNotFoundError: No module named 'cadence.simulation.sumo.signals'`.

- [ ] **Step 3: Add the identifiers**

In `src/cadence/types.py`, beside the existing `NewType` declarations:

```python
ConnectionId = NewType("ConnectionId", str)
MovementId = NewType("MovementId", str)
```

- [ ] **Step 4: Add `SignalState`**

Create `src/cadence/simulation/state.py` with only the enum for now; the rest arrives in Task 4:

```python
"""Canonical traffic state — what a controller is permitted to see.

CONTRACT: every field here is a quantity the simulator reports directly. Anything derived
carries an interpretation, and an interpretation carries a version, so it belongs to the
metric registry at M1b rather than here (ST-D17).
"""

from __future__ import annotations

from enum import StrEnum


class SignalState(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    RED_YELLOW = "red_yellow"
    GREEN_PROTECTED = "green_protected"
    GREEN_PERMISSIVE = "green_permissive"
    GREEN_STOP_THEN_GO = "green_stop_then_go"
    OFF_YIELDING = "off_yielding"
    OFF_PRIORITY = "off_priority"

    @property
    def permits_movement(self) -> bool:
        # PROVENANCE: SUMO's Traffic Lights documentation. G, g and s all let a vehicle
        # proceed; they differ in priority and in whether a stop is required first. This is
        # SUMO's classification, not the project's, so no adapter has to invent it and two
        # adapters cannot disagree about what counts as a go.
        return self in _PERMISSIVE


_PERMISSIVE = frozenset(
    {
        SignalState.GREEN_PROTECTED,
        SignalState.GREEN_PERMISSIVE,
        SignalState.GREEN_STOP_THEN_GO,
    }
)
```

Add to `tests/simulation/sumo/test_signals.py`:

```python
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
```

- [ ] **Step 5: Add the decoder**

Create `src/cadence/simulation/sumo/signals.py`:

```python
"""The one place SUMO's lamp alphabet exists.

CONTRACT: a lamp character enters here and a SignalState leaves. Nothing downstream, in
code or in an artifact, ever holds a raw lamp string (ST-D04, ARCH section 13).
"""

from __future__ import annotations

from cadence.simulation.state import SignalState
from cadence.types import ConnectionId, LaneId

# PROVENANCE: meanings from SUMO's Traffic Lights documentation. The permitted character
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
```

- [ ] **Step 6: Run and watch it pass**

Run: `uv run pytest tests/simulation/sumo/test_signals.py tests/test_types.py -q`
Expected: all pass.

- [ ] **Step 7: Run the full gate and commit**

The architecture test's lamp-string detector will now see `signals.py`. Confirm it still passes: the dictionary keys are single characters, below its three-character minimum, so they are not lamp-string literals.

```bash
make check
git add src/cadence/types.py src/cadence/simulation/state.py \
  src/cadence/simulation/sumo/signals.py tests/simulation/sumo/test_signals.py
git commit -m "feat(simulation): decode SUMO's lamp alphabet once, at the boundary"
```

---

### Task 3: Topology types and the reader

**Files:**
- Create: `src/cadence/simulation/topology.py`, `src/cadence/simulation/sumo/topology_reader.py`
- Test: `tests/simulation/test_topology.py`, `tests/simulation/sumo/test_topology_reader.py`

**Interfaces:**
- Consumes: `connection_id`, `ConnectionId`, `MovementId`, `LaneId`, `EdgeId`, `IntersectionId`.
- Produces: `TurnDirection`, `LaneInfo`, `ConnectionInfo`, `MovementDefinition`, `NetworkTopology`, `movement_id(from_edge, to_edge) -> MovementId`, and `read_topology(binding) -> NetworkTopology`.

This is `movement_definition_v1` (`ST-D06`). A `MovementId` is the ordered edge pair, not a TLS link index: the same junction converted with `--tls.group-signals` yields sixteen indices or eight, while the edge pair is unchanged (spec §3.3).

- [ ] **Step 1: Write the failing unit tests**

Create `tests/simulation/test_topology.py`:

```python
import pytest

from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId


def _connection(from_lane: str, to_lane: str, direction: TurnDirection, index: int):
    return ConnectionInfo(
        connection_id=ConnectionId(f"{from_lane}|{to_lane}"),
        intersection_id=IntersectionId("A0"),
        link_index=index,
        from_lane_id=LaneId(from_lane),
        to_lane_id=LaneId(to_lane),
        via_lane_id=LaneId(f":A0_{index}_0"),
        from_edge_id=EdgeId(from_lane.rsplit("_", 1)[0]),
        to_edge_id=EdgeId(to_lane.rsplit("_", 1)[0]),
        turn_direction=direction,
        movement_id=movement_id(
            EdgeId(from_lane.rsplit("_", 1)[0]), EdgeId(to_lane.rsplit("_", 1)[0])
        ),
    )


def test_movement_id_is_the_ordered_edge_pair():
    assert movement_id(EdgeId("top0A0"), EdgeId("A0bottom0")) == "top0A0->A0bottom0"


def test_a_movement_groups_every_lane_that_serves_it():
    # The straight-through movement is served from two lanes; both belong to one movement.
    connections = [
        _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1),
        _connection("top0A0_1", "A0bottom0_1", TurnDirection.STRAIGHT, 2),
        _connection("top0A0_0", "A0left0_0", TurnDirection.RIGHT, 0),
    ]
    movements = build_movements(connections)

    straight = movements[movement_id(EdgeId("top0A0"), EdgeId("A0bottom0"))]
    assert len(straight.connection_ids) == 2
    assert straight.turn_direction is TurnDirection.STRAIGHT
    assert len(movements) == 2


def test_a_movement_with_inconsistent_directions_is_rejected():
    # Two connections between the same edge pair must agree on what turn they are, or the
    # grouping rule is describing something the network does not.
    connections = [
        _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1),
        _connection("top0A0_1", "A0bottom0_1", TurnDirection.LEFT, 2),
    ]
    with pytest.raises(ValueError, match="disagree"):
        build_movements(connections)


def test_topology_indexes_by_identifier():
    lane = LaneInfo(
        lane_id=LaneId("top0A0_0"),
        edge_id=EdgeId("top0A0"),
        lane_index=0,
        length_m=189.6,
        max_speed_mps=13.89,
    )
    connection = _connection("top0A0_0", "A0bottom0_0", TurnDirection.STRAIGHT, 1)
    topology = NetworkTopology(
        lanes={lane.lane_id: lane},
        connections={connection.connection_id: connection},
        movements=build_movements([connection]),
    )
    assert topology.lanes[LaneId("top0A0_0")].length_m == 189.6
    assert topology.connections[connection.connection_id].link_index == 1
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/simulation/test_topology.py -q`
Expected: `ModuleNotFoundError: No module named 'cadence.simulation.topology'`.

- [ ] **Step 3: Write the topology types**

Create `src/cadence/simulation/topology.py`. It imports `SignalState` from
`cadence.simulation.state`, which Task 2 created:

```python
"""Static network structure, read once when a run opens.

CONTRACT: a movement is the ordered edge pair, and a TLS link index is recorded but is not
an identity. The same junction converted with --tls.group-signals yields a different index
set while the edge pair is unchanged, so a metric keyed on the index cannot be compared
across two conversions of one site (ST-D05, ST-D06).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, MovementId


class TurnDirection(StrEnum):
    STRAIGHT = "straight"
    TURN = "turn"
    TURN_LEFTHAND = "turn_lefthand"
    LEFT = "left"
    RIGHT = "right"
    PARTIALLY_LEFT = "partially_left"
    PARTIALLY_RIGHT = "partially_right"


@dataclass(frozen=True, slots=True)
class LaneInfo:
    lane_id: LaneId
    edge_id: EdgeId
    lane_index: int
    length_m: float
    max_speed_mps: float


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    connection_id: ConnectionId
    intersection_id: IntersectionId
    link_index: int
    from_lane_id: LaneId
    to_lane_id: LaneId
    via_lane_id: LaneId
    from_edge_id: EdgeId
    to_edge_id: EdgeId
    turn_direction: TurnDirection
    movement_id: MovementId


@dataclass(frozen=True, slots=True)
class MovementDefinition:
    movement_id: MovementId
    from_edge_id: EdgeId
    to_edge_id: EdgeId
    turn_direction: TurnDirection
    connection_ids: tuple[ConnectionId, ...]


@dataclass(frozen=True, slots=True)
class PhaseInfo:
    intersection_id: IntersectionId
    program_id: str
    phase_index: int
    duration_s: float
    min_duration_s: float
    max_duration_s: float
    signals: tuple[SignalState, ...]


@dataclass(frozen=True, slots=True)
class NetworkTopology:
    lanes: Mapping[LaneId, LaneInfo]
    connections: Mapping[ConnectionId, ConnectionInfo]
    movements: Mapping[MovementId, MovementDefinition]
    phases: tuple[PhaseInfo, ...]


def movement_id(from_edge: EdgeId, to_edge: EdgeId) -> MovementId:
    return MovementId(f"{from_edge}->{to_edge}")


def build_movements(
    connections: Iterable[ConnectionInfo],
) -> Mapping[MovementId, MovementDefinition]:
    grouped: dict[MovementId, list[ConnectionInfo]] = defaultdict(list)
    for connection in connections:
        grouped[connection.movement_id].append(connection)

    movements: dict[MovementId, MovementDefinition] = {}
    for identifier, members in sorted(grouped.items()):
        directions = {member.turn_direction for member in members}
        if len(directions) > 1:
            raise ValueError(
                f"connections of movement {identifier} disagree on turn direction: "
                + ", ".join(sorted(direction.value for direction in directions))
            )
        first = members[0]
        movements[identifier] = MovementDefinition(
            movement_id=identifier,
            from_edge_id=first.from_edge_id,
            to_edge_id=first.to_edge_id,
            turn_direction=first.turn_direction,
            connection_ids=tuple(sorted(member.connection_id for member in members)),
        )
    return movements
```

- [ ] **Step 4: Run and watch the unit tests pass**

Run: `uv run pytest tests/simulation/test_topology.py -q`
Expected: all four pass.

- [ ] **Step 5: Write the failing reader test**

Create `tests/simulation/sumo/test_topology_reader.py`:

```python
import pytest

from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.topology_reader import read_topology
from cadence.simulation.topology import TurnDirection
from cadence.types import LaneId

TURNING = "scenarios/s0_turning/v1"


@pytest.fixture
def topology(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        return connection.topology


@pytest.mark.sumo
def test_every_controlled_connection_is_read(topology):
    assert len(topology.connections) == 16


@pytest.mark.sumo
def test_connections_collapse_to_twelve_movements(topology):
    # Four approaches times three turns. Sixteen links, twelve movements: the straight
    # movement of each approach is served from two lanes.
    assert len(topology.movements) == 12


@pytest.mark.sumo
def test_a_shared_lane_serves_two_movements(topology):
    shared = LaneId("top0A0_0")
    serving = {
        connection.movement_id
        for connection in topology.connections.values()
        if connection.from_lane_id == shared
    }
    assert len(serving) == 2, "S0's approach lanes each serve a turn and a through movement"


@pytest.mark.sumo
def test_turn_direction_comes_from_sumo(topology):
    directions = {connection.turn_direction for connection in topology.connections.values()}
    assert directions == {TurnDirection.RIGHT, TurnDirection.STRAIGHT, TurnDirection.LEFT}


@pytest.mark.sumo
def test_lane_geometry_is_recorded(topology):
    lane = topology.lanes[LaneId("top0A0_0")]
    assert lane.edge_id == "top0A0"
    assert lane.lane_index == 0
    assert lane.length_m > 0.0
    assert lane.max_speed_mps > 0.0


@pytest.mark.sumo
def test_no_internal_lane_is_recorded(topology):
    assert not [lane for lane in topology.lanes if lane.startswith(":")]


@pytest.mark.sumo
def test_the_signal_program_is_recorded(topology):
    # Without this, phase_index is an integer with no meaning, min and max green are
    # recoverable from nothing, and a phase that is never served leaves no trace at all -
    # which is the starvation case the spec flags as needing a test (ST-D19).
    assert {phase.phase_index for phase in topology.phases} == {0, 1, 2, 3}
    assert all(phase.duration_s > 0 for phase in topology.phases)
    assert all(len(phase.signals) == 16 for phase in topology.phases)
    assert any(
        signal.permits_movement for phase in topology.phases for signal in phase.signals
    )
```

The tests take the topology from `connection.topology`, which `__enter__` builds. **Do not add a `binding` property.** Task 3's review found that one lets any holder of a connection call `connection.binding.trafficlight.setPhase(...)` while the architecture test, which scans imports rather than method calls, sees nothing. Where a test genuinely needs to step the simulator before `step()` exists, reach `connection._binding` as `test_connection_lifecycle.py` already does: tests are outside the scanned tree, and a private attribute is a visible choice rather than a public route.

- [ ] **Step 6: Write the reader**

Create `src/cadence/simulation/sumo/topology_reader.py`:

```python
"""Builds the canonical network topology from a live simulator binding.

GOTCHA: this reads topology from traci rather than sumolib on purpose.
trafficlight.getControlledLinks returns the link-index-to-lane-triple mapping and
lane.getLinks carries the direction character, so the extraction path needs no second SUMO
surface (ST-D12).
"""

from __future__ import annotations

from types import ModuleType

from cadence.simulation.sumo.signals import connection_id
from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import EdgeId, IntersectionId, LaneId

# PROVENANCE: the LINKDIR_* constants in sumolib.net.connection, which that module records
# as taken from sumo/src/utils/xml/SUMOXMLDefinitions.cpp. Read from SUMO rather than
# recomputed from geometry, so the project holds no second opinion on what a left turn is.
_BY_DIRECTION_CHARACTER: dict[str, TurnDirection] = {
    "s": TurnDirection.STRAIGHT,
    "t": TurnDirection.TURN,
    "T": TurnDirection.TURN_LEFTHAND,
    "l": TurnDirection.LEFT,
    "r": TurnDirection.RIGHT,
    "L": TurnDirection.PARTIALLY_LEFT,
    "R": TurnDirection.PARTIALLY_RIGHT,
}

# Index of the outgoing lane and of the direction character in a traci lane.getLinks tuple:
# (toLane, hasPrio, isOpen, hasFoe, viaLane, state, direction, length).
_LINK_TO_LANE = 0
_LINK_DIRECTION = 6


def _turn_direction(character: str) -> TurnDirection:
    try:
        return _BY_DIRECTION_CHARACTER[character]
    except KeyError:
        raise ValueError(f"unknown SUMO link direction: {character!r}") from None


def _edge_and_index(lane_id: str) -> tuple[EdgeId, int]:
    # GOTCHA: SUMO composes a lane id as "<edge>_<index>" and exposes no getter for the
    # index. Splitting on the last underscore is the documented composition, not a guess.
    edge, _, index = lane_id.rpartition("_")
    return EdgeId(edge), int(index)


def read_topology(binding: ModuleType) -> NetworkTopology:
    lanes = {
        LaneId(lane_id): LaneInfo(
            lane_id=LaneId(lane_id),
            edge_id=_edge_and_index(lane_id)[0],
            lane_index=_edge_and_index(lane_id)[1],
            length_m=float(binding.lane.getLength(lane_id)),
            max_speed_mps=float(binding.lane.getMaxSpeed(lane_id)),
        )
        for lane_id in sorted(binding.lane.getIDList())
        if not lane_id.startswith(":")
    }

    connections: dict[str, ConnectionInfo] = {}
    phases: list[PhaseInfo] = []
    for tls_id in sorted(binding.trafficlight.getIDList()):
        logic = binding.trafficlight.getAllProgramLogics(tls_id)[0]
        for phase_index, phase in enumerate(logic.phases):
            phases.append(
                PhaseInfo(
                    intersection_id=IntersectionId(tls_id),
                    program_id=str(logic.programID),
                    phase_index=phase_index,
                    duration_s=float(phase.duration),
                    min_duration_s=float(phase.minDur),
                    max_duration_s=float(phase.maxDur),
                    # The phase's state is a lamp string, decoded before it leaves this
                    # package. That is what keeps ST-D04 true of the artifacts as well as
                    # the code.
                    signals=tuple(decode_signal(character) for character in phase.state),
                )
            )
        for index, group in enumerate(binding.trafficlight.getControlledLinks(tls_id)):
            for from_lane, to_lane, via_lane in group:
                directions = {
                    link[_LINK_TO_LANE]: link[_LINK_DIRECTION]
                    for link in binding.lane.getLinks(from_lane)
                }
                from_edge, _ = _edge_and_index(from_lane)
                to_edge, _ = _edge_and_index(to_lane)
                identifier = connection_id(LaneId(from_lane), LaneId(to_lane))
                connections[identifier] = ConnectionInfo(
                    connection_id=identifier,
                    intersection_id=IntersectionId(tls_id),
                    link_index=index,
                    from_lane_id=LaneId(from_lane),
                    to_lane_id=LaneId(to_lane),
                    via_lane_id=LaneId(via_lane),
                    from_edge_id=from_edge,
                    to_edge_id=to_edge,
                    turn_direction=_turn_direction(directions[to_lane]),
                    movement_id=movement_id(from_edge, to_edge),
                )

    return NetworkTopology(
        lanes=MappingProxyType(lanes),
        connections=MappingProxyType(connections),
        movements=MappingProxyType(dict(build_movements(connections.values()))),
        phases=tuple(phases),
    )
```

In `src/cadence/simulation/sumo/connection.py`, expose the binding:

```python
    @property
    def binding(self) -> ModuleType:
        return self._require_open()
```

- [ ] **Step 7: Run the reader tests**

Run: `uv run pytest tests/simulation/sumo/test_topology_reader.py -q`
Expected: seven pass. If `test_connections_collapse_to_twelve_movements` reports a different number, do not adjust the expectation — the movement grouping is wrong and that is the finding.

- [ ] **Step 8: Run the full gate and commit**

```bash
make check
git add src/cadence/simulation/topology.py src/cadence/simulation/sumo/topology_reader.py \
  src/cadence/simulation/sumo/connection.py tests/simulation/test_topology.py \
  tests/simulation/sumo/test_topology_reader.py
git commit -m "feat(simulation): read network topology and group connections into movements"
```

---

### Task 4: Canonical state and the per-step extractor

**Files:**
- Modify: `src/cadence/simulation/state.py`
- Create: `src/cadence/simulation/sumo/extract.py`
- Test: `tests/simulation/test_state.py`, `tests/simulation/sumo/test_extract.py`

**Interfaces:**
- Consumes: `NetworkTopology`, `decode_signal`, `connection_id`, `SignalState`.
- Produces: `LaneState`, `ConnectionState`, `IntersectionState`, `NetworkState`, `CanonicalTrafficState`; `StateExtractor(topology)` with `extract(binding, time_s, events) -> CanonicalTrafficState`.

- [ ] **Step 1: Write the failing state tests**

Create `tests/simulation/test_state.py`:

```python
import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    NetworkState,
    SignalState,
)
from cadence.types import ConnectionId, IntersectionId, LaneId


def _lane(**overrides):
    fields = {
        "lane_id": LaneId("top0A0_0"),
        "vehicle_count_veh": 3,
        "halting_count_veh": 2,
        "mean_speed_mps": 4.2,
        "occupancy_ratio": 0.15,
        "waiting_total_now_s": 8.0,
    }
    fields.update(overrides)
    return LaneState(**fields)


def test_lane_state_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _lane().vehicle_count_veh = 99


def test_canonical_state_carries_no_derived_quantity():
    # ST-D17: anything derived and interpretive belongs to M1b. If one of these ever
    # appears here, the M1a/M1b line has moved and the spec has to move with it.
    forbidden = {"queue_length_m", "storage_capacity_veh", "available_storage_ratio"}
    present = {field.name for field in dataclasses.fields(LaneState)}
    assert not present & forbidden


@given(
    vehicles=st.integers(min_value=0, max_value=200),
    halting=st.integers(min_value=0, max_value=200),
)
def test_halting_never_exceeds_vehicle_count(vehicles, halting):
    # A physical invariant, asserted on the constructor's own guard rather than on SUMO.
    if halting > vehicles:
        with pytest.raises(ValueError, match="halting"):
            _lane(vehicle_count_veh=vehicles, halting_count_veh=halting)
    else:
        assert _lane(vehicle_count_veh=vehicles, halting_count_veh=halting)


@given(occupancy=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False))
def test_occupancy_stays_within_zero_and_one(occupancy):
    if 0.0 <= occupancy <= 1.0:
        assert _lane(occupancy_ratio=occupancy)
    else:
        with pytest.raises(ValueError, match="occupancy"):
            _lane(occupancy_ratio=occupancy)


def test_state_indexes_by_identifier():
    lane = _lane()
    intersection = IntersectionState(
        intersection_id=IntersectionId("A0"),
        program_id="0",
        phase_index=0,
        phase_elapsed_s=12.0,
        connections=(
            ConnectionState(
                connection_id=ConnectionId("top0A0_0|A0bottom0_0"),
                signal=SignalState.GREEN_PROTECTED,
            ),
        ),
    )
    state = CanonicalTrafficState(
        time_s=42.0,
        topology=_empty_topology(),
        lanes={lane.lane_id: lane},
        movements={},
        intersections={intersection.intersection_id: intersection},
        traversals=(),
        network=NetworkState(
            active_veh=5,
            pending_insertion_veh=0,
            departed_total_veh=10,
            arrived_total_veh=5,
            teleport_total_veh=0,
        ),
    )
    assert state.lanes[LaneId("top0A0_0")].halting_count_veh == 2
    assert state.intersections[IntersectionId("A0")].connections[0].signal is SignalState.GREEN_PROTECTED
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/simulation/test_state.py -q`
Expected: `ImportError` for `LaneState`.

- [ ] **Step 3: Add the state types**

Append to `src/cadence/simulation/state.py`:

```python
from collections.abc import Mapping
from dataclasses import dataclass

from cadence.types import ConnectionId, IntersectionId, LaneId


@dataclass(frozen=True, slots=True)
class LaneState:
    lane_id: LaneId
    vehicle_count_veh: int
    halting_count_veh: int
    mean_speed_mps: float
    occupancy_ratio: float
    waiting_total_now_s: float

    def __post_init__(self) -> None:
        # These are physical impossibilities, not preferences. Catching them here turns a
        # simulator or extraction defect into a loud failure instead of a plausible number
        # that reaches a report.
        if self.halting_count_veh > self.vehicle_count_veh:
            raise ValueError(
                f"lane {self.lane_id}: halting {self.halting_count_veh} exceeds "
                f"vehicle count {self.vehicle_count_veh}"
            )
        if not 0.0 <= self.occupancy_ratio <= 1.0:
            raise ValueError(f"lane {self.lane_id}: occupancy {self.occupancy_ratio} outside [0, 1]")


@dataclass(frozen=True, slots=True)
class ConnectionState:
    connection_id: ConnectionId
    signal: SignalState


@dataclass(frozen=True, slots=True)
class IntersectionState:
    intersection_id: IntersectionId
    program_id: str
    phase_index: int
    phase_elapsed_s: float
    connections: tuple[ConnectionState, ...]


@dataclass(frozen=True, slots=True)
class NetworkState:
    active_veh: int
    pending_insertion_veh: int
    departed_total_veh: int
    arrived_total_veh: int
    teleport_total_veh: int


class TeleportKind(StrEnum):
    STARTED = "started"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class Traversal:
    time_s: float
    vehicle_id: VehicleId
    movement_id: MovementId
    # None when the vehicle changed lane inside the junction, or when its exit lane is one
    # of two the approach serves on that edge. The movement always resolves; the connection
    # does not, and a null says so rather than the vehicle disappearing (ST-D16).
    connection_id: ConnectionId | None


@dataclass(frozen=True, slots=True)
class TeleportEvent:
    time_s: float
    vehicle_id: VehicleId
    from_lane_id: LaneId | None
    kind: TeleportKind


@dataclass(frozen=True, slots=True)
class MovementState:
    movement_id: MovementId
    # Positionally aligned with topology.movements[movement_id].connection_ids, so an
    # adapter can ask which connection shows which signal, not merely whether any is green.
    signals: tuple[SignalState, ...]


@dataclass(frozen=True, slots=True)
class CanonicalTrafficState:
    time_s: float
    topology: NetworkTopology
    lanes: Mapping[LaneId, LaneState]
    movements: Mapping[MovementId, MovementState]
    intersections: Mapping[IntersectionId, IntersectionState]
    traversals: tuple[Traversal, ...]
    network: NetworkState
```

`topology` is the same immutable object every step, held by reference. Without it the
movement layer is decorative: `MovementState` names a movement, `LaneState` names a lane,
and nothing joins them, so an M8 adapter cannot reach the lanes incident to a movement and
ends up in `topology/connection.parquet` — not canonical state — or in
`SimulationGroundTruth`, which is the outcome `ST-D15` exists to prevent. `LaneState`
carries no `edge_id` for the same reason: `topology.lanes[lane_id].edge_id` answers it, and
a duplicated field can disagree.

Add:

```python
def test_canonical_state_can_reach_a_movements_incident_lanes():
    # The check that ST-D15 is real rather than decorative. If this needs anything outside
    # CanonicalTrafficState, an M8 adapter needs it too, and it will take it from wherever
    # it can get it.
    state = _state_with_topology()
    movement = next(iter(state.movements.values()))
    definition = state.topology.movements[movement.movement_id]
    lanes = {
        state.topology.connections[connection_id].from_lane_id
        for connection_id in definition.connection_ids
    }
    assert lanes and all(lane_id in state.lanes for lane_id in lanes)
```

`MovementState` carries no queue on purpose (`ST-D15`, spec §5.2.1): a movement queue needs
an attribution rule for shared lanes, that rule is an interpretation, and interpretations
are versioned at M1b. What it carries is what a controller needs to know whether a movement
is served at all, and it is measured rather than interpreted.

`lanes` excludes SUMO's internal (`:junction`) lanes. `traversals` holds what the step just
produced; it lives in canonical state so an online turn-ratio estimator at M8 runs on
observable data instead of reaching for `SimulationGroundTruth`.

Add to `tests/simulation/test_state.py`:

```python
def test_a_movement_reports_a_signal_for_every_contributing_connection():
    movement = MovementState(
        movement_id=MovementId("top0A0->A0bottom0"),
        signals=(SignalState.GREEN_PROTECTED, SignalState.RED),
    )
    assert len(movement.signals) == 2
    assert any(signal.permits_movement for signal in movement.signals)


def test_movement_state_carries_no_queue():
    # ST-D15/ST-D17: a movement queue needs a shared-lane attribution rule, which is an
    # interpretation, which is M1b's. A queue field here means the line has moved.
    names = {field.name for field in dataclasses.fields(MovementState)}
    assert not names & {"queue_count_veh", "queue_length_m", "turn_ratio"}
```

- [ ] **Step 4: Run and watch it pass**

Run: `uv run pytest tests/simulation/test_state.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing extractor test**

Create `tests/simulation/sumo/test_extract.py`:

```python
import pytest

from cadence.simulation.events import EventKind, SimulationEvent
from cadence.simulation.scenario import load_scenario
from cadence.simulation.state import SignalState
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection
from cadence.simulation.sumo.extract import StateExtractor
from cadence.simulation.sumo.topology_reader import read_topology
from cadence.types import IntersectionId, VehicleId

TURNING = "scenarios/s0_turning/v1"


@pytest.mark.sumo
def test_the_extractor_reports_every_lane_and_connection(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        topology = connection.topology
        extractor = StateExtractor(topology)
        for _ in range(60):
            connection._binding.simulationStep()
        state = extractor.extract(connection._binding, time_s=60.0, events=(), traversals=())

    assert set(state.lanes) == set(topology.lanes)
    assert set(state.movements) == set(topology.movements)
    assert state.topology is topology, "ST-D15: the movement layer has to be reachable"
    for movement_id, movement in state.movements.items():
        assert len(movement.signals) == len(topology.movements[movement_id].connection_ids)
    intersection = state.intersections[IntersectionId("A0")]
    assert len(intersection.connections) == len(topology.connections)
    assert all(isinstance(item.signal, SignalState) for item in intersection.connections)


@pytest.mark.sumo
def test_phase_elapsed_never_exceeds_its_phase(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        topology = connection.topology
        extractor = StateExtractor(topology)
        logic = connection._binding.trafficlight.getAllProgramLogics("A0")[0]
        longest_s = max(phase.duration for phase in logic.phases)
        for step in range(1, 200):
            connection._binding.simulationStep()
            state = extractor.extract(
                connection._binding, time_s=float(step), events=(), traversals=()
            )
            assert state.intersections[IntersectionId("A0")].phase_elapsed_s <= longest_s


def test_totals_accumulate_across_steps():
    # No simulator needed: the accumulator is the part that must not be trusted to SUMO,
    # because getDepartedNumber reports the step, not a running total.
    extractor = StateExtractor.__new__(StateExtractor)
    extractor._departed_total_veh = 0
    extractor._arrived_total_veh = 0
    extractor._teleport_total_veh = 0

    first = (SimulationEvent(1.0, EventKind.DEPARTED, VehicleId("a")),)
    second = (
        SimulationEvent(2.0, EventKind.DEPARTED, VehicleId("b")),
        SimulationEvent(2.0, EventKind.ARRIVED, VehicleId("a")),
        SimulationEvent(2.0, EventKind.TELEPORT_STARTED, VehicleId("b")),
    )
    extractor._accumulate(first)
    extractor._accumulate(second)

    assert extractor._departed_total_veh == 2
    assert extractor._arrived_total_veh == 1
    assert extractor._teleport_total_veh == 1
```

- [ ] **Step 6: Write the extractor**

Create `src/cadence/simulation/sumo/extract.py`:

```python
"""Turns one simulator step into canonical state.

CONTRACT: everything this module returns is observable. Privileged information has its own
module and its own named call (ST-D01, ST-D09).
"""

from __future__ import annotations

from collections.abc import Iterable
from types import ModuleType

from cadence.simulation.events import EventKind, SimulationEvent
from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    NetworkState,
)
from cadence.simulation.sumo.signals import decode_signal
from cadence.simulation.topology import NetworkTopology
from cadence.types import IntersectionId, LaneId


class StateExtractor:
    """Holds the topology and the running totals SUMO does not keep."""

    def __init__(self, topology: NetworkTopology) -> None:
        self._topology = topology
        self._departed_total_veh = 0
        self._arrived_total_veh = 0
        self._teleport_total_veh = 0

    def _accumulate(self, events: Iterable[SimulationEvent]) -> None:
        # GOTCHA: simulation.getDepartedNumber() and getLoadedNumber() report the step just
        # taken, not a running total. Measured at t=120 on a run with over a hundred
        # departures behind it, both returned 0.
        for event in events:
            if event.kind is EventKind.DEPARTED:
                self._departed_total_veh += 1
            elif event.kind is EventKind.ARRIVED:
                self._arrived_total_veh += 1
            elif event.kind is EventKind.TELEPORT_STARTED:
                self._teleport_total_veh += 1

    def _lanes(self, binding: ModuleType) -> dict[LaneId, LaneState]:
        return {
            lane_id: LaneState(
                lane_id=lane_id,
                vehicle_count_veh=int(binding.lane.getLastStepVehicleNumber(lane_id)),
                halting_count_veh=int(binding.lane.getLastStepHaltingNumber(lane_id)),
                mean_speed_mps=float(binding.lane.getLastStepMeanSpeed(lane_id)),
                occupancy_ratio=float(binding.lane.getLastStepOccupancy(lane_id)),
                waiting_total_now_s=float(binding.lane.getWaitingTime(lane_id)),
            )
            for lane_id in self._topology.lanes
        }

    def _intersections(self, binding: ModuleType) -> dict[IntersectionId, IntersectionState]:
        by_intersection: dict[IntersectionId, IntersectionState] = {}
        for intersection_id in sorted({c.intersection_id for c in self._topology.connections.values()}):
            lamp_state = binding.trafficlight.getRedYellowGreenState(intersection_id)
            connections = tuple(
                ConnectionState(
                    connection_id=connection.connection_id,
                    signal=decode_signal(lamp_state[connection.link_index]),
                )
                for connection in sorted(
                    self._topology.connections.values(), key=lambda c: c.connection_id
                )
                if connection.intersection_id == intersection_id
            )
            by_intersection[intersection_id] = IntersectionState(
                intersection_id=intersection_id,
                program_id=str(binding.trafficlight.getProgram(intersection_id)),
                phase_index=int(binding.trafficlight.getPhase(intersection_id)),
                phase_elapsed_s=float(binding.trafficlight.getSpentDuration(intersection_id)),
                connections=connections,
            )
        return by_intersection

    def _movements(
        self, intersections: Mapping[IntersectionId, IntersectionState]
    ) -> Mapping[MovementId, MovementState]:
        # Positionally aligned with topology.movements[...].connection_ids, so an adapter
        # can ask which connection shows which signal rather than only whether any is green.
        by_connection = {
            connection.connection_id: connection.signal
            for intersection in intersections.values()
            for connection in intersection.connections
        }
        return MappingProxyType(
            {
                movement_id: MovementState(
                    movement_id=movement_id,
                    signals=tuple(
                        by_connection[connection_id]
                        for connection_id in definition.connection_ids
                    ),
                )
                for movement_id, definition in self._topology.movements.items()
            }
        )

    def extract(
        self,
        binding: ModuleType,
        time_s: float,
        events: Iterable[SimulationEvent],
        traversals: tuple[Traversal, ...],
    ) -> CanonicalTrafficState:
        self._accumulate(events)
        lanes = self._lanes(binding)
        intersections = self._intersections(binding)
        return CanonicalTrafficState(
            time_s=time_s,
            topology=self._topology,
            lanes=lanes,
            movements=self._movements(intersections),
            intersections=intersections,
            traversals=traversals,
            network=NetworkState(
                active_veh=int(binding.vehicle.getIDCount()),
                pending_insertion_veh=len(binding.simulation.getPendingVehicles()),
                departed_total_veh=self._departed_total_veh,
                arrived_total_veh=self._arrived_total_veh,
                teleport_total_veh=self._teleport_total_veh,
            ),
        )
```

- [ ] **Step 7: Run and watch it pass**

Run: `uv run pytest tests/simulation/sumo/test_extract.py -q`
Expected: three pass.

If `binding.vehicle.getIDCount()` is unavailable in this SUMO version, use `len(binding.vehicle.getIDList())` and record why in a comment. Do not silently substitute a different quantity.

- [ ] **Step 8: Run the full gate and commit**

```bash
make check
git add src/cadence/simulation/state.py src/cadence/simulation/sumo/extract.py \
  tests/simulation/test_state.py tests/simulation/sumo/test_extract.py
git commit -m "feat(simulation): extract canonical lane, intersection and network state"
```

---

### Task 5: Traversal detection

**Files:**
- Modify: `src/cadence/simulation/events.py`, `src/cadence/simulation/sumo/extract.py`, `src/cadence/simulation/sumo/connection.py`
- Test: `tests/simulation/sumo/test_extract.py`, `tests/simulation/sumo/test_connection.py`

**Interfaces:**
- Produces: `Traversal(time_s, vehicle_id, connection_id)` in `events.py`; `StepResult` grows `state` and `traversals`; `TraversalDetector(topology)` with `observe(binding, time_s) -> tuple[Traversal, ...]`.

Keyed on the `(incoming lane, outgoing **edge**)` transition (`ST-D16`, superseding `ST-D07`). Three keys were measured against the turning fixture's 315 departures:

```
via-lane presence           322 traversals   over-counts a mid-junction lane change
(from_lane, to_lane)        306 traversals   loses 9 that exit on another lane of the right edge
(from_lane, to_edge)        315 traversals   exact, 12/12 movements, 0 unmatched
```

The connection is recorded when the exit lane resolves to a declared one and left `None` otherwise — nine times in 315 here — so a consumer needing connection granularity sees exactly how often it is unavailable rather than inferring it from a shortfall.

- [ ] **Step 1: Write the failing unit test**

Add to `tests/simulation/sumo/test_extract.py`:

```python
from cadence.simulation.sumo.extract import TraversalDetector
from cadence.simulation.topology import NetworkTopology, build_movements


class _FakeVehicleApi:
    def __init__(self, lanes_by_step):
        self._lanes_by_step = lanes_by_step
        self._step = -1

    def advance(self):
        self._step += 1

    def getIDList(self):
        return tuple(self._lanes_by_step[self._step])

    def getLaneID(self, vehicle_id):
        return self._lanes_by_step[self._step][vehicle_id]


class _FakeBinding:
    def __init__(self, lanes_by_step):
        self.vehicle = _FakeVehicleApi(lanes_by_step)


def test_a_mid_junction_lane_change_produces_one_traversal(turning_topology):
    # The defect via-lane counting has: this vehicle is seen on two internal lanes and
    # would be counted twice. Keyed on the lane pair it is one traversal.
    steps = [
        {"v0": "top0A0_0"},
        {"v0": ":A0_1_0"},
        {"v0": ":A0_1_1"},
        {"v0": "A0bottom0_1"},
    ]
    binding = _FakeBinding(steps)
    detector = TraversalDetector(turning_topology)

    seen = []
    for index in range(len(steps)):
        binding.vehicle.advance()
        seen.extend(detector.observe(binding, time_s=float(index)))

    assert len(seen) == 1
    assert seen[0].vehicle_id == "v0"


def test_a_vehicle_that_never_leaves_its_approach_produces_none(turning_topology):
    steps = [{"v0": "top0A0_0"}, {"v0": "top0A0_0"}, {"v0": "top0A0_0"}]
    binding = _FakeBinding(steps)
    detector = TraversalDetector(turning_topology)

    seen = []
    for index in range(len(steps)):
        binding.vehicle.advance()
        seen.extend(detector.observe(binding, time_s=float(index)))

    assert seen == ()
```

Add a `turning_topology` fixture to `tests/conftest.py`, session-scoped so one SUMO start serves every test that needs it:

```python
@pytest.fixture(scope="session")
def turning_topology(repo_root):
    from cadence.simulation.scenario import load_scenario
    from cadence.simulation.sumo.binding import BindingKind
    from cadence.simulation.sumo.connection import SumoConnection
    from cadence.simulation.sumo.topology_reader import read_topology

    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        return connection.topology
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/simulation/sumo/test_extract.py -q -k traversal`
Expected: `ImportError` for `TraversalDetector`.

- [ ] **Step 3: Grow `StepResult`**

`Traversal`, `TeleportEvent` and `TeleportKind` already exist in `state.py` from Task 4 —
`CanonicalTrafficState` needed them, and defining them here instead would make `state.py`
and `events.py` import each other. In `src/cadence/simulation/events.py`, import them and
change `StepResult` to:

```python
@dataclass(frozen=True, slots=True)
class StepResult:
    time_s: float
    events: tuple[SimulationEvent, ...]
    state: CanonicalTrafficState
    teleports: tuple[TeleportEvent, ...]
    expected_remaining_veh: int
```

Import `CanonicalTrafficState` from `cadence.simulation.state`. Traversals live on `state`
and nowhere else; two copies of one fact with nothing asserting they agree is a defect
waiting for a reader to pick the stale one. `TeleportEvent` arrives in Task 6a — until then
the field is an empty tuple, and Task 6a's tests are what fill it.

- [ ] **Step 4: Add the detector**

Append to `src/cadence/simulation/sumo/extract.py`:

```python
class TraversalDetector:
    """Records a completed movement from the lane a vehicle left and the edge it reached.

    GOTCHA: neither via-lane presence nor the lane pair works. Via-lane presence counts a
    mid-junction lane change twice (322 for 315). The lane pair loses that same vehicle
    entirely (306 for 315), because it exits on a lane the pair does not name. The outgoing
    EDGE resolves in both cases, and a lane serves at most one connection to any given
    edge, so it is unique as well as complete.
    """

    def __init__(self, topology: NetworkTopology) -> None:
        self._by_movement_key: dict[tuple[LaneId, EdgeId], MovementId] = {}
        self._by_lane_pair: dict[tuple[LaneId, LaneId], ConnectionId] = {}
        for connection in topology.connections.values():
            key = (connection.from_lane_id, connection.to_edge_id)
            self._by_movement_key[key] = connection.movement_id
            self._by_lane_pair[(connection.from_lane_id, connection.to_lane_id)] = (
                connection.connection_id
            )
        self._incoming = {from_lane for from_lane, _edge in self._by_movement_key}
        self._lane_edge = {lane_id: info.edge_id for lane_id, info in topology.lanes.items()}
        self._last_lane: dict[str, LaneId] = {}
        self.unmatched_count = 0

    def observe(self, binding: ModuleType, time_s: float) -> tuple[Traversal, ...]:
        traversals: list[Traversal] = []
        active: set[str] = set()
        for vehicle_id in binding.vehicle.getIDList():
            active.add(vehicle_id)
            lane_id = LaneId(binding.vehicle.getLaneID(vehicle_id))
            previous = self._last_lane.get(vehicle_id)
            if lane_id == previous:
                continue
            # An internal lane is a waypoint, not a destination. Hold the approach: a
            # vehicle is usually seen on the via lane, so comparing against the immediately
            # preceding lane would almost never fire (spec section 3.5).
            if lane_id.startswith(":"):
                continue
            if previous in self._incoming:
                edge_id = self._lane_edge.get(lane_id)
                if edge_id == self._lane_edge.get(previous):
                    pass  # A lane change on the same approach is not a traversal.
                else:
                    movement = self._by_movement_key.get((previous, edge_id))
                    if movement is None:
                        # Counted, never silent: an undercount at M8 with multi-lane exits
                        # would otherwise look like light demand rather than a defect.
                        self.unmatched_count += 1
                    else:
                        traversals.append(
                            Traversal(
                                time_s=time_s,
                                vehicle_id=VehicleId(vehicle_id),
                                movement_id=movement,
                                connection_id=self._by_lane_pair.get((previous, lane_id)),
                            )
                        )
            self._last_lane[vehicle_id] = lane_id
        for gone in self._last_lane.keys() - active:
            del self._last_lane[gone]
        return tuple(traversals)

    def held_lane(self, vehicle_id: str) -> LaneId | None:
        return self._last_lane.get(vehicle_id)

    def forget(self, vehicle_ids: Iterable[str]) -> None:
        # GOTCHA: SUMO removes a stuck vehicle and reinserts it downstream. Without this the
        # detector compares the approach lane it is still holding against a lane the vehicle
        # never drove to, and either fabricates a traversal -- if that edge happens to be a
        # legal successor -- or trips the unmatched counter. s0_turning has zero teleports,
        # so M1a passes either way; regimes C and D are where it matters, and they are what
        # the project exists to study.
        for vehicle_id in vehicle_ids:
            self._last_lane.pop(vehicle_id, None)
```

Import `Traversal` and `VehicleId` at the top of the module. `SumoConnection.step()` calls
`forget(binding.simulation.getStartingTeleportIDList())` **before** `observe`, so a
teleported vehicle starts again from wherever it reappears.

Add the regression test, which needs a fixture that teleports — `s0_turning` does not:

```python
def test_a_teleported_vehicle_produces_no_traversal(turning_topology):
    # Approach lane held, vehicle reappears two edges downstream. Without forget() the
    # detector matches (top0A0_0, A0bottom0) and invents a crossing that never happened.
    detector = TraversalDetector(turning_topology)
    binding = _FakeBinding([{"v0": "top0A0_0"}, {"v0": "A0bottom0_0"}])

    binding.vehicle.advance()
    detector.observe(binding, time_s=0.0)
    detector.forget(["v0"])
    binding.vehicle.advance()
    seen = detector.observe(binding, time_s=1.0)

    assert seen == ()
    assert detector.unmatched_count == 0
```

- [ ] **Step 5: Run and watch the unit tests pass**

Run: `uv run pytest tests/simulation/sumo/test_extract.py -q`
Expected: all pass.

- [ ] **Step 6: Wire both into `step()` and add the integration regression test**

In `src/cadence/simulation/sumo/connection.py`, build the topology, extractor and detector in `__enter__`, and return them from `step()`:

```python
    def __enter__(self) -> Self:
        binding = load_binding(self._binding_kind)
        command = build_sumo_command(
            self._config, self._paths, seed=self._seed, use_gui=self._use_gui
        )
        binding.start(command)
        self._binding = binding
        self._topology = read_topology(binding)
        self._extractor = StateExtractor(self._topology)
        self._traversals = TraversalDetector(self._topology)
        return self

    @property
    def topology(self) -> NetworkTopology:
        if self._topology is None:
            raise RuntimeError("simulation connection is closed")
        return self._topology
```

and in `step()`, after collecting `events`. **The order is load-bearing**: the teleport
record needs the lane the detector is still holding, and the detector must forget that lane
before it observes the vehicle downstream.

```python
        teleporting = binding.simulation.getStartingTeleportIDList()
        teleports = tuple(
            TeleportEvent(
                time_s=time_s,
                vehicle_id=VehicleId(vehicle_id),
                # GOTCHA: getLaneID() returns "" for a vehicle mid-teleport. The lane it
                # left survives only in what the detector is holding, so read it here and
                # not from the binding.
                from_lane_id=self._traversals.held_lane(vehicle_id),
                kind=TeleportKind.STARTED,
            )
            for vehicle_id in teleporting
        )
        self._traversals.forget(teleporting)
        traversals = self._traversals.observe(binding, time_s)
        return StepResult(
            time_s=time_s,
            events=events,
            state=self._extractor.extract(binding, time_s, events, traversals),
            teleports=teleports,
            expected_remaining_veh=int(binding.simulation.getMinExpectedNumber()),
        )

    def unmatched_traversals(self) -> int:
        return self._traversals.unmatched_count
```

Add to `tests/simulation/sumo/test_connection.py`:

```python
# PROVENANCE: the twelve integers the turning demand was built from (spec section 10.3).
# The total of 315 is invariant under every possible movement-mapping error; these are not.
EXPECTED_MOVEMENT_TRAVERSALS = {
    "top0A0->A0left0": 10, "top0A0->A0bottom0": 60, "top0A0->A0right0": 20,
    "right0A0->A0top0": 30, "right0A0->A0left0": 40, "right0A0->A0bottom0": 12,
    "bottom0A0->A0right0": 15, "bottom0A0->A0top0": 32, "bottom0A0->A0left0": 24,
    "left0A0->A0bottom0": 40, "left0A0->A0right0": 24, "left0A0->A0top0": 8,
}


@pytest.mark.sumo
def test_every_vehicle_produces_exactly_one_traversal(repo_root):
    # Measured: via-lane presence gives 322, the lane pair gives 306, the outgoing edge
    # gives 315. This asserts ST-D16.
    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    total = 0
    departed = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            result = connection.step()
            total += len(result.state.traversals)
            departed += sum(1 for e in result.events if e.kind is EventKind.DEPARTED)
        unmatched = connection.unmatched_traversals()

    assert departed == 315
    assert total == 315
    assert unmatched == 0


@pytest.mark.sumo
def test_per_movement_totals_match_the_demand_they_were_built_from(repo_root):
    # The stronger test. A swapped MovementId derivation leaves the total at 315 and moves
    # these twelve, which is the entire reason the demand is asymmetric.
    from collections import Counter

    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    counts: Counter[str] = Counter()
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            for traversal in connection.step().state.traversals:
                counts[str(traversal.movement_id)] += 1

    assert dict(counts) == EXPECTED_MOVEMENT_TRAVERSALS


@pytest.mark.sumo
def test_a_mid_junction_lane_change_leaves_the_connection_unresolved(repo_root):
    # Nine of 315 exit on another lane of the correct edge. The movement always resolves;
    # the connection does not, and a null says so rather than the vehicle disappearing.
    config, paths = load_scenario(repo_root / "scenarios/s0_turning/v1")
    unresolved = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            for traversal in connection.step().state.traversals:
                assert traversal.movement_id is not None
                unresolved += traversal.connection_id is None

    assert unresolved == 9
```

- [ ] **Step 7: Run it**

Run: `uv run pytest tests/simulation/sumo/test_connection.py -q`
Expected: pass. **322 means the detector is keyed on the via lane. 306 means it is keyed on the lane pair. Anything else means vehicles are being missed and `unmatched_traversals()` will say how many. None of these is a reason to change the expected number** — all three were measured before this plan was written.

- [ ] **Step 8: Run the full gate and commit**

```bash
make check
git add src/cadence/simulation/events.py src/cadence/simulation/sumo/extract.py \
  src/cadence/simulation/sumo/connection.py tests/conftest.py \
  tests/simulation/sumo/test_extract.py tests/simulation/sumo/test_connection.py
git commit -m "feat(simulation): detect a completed movement from the lane pair it crossed"
```

---

### Task 6: Ground truth, and the boundary that fences it

**Files:**
- Create: `src/cadence/simulation/ground_truth.py`
- Modify: `src/cadence/simulation/sumo/extract.py`, `src/cadence/simulation/sumo/connection.py`, `tests/test_architecture.py`, `pyproject.toml`
- Move: `src/cadence/simulation/validation.py` to `src/cadence/simulation/sumo/validation.py`
- Test: `tests/simulation/sumo/test_ground_truth.py`, `tests/test_architecture.py`, `tests/simulation/test_validation.py`

**Interfaces:**
- Produces: `LaneTurnCount`, `SimulationGroundTruth`; `GroundTruthReader(topology)` with `read(binding, time_s) -> SimulationGroundTruth`; `SumoConnection.read_ground_truth() -> SimulationGroundTruth`.

Exact turn intent is affordable — 0.44 µs per vehicle per step with the route cached (spec §3.4) — and unobservable: on a shared lane no sensor reports how many queued vehicles intend to turn. It is therefore privileged, and reaching for it is a separately named act (`ST-D01`, `ST-D09`).

`CanonicalTrafficState` is a **parity** claim, not a realism claim: it still contains whole-lane halting counts no single detector returns. What the boundary guarantees is that every controller CADENCE compares receives the same information.

- [ ] **Step 1: Write the failing boundary tests**

Add to `tests/test_architecture.py`:

```python
GROUND_TRUTH_MODULE = "cadence.simulation.ground_truth"
# Every module permitted to name the privileged directory or import its types. Extending
# this list is a deliberate edit; a new entry appearing without one is the finding.
# Exactly the modules that exist and name it at the commit where this test lands.
# `simulation/artifacts.py` and `cli.py` join it in Task 7, when they are written — the
# test's whole purpose is that growing this set is a deliberate edit, so it cannot be
# pre-populated with files that do not exist.
GROUND_TRUTH_ALLOWLIST = {
    "simulation/ground_truth.py",
    "simulation/sumo/extract.py",
    "simulation/sumo/connection.py",
}


def _imports_ground_truth(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "cadence.simulation.ground_truth"
        ):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.startswith(GROUND_TRUTH_MODULE) for alias in node.names
        ):
            return True
    return False


def test_nothing_outside_simulation_imports_ground_truth():
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if not str(path.relative_to(SRC_ROOT)).startswith("simulation/")
        and _imports_ground_truth(path)
    ]
    assert not offenders, "ST-D01 violated: " + "; ".join(offenders)


def test_the_ground_truth_allowlist_is_exactly_what_names_it():
    naming = {
        str(path.relative_to(SRC_ROOT))
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "ground_truth" in path.read_text()
    }
    assert naming == GROUND_TRUTH_ALLOWLIST, (
        "ST-D08: extending the privileged surface must be a deliberate edit. "
        f"unexpected: {sorted(naming - GROUND_TRUTH_ALLOWLIST)}; "
        f"missing: {sorted(GROUND_TRUTH_ALLOWLIST - naming)}"
    )


def test_only_the_sumo_package_imports_sumolib():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "sumo" in path.relative_to(SRC_ROOT).parts:
            continue
        if "sumolib" in _imported_roots(path):
            offenders.append(str(path.relative_to(SRC_ROOT)))
    assert not offenders, "ST-D12 violated: " + "; ".join(offenders)


def test_mypy_strictness_is_not_disabled_for_any_cadence_package():
    # ST-D02: the import ban and mypy --strict enforce this boundary together. Relaxing
    # strictness anywhere under src/cadence silently relaxes the boundary with it.
    import tomllib

    config = tomllib.loads((SRC_ROOT.parents[1] / "pyproject.toml").read_text())
    assert config["tool"]["mypy"]["strict"] is True
    for override in config["tool"]["mypy"].get("overrides", []):
        modules = override.get("module", [])
        targeted = [m for m in ([modules] if isinstance(modules, str) else modules)
                    if m.startswith("cadence")]
        relaxed = {key for key, value in override.items() if key != "module" and value is False}
        assert not (targeted and relaxed), f"strictness relaxed for {targeted}: {sorted(relaxed)}"
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_architecture.py -q`
Expected: `test_only_the_sumo_package_imports_sumolib` fails on `simulation/validation.py`, and `test_the_ground_truth_allowlist_is_exactly_what_names_it` fails because no module names it yet.

- [ ] **Step 3: Move `validation.py` under the SUMO package**

```bash
git mv src/cadence/simulation/validation.py src/cadence/simulation/sumo/validation.py
git mv tests/simulation/test_validation.py tests/simulation/sumo/test_validation.py
```

Update the import in `src/cadence/cli.py` to `from cadence.simulation.sumo.validation import validate_network`, and the import in the moved test. Add the banned-api entry to `pyproject.toml` beside the existing two:

```toml
"sumolib".msg = "Every SUMO surface lives under cadence.simulation.sumo (ST-D12)."
```

and extend the per-file ignore so the two modules that legitimately use it are exempt:

```toml
"src/cadence/simulation/sumo/validation.py" = ["TID251"]
```

- [ ] **Step 4: Write the failing ground-truth test**

Create `tests/simulation/sumo/test_ground_truth.py`:

```python
import pytest

from cadence.simulation.ground_truth import SimulationGroundTruth
from cadence.simulation.scenario import load_scenario
from cadence.simulation.sumo.binding import BindingKind
from cadence.simulation.sumo.connection import SumoConnection

TURNING = "scenarios/s0_turning/v1"


@pytest.mark.sumo
def test_ground_truth_cross_tabs_lane_against_intended_next_edge(repo_root):
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        for _ in range(120):
            connection.step()
        truth = connection.read_ground_truth()

    assert isinstance(truth, SimulationGroundTruth)
    assert truth.lane_turns, "the fixture has traffic at t=120"
    assert all(row.count_veh > 0 for row in truth.lane_turns), "only non-zero rows are kept"
    assert all(row.halting_count_veh <= row.count_veh for row in truth.lane_turns)


@pytest.mark.sumo
def test_a_shared_lane_reports_more_than_one_intended_next_edge(repo_root):
    # The whole reason this stream exists: on a shared lane the split is not recoverable
    # from the lane count alone.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        shared_seen = False
        for _ in range(400):
            connection.step()
            truth = connection.read_ground_truth()
            by_lane: dict[str, set[str]] = {}
            for row in truth.lane_turns:
                by_lane.setdefault(row.lane_id, set()).add(row.next_edge_id)
            if any(len(edges) > 1 for edges in by_lane.values()):
                shared_seen = True
                break

    assert shared_seen


@pytest.mark.sumo
def test_step_does_not_carry_ground_truth(repo_root):
    # ST-D09: reaching for privileged information must be visible in a diff.
    import dataclasses

    from cadence.simulation.events import StepResult

    names = {field.name for field in dataclasses.fields(StepResult)}
    assert "ground_truth" not in names
    assert "lane_turns" not in names
```

- [ ] **Step 5: Write the ground-truth types and reader**

Create `src/cadence/simulation/ground_truth.py`:

```python
"""Privileged simulator truth. Controllers must not reach this.

CONTRACT: exact per-vehicle turn intent is unobservable in the field — on a shared lane no
sensor reports how many queued vehicles intend to turn. It exists here for validation,
debugging, and explicitly labelled oracle experiments, and an architecture test refuses any
import of this module from outside `simulation/` (ST-D01).
"""

from __future__ import annotations

from dataclasses import dataclass

from cadence.types import EdgeId, LaneId


@dataclass(frozen=True, slots=True)
class LaneTurnCount:
    lane_id: LaneId
    next_edge_id: EdgeId
    count_veh: int
    halting_count_veh: int
    waiting_total_now_s: float


@dataclass(frozen=True, slots=True)
class SimulationGroundTruth:
    time_s: float
    lane_turns: tuple[LaneTurnCount, ...]
```

Append to `src/cadence/simulation/sumo/extract.py`:

```python
# PROVENANCE: a vehicle is halting when its speed is below this. Matches SUMO's own
# definition behind getLastStepHaltingNumber, documented as 0.1 m/s.
HALTING_SPEED_MPS = 0.1


class GroundTruthReader:
    """Cross-tabs lane against the edge each vehicle on it intends to enter next."""

    def __init__(self, topology: NetworkTopology) -> None:
        self._lanes = set(topology.lanes)
        self._routes: dict[str, tuple[str, ...]] = {}

    def read(self, binding: ModuleType, time_s: float) -> SimulationGroundTruth:
        counts: dict[tuple[LaneId, EdgeId], list[float]] = {}
        active = set()
        for vehicle_id in binding.vehicle.getIDList():
            active.add(vehicle_id)
            lane_id = LaneId(binding.vehicle.getLaneID(vehicle_id))
            if lane_id not in self._lanes:
                continue
            route = self._routes.get(vehicle_id)
            if route is None:
                # Cached once: a route is static unless the vehicle reroutes, and querying
                # it every step costs roughly twice as much per vehicle.
                route = tuple(binding.vehicle.getRoute(vehicle_id))
                self._routes[vehicle_id] = route
            index = int(binding.vehicle.getRouteIndex(vehicle_id))
            if not 0 <= index + 1 < len(route):
                continue
            key = (lane_id, EdgeId(route[index + 1]))
            speed = float(binding.vehicle.getSpeed(vehicle_id))
            tally = counts.setdefault(key, [0.0, 0.0, 0.0])
            tally[0] += 1
            tally[1] += 1 if speed < HALTING_SPEED_MPS else 0
            tally[2] += float(binding.vehicle.getWaitingTime(vehicle_id))
        for gone in self._routes.keys() - active:
            del self._routes[gone]

        return SimulationGroundTruth(
            time_s=time_s,
            lane_turns=tuple(
                LaneTurnCount(
                    lane_id=lane_id,
                    next_edge_id=next_edge_id,
                    count_veh=int(tally[0]),
                    halting_count_veh=int(tally[1]),
                    waiting_total_now_s=tally[2],
                )
                for (lane_id, next_edge_id), tally in sorted(counts.items())
            ),
        )
```

Import `SimulationGroundTruth`, `LaneTurnCount`, and `EdgeId` at the top of the module.

In `connection.py`, build the reader in `__enter__` and add the named call:

```python
    def read_ground_truth(self) -> SimulationGroundTruth:
        binding = self._require_open()
        return self._ground_truth.read(binding, float(binding.simulation.getTime()))
```

- [ ] **Step 6: Run everything**

Run: `uv run pytest tests/simulation/sumo/test_ground_truth.py tests/test_architecture.py tests/simulation/sumo/test_validation.py -q`
Expected: all pass. The allowlist test now sees exactly the five modules named in `GROUND_TRUTH_ALLOWLIST`; if it reports a sixth, that module reached for privileged information and the test is doing its job.

- [ ] **Step 7: Run the full gate and commit**

```bash
make check
git add -A src/cadence tests pyproject.toml
git commit -m "feat(simulation): add privileged ground truth and fence it with three mechanisms"
```

---

### Task 6a: Record what the reviews found missing

**Files:**
- Modify: `src/cadence/simulation/topology.py`, `src/cadence/simulation/sumo/topology_reader.py`, `src/cadence/simulation/sumo/command.py`, `src/cadence/simulation/sumo/extract.py`, `src/cadence/simulation/events.py`
- Test: `tests/simulation/sumo/test_topology_reader.py`, `tests/simulation/sumo/test_command.py`, `tests/simulation/sumo/test_ground_truth.py`

**Interfaces:**
- Produces: `PhaseInfo`, `NetworkTopology.phases`; `TeleportEvent`; `--tripinfo-output` in the SUMO command; `next_edge_id: EdgeId | None` on `LaneTurnCount`. The residual is a row, not a pair of columns — an earlier design used extra columns and was corrected in the spec's §6.1; this line was the leftover.

Two things the run directory could not answer, and one it answered wrongly. The signal
program moved to Task 3, where the rest of the topology is read. `ST-D18` and `ST-D19`, spec §8 and §6.1. None of these is discoverable later without re-running the simulation, which is the exact failure spec §8's sufficiency claim exists to prevent.

- [ ] **Step 1: Write the failing tests**

```python
# tests/simulation/sumo/test_topology_reader.py
@pytest.mark.sumo
def test_the_signal_program_is_recorded(topology):
    # Without this, phase_index is an integer with no meaning, min and max green are
    # recoverable from nothing, and a phase that is never served leaves no trace at all -
    # which is the starvation case the spec flags as needing a test.
    assert topology.phases, "S0's static program has four phases"
    indices = {phase.phase_index for phase in topology.phases}
    assert indices == {0, 1, 2, 3}
    assert all(phase.duration_s > 0 for phase in topology.phases)
    assert all(len(phase.signals) == 16 for phase in topology.phases)
    assert any(
        signal.permits_movement for phase in topology.phases for signal in phase.signals
    )


# tests/simulation/sumo/test_command.py
def test_the_command_asks_sumo_for_tripinfo(s0_config, s0_paths, tmp_path):
    # ST-D18: M1b's trip metrics have no other source, and the flag was absent since M0.
    command = build_sumo_command(s0_config, s0_paths, seed=1, use_gui=False,
                                 tripinfo_path=tmp_path / "tripinfo.xml")
    assert "--tripinfo-output" in command
    assert str(tmp_path / "tripinfo.xml") in command
    # Without this SUMO writes no row for a vehicle still in the network when the run ends,
    # and under oversaturation that is exactly the most delayed trips.
    assert "--tripinfo-output.write-unfinished" in command


# tests/simulation/sumo/test_ground_truth.py
@pytest.mark.sumo
def test_the_cross_tab_conserves_the_lane_count(repo_root):
    # Spec 6.1: a vehicle on its final edge has no next edge and appears in no row, while
    # getLastStepHaltingNumber counts it. No threshold choice fixes that, so the residual
    # is recorded and M1b can tell an attribution error from a definitional artefact.
    config, paths = load_scenario(repo_root / TURNING)
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        for _ in range(200):
            result = connection.step()
            truth = connection.read_ground_truth()
            by_lane: dict[str, int] = {}
            nulls: dict[str, int] = {}
            for row in truth.lane_turns:
                by_lane[row.lane_id] = by_lane.get(row.lane_id, 0) + row.count_veh
                if row.next_edge_id is None:
                    nulls[row.lane_id] = nulls.get(row.lane_id, 0) + 1
            for lane_id, lane_state in result.state.lanes.items():
                assert nulls.get(lane_id) == 1, f"{lane_id} has no unattributed row"
                assert by_lane[lane_id] == lane_state.vehicle_count_veh
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/simulation/sumo/test_topology_reader.py tests/simulation/sumo/test_command.py tests/simulation/sumo/test_ground_truth.py -q`
Expected: `AttributeError` on `topology.phases`, a `TypeError` on the unexpected `tripinfo_path`, and an `AttributeError` on `unattributed_count_veh`.

- [ ] **Step 3: Add `PhaseInfo` and read the program**

In `topology.py`:

```python
@dataclass(frozen=True, slots=True)
class PhaseInfo:
    intersection_id: IntersectionId
    program_id: str
    phase_index: int
    duration_s: float
    min_duration_s: float
    max_duration_s: float
    signals: tuple[SignalState, ...]
```

Add `phases: tuple[PhaseInfo, ...]` to `NetworkTopology`. In `topology_reader.py`, read it beside the connections:

```python
    phases: list[PhaseInfo] = []
    for tls_id in sorted(binding.trafficlight.getIDList()):
        logic = binding.trafficlight.getAllProgramLogics(tls_id)[0]
        for index, phase in enumerate(logic.phases):
            phases.append(
                PhaseInfo(
                    intersection_id=IntersectionId(tls_id),
                    program_id=str(logic.programID),
                    phase_index=index,
                    duration_s=float(phase.duration),
                    min_duration_s=float(phase.minDur),
                    max_duration_s=float(phase.maxDur),
                    signals=tuple(decode_signal(character) for character in phase.state),
                )
            )
```

`decode_signal` is already imported in this module's sibling; import it here too. The phase's `state` is a lamp string and it is decoded before it leaves `simulation/sumo/`, which is what keeps `ST-D04` true of the artifacts as well as the code.

- [ ] **Step 4: Ask SUMO for tripinfo**

In `command.py`, add an optional `tripinfo_path: Path | None = None` parameter and, when given:

```python
        # ST-D18: M1b's trip metrics -- travel time, time loss, depart delay -- have no
        # other source, and this flag was absent from every run since M0.
        # GOTCHA: write-unfinished is not optional. SUMO emits no row for a vehicle still in
        # the network at the end, and a run under regime C or D ends at the horizon with the
        # most delayed trips unfinished -- censoring the tail the research question is about.
        arguments += [
            "--tripinfo-output", str(tripinfo_path),
            "--tripinfo-output.write-unfinished", "true",
        ]
```

- [ ] **Step 5: Confirm the teleport record is wired**

`TeleportEvent` and `TeleportKind` were defined in Task 4 and `SumoConnection.step()` builds
them in Task 5, from the detector's held lane and before `forget()`. Nothing new is defined
here; confirm the wiring and that `from_lane_id` is nullable, because a vehicle can teleport
before the detector has ever seen it on an approach lane.

Under regimes C and D a teleport fabricates discharge on one specific approach. At M9 the question "did Max-Pressure's advantage come from service, or from gridlock removal on the blocked approach?" has to be answerable from the run directory.

- [ ] **Step 6: Add the unattributed residual**

The residual gets **its own row**, not extra columns on every row (spec §6.1). Attaching a
per-lane residual to each `(lane, next_edge)` row double-counts it the moment a lane serves
two movements, and a lane whose vehicles are all on their final edge emits no row at all
under the non-zero rule — on `s0_turning` that is every one of the eight exit lanes, so half
the network's residual would go unrecorded and the conservation test would silently skip it.

`LaneTurnCount.next_edge_id` becomes `EdgeId | None`. `GroundTruthReader` emits one row per
`(lane, next_edge)` with a non-zero count, plus **one row per lane in `topology`** with
`next_edge_id = None` carrying the vehicles whose next edge does not resolve — the final-edge
case — written whether or not the count is zero. A missing null row is itself a failure, and
§11's identity is a sum over all of a lane's rows.

Update Task 6's `test_ground_truth_cross_tabs_lane_against_intended_next_edge`: it asserts
`all(row.count_veh > 0 ...)`, which the null rows break. Assert instead that every row with a
non-null `next_edge_id` has a positive count, and that exactly one null row exists per lane.

- [ ] **Step 7: Run everything and commit**

```bash
uv run pytest tests/simulation -q
make check
git add -A src/cadence tests
git commit -m "feat(simulation): record the program, the teleport lane and the cross-tab residual"
```

### Task 7: Run artifacts

**Files:**
- Create: `src/cadence/simulation/artifacts.py`
- Modify: `tests/test_architecture.py` — add `simulation/artifacts.py` to `GROUND_TRUTH_ALLOWLIST`
- Test: `tests/simulation/test_artifacts.py`

**Interfaces:**
- Consumes: `NetworkTopology`, `PhaseInfo`, `CanonicalTrafficState`, `TeleportEvent`,
  `SimulationGroundTruth`. `Traversal` is reached through `state.traversals`, not passed
  separately.
- Produces: `RunRecorder(run_dir, topology)` with `record(state, teleports, truth)`,
  `write_tripinfo(tripinfo_xml)`, `write()`, and the directory layout of spec §8. Task 9
  calls all three.

`topology/` is written per run rather than referenced from the scenario, so reading a run
directory needs no access to the network file that produced it.

`artifacts.py` imports `cadence.simulation.ground_truth`, and
`test_the_ground_truth_allowlist_is_exact` compares the importing set against
`GROUND_TRUTH_ALLOWLIST` for **exact equality**. Adding the module without adding the
allowlist entry fails the architecture suite. That failure is the test working: extending
the privileged surface is meant to be a deliberate edit, so make it deliberately, in the
same commit.

- [ ] **Step 1: Write the failing test**

Create `tests/simulation/test_artifacts.py`:

```python
import polars as pl
import pytest

from cadence.simulation.artifacts import (
    EVALUATION_DIR,
    GROUND_TRUTH_DIR,
    STATE_DIR,
    TOPOLOGY_DIR,
    RunRecorder,
)
from cadence.simulation.ground_truth import LaneTurnCount, SimulationGroundTruth
from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    MovementState,
    NetworkState,
    SignalState,
    TeleportEvent,
    TeleportKind,
    Traversal,
)
from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    PhaseInfo,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, VehicleId

_TRIPINFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<tripinfos>
    <tripinfo id="v0" depart="0.00" arrival="42.00" duration="42.00" waitingTime="7.00"/>
</tripinfos>
"""


def _topology() -> NetworkTopology:
    lane = LaneInfo(LaneId("a_0"), EdgeId("a"), 0, 100.0, 13.89)
    out = LaneInfo(LaneId("b_0"), EdgeId("b"), 0, 100.0, 13.89)
    connection = ConnectionInfo(
        connection_id=ConnectionId("a_0|b_0"),
        intersection_id=IntersectionId("A0"),
        link_index=0,
        from_lane_id=LaneId("a_0"),
        to_lane_id=LaneId("b_0"),
        via_lane_id=LaneId(":A0_0_0"),
        from_edge_id=EdgeId("a"),
        to_edge_id=EdgeId("b"),
        turn_direction=TurnDirection.STRAIGHT,
        movement_id=movement_id(EdgeId("a"), EdgeId("b")),
    )
    return NetworkTopology(
        lanes={lane.lane_id: lane, out.lane_id: out},
        connections={connection.connection_id: connection},
        movements=build_movements([connection]),
        phases=(
            PhaseInfo(
                intersection_id=IntersectionId("A0"),
                program_id="0",
                phase_index=0,
                duration_s=42.0,
                min_duration_s=42.0,
                max_duration_s=42.0,
                signals=(SignalState.GREEN_PROTECTED,),
            ),
        ),
    )


def _state(time_s: float, topology: NetworkTopology) -> CanonicalTrafficState:
    lane = LaneState(LaneId("a_0"), 2, 1, 3.0, 0.1, 4.0)
    identifier = next(iter(topology.movements))
    return CanonicalTrafficState(
        time_s=time_s,
        topology=topology,
        lanes={lane.lane_id: lane},
        movements={
            identifier: MovementState(
                movement_id=identifier,
                signals=(SignalState.GREEN_PROTECTED,),
            )
        },
        intersections={
            IntersectionId("A0"): IntersectionState(
                IntersectionId("A0"),
                "0",
                0,
                5.0,
                (ConnectionState(ConnectionId("a_0|b_0"), SignalState.GREEN_PROTECTED),),
            )
        },
        traversals=(
            Traversal(time_s, VehicleId("v0"), identifier, ConnectionId("a_0|b_0")),
        ),
        network=NetworkState(2, 0, 3, 1, 0),
    )


@pytest.fixture
def recorder(tmp_path):
    topology = _topology()
    return RunRecorder(tmp_path, topology), topology


def test_the_run_directory_has_the_specified_shape(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(
        state=_state(1.0, topology),
        teleports=(),
        truth=SimulationGroundTruth(
            1.0, (LaneTurnCount(LaneId("a_0"), EdgeId("b"), 2, 1, 4.0),)
        ),
    )
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(_TRIPINFO_XML)
    run_recorder.write_tripinfo(tripinfo)
    run_recorder.write()

    for relative in (
        f"{TOPOLOGY_DIR}/lane.parquet",
        f"{TOPOLOGY_DIR}/connection.parquet",
        f"{TOPOLOGY_DIR}/tls_program.parquet",
        f"{STATE_DIR}/lane.parquet",
        f"{STATE_DIR}/intersection.parquet",
        f"{STATE_DIR}/signal.parquet",
        f"{STATE_DIR}/network.parquet",
        f"{STATE_DIR}/movement.parquet",
        f"{STATE_DIR}/traversal.parquet",
        f"{STATE_DIR}/teleport.parquet",
        f"{GROUND_TRUTH_DIR}/lane_turn.parquet",
        f"{EVALUATION_DIR}/tripinfo.parquet",
    ):
        assert (tmp_path / relative).is_file(), relative


def test_state_tables_carry_the_specified_columns(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    lane = pl.read_parquet(tmp_path / STATE_DIR / "lane.parquet")
    assert lane.columns == [
        "time_s",
        "lane_id",
        "vehicle_count_veh",
        "halting_count_veh",
        "mean_speed_mps",
        "occupancy_ratio",
        "waiting_total_now_s",
    ]
    signal = pl.read_parquet(tmp_path / STATE_DIR / "signal.parquet")
    assert signal.columns == ["time_s", "connection_id", "signal"]


def test_no_lamp_string_reaches_an_artifact(tmp_path, recorder):
    # ST-D04: decoding at extraction extends the rule to the artifacts, not just the code.
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    signal = pl.read_parquet(tmp_path / STATE_DIR / "signal.parquet")
    assert signal["signal"].to_list() == ["green_protected"]


def test_two_steps_append_rather_than_overwrite(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.record(_state(2.0, topology), (), SimulationGroundTruth(2.0, ()))
    run_recorder.write()

    network = pl.read_parquet(tmp_path / STATE_DIR / "network.parquet")
    assert network["time_s"].to_list() == [1.0, 2.0]


def test_an_empty_table_still_declares_its_columns_and_types(tmp_path, recorder):
    # A run with no teleports must be readable by the same code as a run with some. Without
    # a declared schema polars writes a nought-column frame, and every downstream select
    # crashes on exactly the quiet runs.
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    teleport = pl.read_parquet(tmp_path / STATE_DIR / "teleport.parquet")
    assert teleport.height == 0
    assert teleport.columns == ["time_s", "vehicle_id", "from_lane_id", "kind"]
    assert teleport.schema["time_s"] == pl.Float64
    assert teleport.schema["vehicle_id"] == pl.String


def test_the_residual_row_keeps_a_null_rather_than_the_string_none(tmp_path, recorder):
    # ST-D19: the unattributed residual is a row whose next_edge_id is null. Rendering it as
    # "None" would make it indistinguishable from an edge literally named None, and every
    # conservation check would silently count it as attributed.
    run_recorder, topology = recorder
    run_recorder.record(
        _state(1.0, topology),
        (TeleportEvent(1.0, VehicleId("v9"), None, TeleportKind.STARTED),),
        SimulationGroundTruth(
            1.0,
            (
                LaneTurnCount(LaneId("a_0"), EdgeId("b"), 2, 1, 4.0),
                LaneTurnCount(LaneId("a_0"), None, 1, 0, 0.0),
            ),
        ),
    )
    run_recorder.write()

    lane_turn = pl.read_parquet(tmp_path / GROUND_TRUTH_DIR / "lane_turn.parquet")
    assert lane_turn["next_edge_id"].to_list() == ["b", None]
    teleport = pl.read_parquet(tmp_path / STATE_DIR / "teleport.parquet")
    assert teleport["from_lane_id"].to_list() == [None]


def test_tripinfo_keeps_sumo_attribute_names_verbatim(tmp_path, recorder):
    run_recorder, _topology = recorder
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(_TRIPINFO_XML)
    run_recorder.write_tripinfo(tripinfo)

    table = pl.read_parquet(tmp_path / EVALUATION_DIR / "tripinfo.parquet")
    assert table.columns == ["id", "depart", "arrival", "duration", "waitingTime"]
    assert table["waitingTime"].to_list() == ["7.00"]
```

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/simulation/test_artifacts.py -q`
Expected: `ModuleNotFoundError: No module named 'cadence.simulation.artifacts'`.

- [ ] **Step 3: Write the recorder**

Create `src/cadence/simulation/artifacts.py`. Accumulate per-step rows in lists and write
once at the end; a run's state is a few hundred kilobytes at S0 scale and under 2 MB at M8
corridor scale (spec §3.2), so streaming to disk buys nothing and costs a partial-file
failure mode.

```python
"""Writes a run directory that describes itself.

CONTRACT: the layout partitions along the same line as the type space. `state/` holds what
a controller could see; `ground_truth/` holds what it may not. An import ban does not
constrain a file read, so an offline dataset loader is bounded by this directory split
rather than by discipline (ST-D08).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

import polars as pl

from cadence.simulation.ground_truth import SimulationGroundTruth
from cadence.simulation.state import CanonicalTrafficState, TeleportEvent
from cadence.simulation.topology import NetworkTopology

TOPOLOGY_DIR = "topology"
STATE_DIR = "state"
GROUND_TRUTH_DIR = "ground_truth"
# ST-D18: post-hoc per-trip data is not privileged -- no controller could see a trip that
# has ended. Filing it under ground_truth/ would force every metrics module into the
# privileged allowlist, and a partition the whole metrics package must read means nothing.
EVALUATION_DIR = "evaluation"
```

Declare every table's schema. This is what makes a run with no teleports readable by the
same code as a run with thirty-five:

```python
_SCHEMAS: dict[str, dict[str, pl.DataType]] = {
    "topology/lane": {
        "lane_id": pl.String, "edge_id": pl.String, "lane_index": pl.Int64,
        "length_m": pl.Float64, "max_speed_mps": pl.Float64,
    },
    "topology/connection": {
        "connection_id": pl.String, "intersection_id": pl.String, "link_index": pl.Int64,
        "from_lane_id": pl.String, "to_lane_id": pl.String, "via_lane_id": pl.String,
        "from_edge_id": pl.String, "to_edge_id": pl.String, "turn_direction": pl.String,
        "movement_id": pl.String,
    },
    "topology/tls_program": {
        "intersection_id": pl.String, "program_id": pl.String, "phase_index": pl.Int64,
        "duration_s": pl.Float64, "min_duration_s": pl.Float64,
        "max_duration_s": pl.Float64, "connection_id": pl.String, "signal": pl.String,
    },
    "state/lane": {
        "time_s": pl.Float64, "lane_id": pl.String, "vehicle_count_veh": pl.Int64,
        "halting_count_veh": pl.Int64, "mean_speed_mps": pl.Float64,
        "occupancy_ratio": pl.Float64, "waiting_total_now_s": pl.Float64,
    },
    "state/intersection": {
        "time_s": pl.Float64, "intersection_id": pl.String, "program_id": pl.String,
        "phase_index": pl.Int64, "phase_elapsed_s": pl.Float64,
    },
    "state/signal": {"time_s": pl.Float64, "connection_id": pl.String, "signal": pl.String},
    "state/network": {
        "time_s": pl.Float64, "active_veh": pl.Int64, "pending_insertion_veh": pl.Int64,
        "departed_total_veh": pl.Int64, "arrived_total_veh": pl.Int64,
        "teleport_total_veh": pl.Int64,
    },
    "state/movement": {
        "time_s": pl.Float64, "movement_id": pl.String, "connection_id": pl.String,
        "signal": pl.String,
    },
    "state/traversal": {
        "time_s": pl.Float64, "vehicle_id": pl.String, "movement_id": pl.String,
        "connection_id": pl.String,
    },
    "state/teleport": {
        "time_s": pl.Float64, "vehicle_id": pl.String, "from_lane_id": pl.String,
        "kind": pl.String,
    },
    "ground_truth/lane_turn": {
        "time_s": pl.Float64, "lane_id": pl.String, "next_edge_id": pl.String,
        "count_veh": pl.Int64, "halting_count_veh": pl.Int64,
        "waiting_total_now_s": pl.Float64,
    },
}
```

`evaluation/tripinfo` has no entry: its columns are whatever attributes SUMO emitted, and
declaring them here would silently drop any SUMO adds.

```python
class RunRecorder:
    def __init__(self, run_dir: Path, topology: NetworkTopology) -> None:
        self._run_dir = run_dir
        self._topology = topology
        self._rows: dict[str, list[dict[str, object]]] = {name: [] for name in _SCHEMAS}

    def record(
        self,
        state: CanonicalTrafficState,
        teleports: Iterable[TeleportEvent],
        truth: SimulationGroundTruth,
    ) -> None:
        for lane in state.lanes.values():
            self._rows["state/lane"].append({"time_s": state.time_s, **_as_row(lane)})
        for intersection in state.intersections.values():
            self._rows["state/intersection"].append(
                {
                    "time_s": state.time_s,
                    "intersection_id": str(intersection.intersection_id),
                    "program_id": intersection.program_id,
                    "phase_index": intersection.phase_index,
                    "phase_elapsed_s": intersection.phase_elapsed_s,
                }
            )
            for connection in intersection.connections:
                self._rows["state/signal"].append(
                    {
                        "time_s": state.time_s,
                        "connection_id": str(connection.connection_id),
                        "signal": connection.signal.value,
                    }
                )
        self._rows["state/network"].append({"time_s": state.time_s, **_as_row(state.network)})
        for movement in state.movements.values():
            definition = state.topology.movements[movement.movement_id]
            for connection_id, signal in zip(
                definition.connection_ids, movement.signals, strict=True
            ):
                self._rows["state/movement"].append(
                    {
                        "time_s": state.time_s,
                        "movement_id": str(movement.movement_id),
                        "connection_id": str(connection_id),
                        "signal": signal.value,
                    }
                )
        for traversal in state.traversals:
            self._rows["state/traversal"].append(_as_row(traversal))
        for teleport in teleports:
            self._rows["state/teleport"].append(_as_row(teleport))
        for row in truth.lane_turns:
            self._rows["ground_truth/lane_turn"].append(
                {"time_s": truth.time_s, **_as_row(row)}
            )

    def write_tripinfo(self, tripinfo_xml: Path) -> None:
        """Convert SUMO's tripinfo XML into evaluation/tripinfo.parquet.

        One row per trip, every attribute SUMO emits kept as it is. Renaming or selecting
        here would be a metric definition, and metric definitions are versioned at M1b.
        """
        root = ElementTree.parse(tripinfo_xml).getroot()
        rows = [dict(element.attrib) for element in root.iter("tripinfo")]
        path = self._run_dir / EVALUATION_DIR / "tripinfo.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(rows).write_parquet(path)

    def write(self) -> None:
        self._rows["topology/lane"] = [
            _as_row(lane) for lane in self._topology.lanes.values()
        ]
        self._rows["topology/connection"] = [
            _as_row(item) for item in self._topology.connections.values()
        ]
        # One row per phase per controlled connection: a phase's signals are positional
        # against the TLS lamp string, and a reader should not have to re-derive which
        # connection each position belongs to.
        by_index = {
            connection.link_index: connection.connection_id
            for connection in self._topology.connections.values()
        }
        self._rows["topology/tls_program"] = [
            {
                "intersection_id": str(phase.intersection_id),
                "program_id": phase.program_id,
                "phase_index": phase.phase_index,
                "duration_s": phase.duration_s,
                "min_duration_s": phase.min_duration_s,
                "max_duration_s": phase.max_duration_s,
                "connection_id": str(by_index[position]),
                "signal": signal.value,
            }
            for phase in self._topology.phases
            for position, signal in enumerate(phase.signals)
            if position in by_index
        ]
        for name, schema in _SCHEMAS.items():
            path = self._run_dir / f"{name}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pl.DataFrame(self._rows[name], schema=schema).write_parquet(path)
```

Add the row helper. `_as_row` turns a frozen slotted dataclass into a dict of plain values;
every enum becomes its string and every `NewType` its underlying `str`, so the Parquet
schema holds no Python type:

```python
def _as_value(value: object) -> object:
    # None passes through as None. str(None) would write the four characters "None", and a
    # null that reads as a string is worse than no column at all: it looks attributed.
    if value is None or isinstance(value, int | float):
        return value
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _as_row(record: object) -> dict[str, object]:
    return {slot: _as_value(getattr(record, slot)) for slot in record.__slots__}
```

`record.__slots__` is the field tuple of a frozen slotted dataclass, in declaration order —
which is why the column order the tests assert falls out of the dataclass rather than being
restated here.

If `pl.DataFrame(rows, schema=schema)` rejects a list of dicts, or matches by position
rather than by name, build the frame from a column-wise dict instead — and say which in your
report. Do not drop the schema.

- [ ] **Step 4: Extend the ground-truth allowlist**

In `tests/test_architecture.py`, add `"simulation/artifacts.py"` to `GROUND_TRUTH_ALLOWLIST`.
`cli.py` is Task 9's and stays out until then.

- [ ] **Step 5: Run and watch it pass**

Run: `uv run pytest tests/simulation/test_artifacts.py tests/test_architecture.py -q`
Expected: all pass.

- [ ] **Step 6: Run the full gate and commit**

```bash
make check
git add src/cadence/simulation/artifacts.py tests/simulation/test_artifacts.py tests/test_architecture.py
git commit -m "feat(simulation): write a self-describing run directory split by privilege"
```

---

### Task 8: Manifest run outcome and dirty digest

**Files:**
- Modify: `src/cadence/simulation/manifest.py`, `src/cadence/simulation/sumo/connection.py`
- Test: `tests/simulation/test_manifest.py`, `tests/simulation/sumo/test_connection_lifecycle.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `TerminationReason` and `working_tree_digest(repo_root)` in `manifest.py`;
  `RunManifest` gains `terminal_time_s`, `step_count`, `termination_reason`,
  `cadence_dirty_digest`; `build_manifest` gains matching keyword arguments;
  `git_commit(repo_root) -> str` returns the sha alone; `SumoConnection.time_s() -> float`
  and `SumoConnection.termination_reason() -> TerminationReason | None`.

`docs/DIRECTION.md` §7 items 2 and 3. S0 drains at 520 s of a 600 s horizon and the turning
fixture at 558.0 s (spec §10.3); two runs differing in termination reason are today
indistinguishable from their manifests.

Two existing tests are exact-equality gates that this task must move deliberately, in the
same commit as the change that trips them:

- `test_manifest_declares_every_reproducibility_field` compares `RunManifest.model_fields`
  against the module-level `FIELDS` set. Four new fields means four new names in `FIELDS`.
- `test_git_commit_reports_the_repository_head` unpacks `sha, dirty = git_commit(...)`.
  `git_commit` stops returning the bool; the test becomes a single assertion on the sha.

A third file breaks for the same reason without naming any of these symbols:
`tests/test_cli.py` holds a module-level `MANIFEST_FIELDS` dict that is splatted into
`RunManifest(**...)`. `RunManifest` forbids extras and requires every field, so four new
required fields make every test in that file raise `ValidationError`. Add the same four
entries there:

```python
    "terminal_time_s": 558.0,
    "step_count": 558,
    "termination_reason": "drained",
    "cadence_dirty_digest": None,
```

- [ ] **Step 1: Write the failing tests**

`tests/simulation/test_manifest.py` currently imports
`NON_REPRODUCIBLE_FIELDS, RunManifest, git_commit`. Add `TerminationReason` and
`working_tree_digest` to that import, and add `import subprocess` at the top.

Add the four new names to the `FIELDS` set:

```python
    "terminal_time_s",
    "step_count",
    "termination_reason",
    "cadence_dirty_digest",
```

Extend the existing `manifest_fixture` with the four new fields — it is a direct
`RunManifest(...)` construction, so add them alongside `time_to_teleport_s`:

```python
        terminal_time_s=558.0,
        step_count=558,
        termination_reason=TerminationReason.DRAINED,
        cadence_dirty_digest=None,
```

Replace `test_git_commit_reports_the_repository_head` with:

```python
def test_git_commit_reports_the_repository_head():
    assert len(git_commit(REPO_ROOT)) == 40
```

Then add the new tests:

```python
def _repository_with_one_commit(root: Path) -> None:
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.com"],
        ["git", "config", "user.name", "T"],
    ):
        subprocess.run(command, cwd=root, check=True)
    (root / "a.txt").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=root, check=True)


def test_the_manifest_records_how_the_run_ended(manifest_fixture):
    assert manifest_fixture.terminal_time_s == 558.0
    assert manifest_fixture.step_count == 558
    assert manifest_fixture.termination_reason is TerminationReason.DRAINED


def test_run_outcome_is_part_of_the_reproducible_comparison(manifest_fixture):
    # Two runs of the same scenario and seed that ended differently are not the same run,
    # and saying so is exactly what M1b's verify-run has to be able to do.
    fields = manifest_fixture.reproducible_fields()
    assert {"terminal_time_s", "step_count", "termination_reason"} <= set(fields)


def test_a_clean_tree_has_no_digest(tmp_path):
    _repository_with_one_commit(tmp_path)
    assert working_tree_digest(tmp_path) is None


def test_two_different_dirty_trees_produce_different_digests(tmp_path):
    _repository_with_one_commit(tmp_path)

    (tmp_path / "a.txt").write_text("first change\n")
    first = working_tree_digest(tmp_path)
    (tmp_path / "a.txt").write_text("second change\n")
    second = working_tree_digest(tmp_path)

    assert first is not None and second is not None
    assert first != second, "ST-D11: a boolean cannot tell these two runs apart"


def test_an_untracked_file_alone_makes_the_tree_dirty(tmp_path):
    # `git diff HEAD` is blind to a file git has never seen, and a scenario or a scratch
    # script added but not committed changes what a run does.
    _repository_with_one_commit(tmp_path)
    (tmp_path / "new.txt").write_text("untracked\n")
    assert working_tree_digest(tmp_path) is not None
```

Add to `tests/simulation/sumo/test_connection_lifecycle.py`. It has no `repo_root` fixture
in scope but does have a module-level `S0_ROOT`; add a sibling for the turning scenario:

```python
TURNING_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_turning" / "v1"


@pytest.mark.sumo
def test_the_turning_fixture_drains_rather_than_hitting_the_horizon():
    config, paths = load_scenario(TURNING_ROOT)
    steps = 0
    with SumoConnection(config, paths, seed=1, binding=BindingKind.LIBSUMO) as connection:
        while not connection.is_finished():
            connection.step()
            steps += 1
        reason = connection.termination_reason()
        terminal_time_s = connection.time_s()

    assert reason is TerminationReason.DRAINED
    assert terminal_time_s == 558.0
    assert steps == 558
```

Import `TerminationReason` from `cadence.simulation.manifest` in that file too.

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/simulation/test_manifest.py tests/simulation/sumo/test_connection_lifecycle.py -q`
Expected: `ImportError` for `TerminationReason` and `working_tree_digest`.

- [ ] **Step 3: Add the outcome fields and the digest**

In `src/cadence/simulation/manifest.py`, add `import hashlib` and `from enum import StrEnum`:

```python
class TerminationReason(StrEnum):
    DRAINED = "drained"
    HORIZON = "horizon"
    # Every other way a run can stop: a simulator error, an external kill, a gridlock the
    # harness declines to sit through. Two values would have meant a run ending any other
    # way produces no manifest at all rather than an honest one, and under oversaturation
    # that is a normal outcome, not an impossible one.
    ABORTED = "aborted"
```

Add four fields to `RunManifest`, after `time_to_teleport_s`:

```python
    terminal_time_s: float
    step_count: int
    termination_reason: TerminationReason
    cadence_dirty_digest: str | None
```

They stay out of `NON_REPRODUCIBLE_FIELDS`.

```python
def working_tree_digest(repo_root: Path) -> str | None:
    """Identity of the uncommitted state, or None when the tree is clean.

    ST-D11: a boolean cannot distinguish two runs made from two different uncommitted
    trees. `git diff HEAD` covers modified tracked files and `git status --porcelain -uall`
    covers the presence of untracked ones; neither alone is enough.
    """
    parts = [
        subprocess.run(
            command, cwd=repo_root, capture_output=True, text=True, check=True
        ).stdout
        for command in (["git", "diff", "HEAD"], ["git", "status", "--porcelain", "-uall"])
    ]
    combined = "".join(parts)
    if not combined.strip():
        return None
    return hashlib.sha256(combined.encode()).hexdigest()
```

- [ ] **Step 4: Make `cadence_dirty` an answer, not a second opinion**

`git_commit` currently computes dirtiness itself, with `git status --porcelain`.
`working_tree_digest` now computes the same predicate from a wider view. Two independent
answers to one question can disagree, and a manifest reading
`cadence_dirty: false, cadence_dirty_digest: "3f2a..."` is worse than either field alone —
it is the exact incoherence this field was added to remove.

So `git_commit` returns the sha and nothing else:

```python
def git_commit(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
```

and `build_manifest` derives the boolean from the digest, so the two cannot disagree by
construction:

```python
    digest = working_tree_digest(repo_root)
    return RunManifest(
        cadence_commit=git_commit(repo_root),
        cadence_dirty=digest is not None,
        cadence_dirty_digest=digest,
        ...
```

Extend `build_manifest`'s signature with the three keyword-only run-outcome arguments —
`terminal_time_s: float`, `step_count: int`, `termination_reason: TerminationReason` — and
pass them straight through. `cadence_dirty_digest` is computed here, not passed in.

- [ ] **Step 5: Report which condition ended the run**

In `src/cadence/simulation/sumo/connection.py`:

```python
    def time_s(self) -> float:
        return float(self._require_open().simulation.getTime())

    def termination_reason(self) -> TerminationReason | None:
        """Which of is_finished()'s two conditions fired, or None if neither has.

        GOTCHA: the horizon check comes first here for the same reason it does in
        is_finished() — SUMO does not stop at --end while a client is attached, so a run
        that reaches the horizon with vehicles still loaded is a horizon stop, not a drain.
        """
        binding = self._require_open()
        if float(binding.simulation.getTime()) >= float(binding.simulation.getEndTime()):
            return TerminationReason.HORIZON
        if int(binding.simulation.getMinExpectedNumber()) == 0:
            return TerminationReason.DRAINED
        return None
```

`from cadence.simulation.manifest import TerminationReason`. `manifest.py` imports from
`simulation.sumo.binding`, not from `connection.py`, so this closes no cycle.

- [ ] **Step 6: Run and watch them pass**

Run: `uv run pytest tests/simulation/test_manifest.py tests/simulation/sumo/test_connection_lifecycle.py -q`
Expected: all pass. If `terminal_time_s` is not 558.0, the fixture changed and Task 1's
numbers need re-measuring — do not adjust the assertion to match.

`cli.py` calls `build_manifest` and will not compile until Task 9 supplies the three new
arguments. That is expected: pass placeholders only if `make check` demands it to stay
green, and say so in your report — Task 9 replaces them with the real values.

- [ ] **Step 7: Run the full gate and commit**

```bash
make check
git add src/cadence/simulation/manifest.py src/cadence/simulation/sumo/connection.py \
  src/cadence/cli.py tests/simulation/test_manifest.py tests/test_cli.py \
  tests/simulation/sumo/test_connection_lifecycle.py
git commit -m "feat(simulation): record how a run ended and which dirty tree produced it"
```

---

### Task 9: Wire the CLI and prove it end to end

**Files:**
- Modify: `src/cadence/cli.py`, `src/cadence/simulation/sumo/connection.py`, `tests/conftest.py`, `tests/simulation/sumo/test_connection.py`
- Test: `tests/test_cli.py`, `tests/simulation/sumo/test_reproducibility.py`

**Interfaces:**
- Consumes: everything above. `RunRecorder(run_dir, topology)` with `record(state, teleports, truth)`, `write_tripinfo(path)` and `write()`; `StepResult.state`, `.events`, `.teleports`; `SumoConnection.topology`, `.read_ground_truth()`, `.time_s()`, `.termination_reason()`; `build_sumo_command(..., tripinfo_path=...)`, which already accepts it.
- Produces: `cadence run --scenario scenarios/s0_turning/v1` writing the full layout of spec §8, and `SumoConnection(..., tripinfo_path=...)`.

Every integer asserted below was measured against the fixture immediately before this task
was written, by running the turning scenario under libsumo: 16 lanes, 16 controlled
connections, 12 movements, 4 phases of 16 signals each, 315 traversals across 12 distinct
movements, 9 null connection ids, 315 departed and 315 arrived, and a drain at 558.0 s
after 558 steps. If one of them differs, something changed — report the discrepancy rather
than editing the expectation.

- [ ] **Step 1: Give the twelve integers one home**

`EXPECTED_MOVEMENT_TRAVERSALS` currently lives at the top of
`tests/simulation/sumo/test_connection.py`, where Task 5 put it. Task 9 needs the same
twelve numbers to check the *recorded artifact* rather than the in-memory traversals — a
genuinely different claim, since a correct traversal stream can still be written out
mangled. Two copies of a provenance constant is how they drift, and `tests/` is not a
package, so the second file cannot import the first.

Move it into `tests/conftest.py` as a session fixture:

```python
@pytest.fixture(scope="session")
def expected_movement_traversals() -> dict[str, int]:
    # PROVENANCE: the twelve integers the turning demand was built from (spec §10.3).
    # The total of 315 is invariant under every possible movement-mapping error; these are
    # not, and they are the only check that catches a swapped MovementId derivation.
    return {
        "top0A0->A0left0": 10, "top0A0->A0bottom0": 60, "top0A0->A0right0": 20,
        "right0A0->A0top0": 30, "right0A0->A0left0": 40, "right0A0->A0bottom0": 12,
        "bottom0A0->A0right0": 15, "bottom0A0->A0top0": 32, "bottom0A0->A0left0": 24,
        "left0A0->A0bottom0": 40, "left0A0->A0right0": 24, "left0A0->A0top0": 8,
    }
```

Delete the module-level constant and its comment from `test_connection.py`, and give the
test that used it the fixture as a parameter. Its assertion becomes
`assert dict(counts) == expected_movement_traversals`.

- [ ] **Step 2: Write the failing integration tests**

`tests/test_cli.py` today imports only `json` and two names from `cadence.cli`. Add:

```python
import polars as pl
import pytest

from cadence.cli import run_scenario
from cadence.simulation.artifacts import (
    EVALUATION_DIR,
    GROUND_TRUTH_DIR,
    STATE_DIR,
    TOPOLOGY_DIR,
)
from cadence.simulation.manifest import RunManifest
from cadence.simulation.state import SignalState
from cadence.simulation.sumo.binding import BindingKind
```

Then the tests:

```python
@pytest.mark.sumo
def test_a_turning_run_writes_every_artifact(tmp_path, repo_root, expected_movement_traversals):
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.LIBSUMO
    )

    manifest = RunManifest(**json.loads((run_dir / "manifest.json").read_text()))
    assert manifest.scenario_id == "s0_turning"
    assert manifest.termination_reason == "drained"
    assert manifest.terminal_time_s == 558.0
    assert manifest.step_count == 558

    assert pl.read_parquet(run_dir / TOPOLOGY_DIR / "connection.parquet").height == 16
    assert pl.read_parquet(run_dir / TOPOLOGY_DIR / "lane.parquet").height == 16

    traversals = pl.read_parquet(run_dir / STATE_DIR / "traversal.parquet")
    assert traversals.height == 315, "ST-D16: 322 is the via lane, 306 is the lane pair"
    assert traversals["movement_id"].n_unique() == 12
    by_movement = dict(traversals["movement_id"].value_counts().rows())
    assert by_movement == expected_movement_traversals, (
        "the total of 315 is invariant under every movement-mapping error; these twelve "
        "are not, which is why the demand is asymmetric"
    )
    assert traversals["connection_id"].null_count() == 9, "mid-junction lane changes"

    # ST-D19: a phase that is never served leaves no row in state/signal.parquet, so the
    # program has to be recorded separately or the starvation case is unreconstructable.
    program = pl.read_parquet(run_dir / TOPOLOGY_DIR / "tls_program.parquet")
    assert program["phase_index"].n_unique() == 4, "S0's static program has four phases"
    assert program.height == 4 * 16, "one row per phase per controlled connection"
    assert set(program["signal"].unique()) <= {state.value for state in SignalState}

    # ST-D18: the tail the research question is about is the unfinished trips, so the run
    # asks SUMO for those too; a drained run simply has none.
    trips = pl.read_parquet(run_dir / EVALUATION_DIR / "tripinfo.parquet")
    assert trips.height == 315

    events = pl.read_parquet(run_dir / "events.parquet")
    kinds = events["kind"].value_counts().to_dict(as_series=False)
    counts = dict(zip(kinds["kind"], kinds["count"], strict=True))
    assert counts.get("departed") == 315
    assert counts.get("arrived") == 315
    assert counts.get("teleport_started", 0) == 0
    assert counts.get("collision", 0) == 0

    assert (run_dir / GROUND_TRUTH_DIR / "lane_turn.parquet").stat().st_size > 0


@pytest.mark.sumo
def test_the_privileged_split_is_visible_on_disk(tmp_path, repo_root):
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.LIBSUMO
    )
    assert (run_dir / STATE_DIR).is_dir()
    assert (run_dir / GROUND_TRUTH_DIR).is_dir()
    # A dataset loader bounded by directory rather than by discipline needs the split to be
    # a real directory boundary, not a naming convention inside one table.
    state_columns = set(pl.read_parquet(run_dir / STATE_DIR / "lane.parquet").columns)
    assert "next_edge_id" not in state_columns
    # ST-D18: tripinfo is post-hoc, not privileged. If it sits under ground_truth/ then
    # every metrics module has to enter the privileged allowlist and the partition stops
    # meaning anything.
    assert not (run_dir / GROUND_TRUTH_DIR / "tripinfo.parquet").exists()
    assert (run_dir / EVALUATION_DIR / "tripinfo.parquet").is_file()
    # The XML SUMO wrote is converted and removed: two copies of one dataset, one of them in
    # a format nothing else in the run directory uses, is a format decision made by accident.
    assert not (run_dir / "tripinfo.xml").exists()
```

See `tests/test_cli.py::test_the_cross_tab_only_names_reachable_successors` as shipped.
The plan originally asserted the successor at the **lane**, per spec §11. Run against the
fixture, that is false — 227 vehicle-steps of 10351, in eight pairs — because
`departLane="free"` inserts a vehicle wherever there is room rather than on a lane serving
its route. `ST-D20` moved the invariant to the edge, where it is true in general and still
fails a cross-tab that attributes vehicles to the wrong edge, and pinned the eight pairs so
pre-positioning cannot quietly become something else. Spec §14.2 records why the fixture was
not changed to hide it.

Add to `tests/simulation/sumo/test_reproducibility.py`. It already imports `run_scenario`,
`BindingKind` and `pl`, and carries a module-level `pytestmark = pytest.mark.sumo`:

```python
def test_both_bindings_write_byte_identical_artifacts(tmp_path, repo_root):
    scenario = repo_root / "scenarios/s0_turning/v1"
    first = run_scenario(scenario, tmp_path / "libsumo", seed=1, binding=BindingKind.LIBSUMO)
    second = run_scenario(scenario, tmp_path / "traci", seed=1, binding=BindingKind.TRACI)

    relatives = sorted(path.relative_to(first) for path in first.rglob("*.parquet"))
    assert relatives, "the run wrote no parquet at all"
    for relative in relatives:
        assert (first / relative).read_bytes() == (second / relative).read_bytes(), relative
```

`manifest.json` is deliberately not compared: it carries two wall-clock timestamps that
differ between any two runs, which is what `NON_REPRODUCIBLE_FIELDS` exists to say.

- [ ] **Step 3: Run and watch them fail**

Run: `uv run pytest tests/test_cli.py tests/simulation/sumo/test_reproducibility.py -q`
Expected: failures on the missing directories — `run_scenario` still writes only
`manifest.json` and `events.parquet`.

- [ ] **Step 4: Let the connection ask SUMO for tripinfo**

`build_sumo_command` already takes `tripinfo_path: Path | None = None` and appends
`--tripinfo-output` and `--tripinfo-output.write-unfinished` (Task 6). `SumoConnection` is
what does not yet pass it. Add the parameter alongside `use_gui`, store it, and forward it:

```python
        tripinfo_path: Path | None = None,
```

```python
        command = build_sumo_command(
            self._config,
            self._paths,
            seed=self._seed,
            use_gui=self._use_gui,
            tripinfo_path=self._tripinfo_path,
        )
```

- [ ] **Step 5: Wire the recorder into the run loop**

In `src/cadence/cli.py`, inside `run_scenario`. `run_dir` is currently built after the loop;
move its construction above the `with` block so the recorder has somewhere to write. The
stamp it is named from comes from `started`, which is already available before the run.
Keep `exist_ok=False` — losing an artifact silently is worse than failing loudly.

```python
    log = EventLog()
    steps = 0
    tripinfo_xml = run_dir / "tripinfo.xml"
    with SumoConnection(
        config, paths, seed=seed, binding=binding, tripinfo_path=tripinfo_xml
    ) as connection:
        recorder = RunRecorder(run_dir, connection.topology)
        while not connection.is_finished():
            result = connection.step()
            log.append(result.events)
            recorder.record(result.state, result.teleports, connection.read_ground_truth())
            steps += 1
        terminal_time_s = connection.time_s()
        termination_reason = connection.termination_reason()
```

`EventLog.append` takes events, not a `StepResult`. It stays that way: `StepResult` grew a
canonical-state payload at Task 4, and `events.parquet` is still about events —
`DIRECTION.md` §7 item 1 asked which of the two happens, and this is the answer. The state
goes to `RunRecorder`, which is a sibling writer rather than an extension of the event log.

`termination_reason` is `TerminationReason | None`; `is_finished()` returning true
guarantees one of the two conditions holds, so a `None` here means the loop exited for a
reason nobody modelled. That is what `ABORTED` is for, and it is the only place the value is
ever produced:

```python
    if termination_reason is None:
        # The loop only exits when is_finished() is true, so neither condition holding means
        # something stopped it that nobody modelled. Record that honestly rather than
        # refusing to write a manifest for a run that did happen.
        termination_reason = TerminationReason.ABORTED
```

Pass `terminal_time_s`, `step_count=steps` and `termination_reason` into `build_manifest`,
then write the artifacts after the manifest and convert the trip file:

```python
    recorder.write()
    recorder.write_tripinfo(tripinfo_xml)
    tripinfo_xml.unlink()
```

SUMO writes the XML only when it closes, so the conversion happens after the `with` block.

- [ ] **Step 6: Run the integration tests**

Run: `uv run pytest tests/test_cli.py -q`
Expected: both pass.

Every number in the first test comes from a measured run recorded in spec §10.3. If one differs, the fixture or the extraction changed; report the discrepancy rather than editing the expectation.

- [ ] **Step 7: Run the reproducibility test**

Run: `uv run pytest tests/simulation/sumo/test_reproducibility.py -q`
Expected: pass.

A byte difference between bindings is a real finding, not flakiness. The most likely cause is dict-ordering leaking into a table's row order; every writer in `artifacts.py` iterates a sorted or insertion-stable structure for exactly this reason (`AP-06`).

- [ ] **Step 8: Update the direction document**

`docs/DIRECTION.md` §7 lists the four decisions M0 deferred. All four are now taken. Replace that table's rows with one line each recording where they landed — `ST-D08` for the artifact shape, `ST-D10` for the run outcome, `ST-D11` for the dirty digest, `ST-D12` for the `sumolib` boundary — and move `_approach_pairs` out of the deferred-minor list, since Task 1 fixed it.

Update §1 to read `M1a complete, M1b not started`, and add M1b to the ladder in §2 with the five questions spec §12 hands it.

- [ ] **Step 9: Full gate, then commit**

```bash
make check
git add -A
git commit -m "feat(cli): write canonical state, traversals and ground truth for every run"
```

- [ ] **Step 10: Regroup and open the pull request**

`CLAUDE.md` §10: a branch arrives as 3 to 6 commits, each a coherent unit. Nine task commits regroup naturally into five: the fixture and its generator; identifiers, signals and topology; canonical state, traversals and extraction; ground truth and the boundary; artifacts, manifest and the CLI that ties them together.

Count the commits against `origin/main`, not local `main`. A local base that is ahead of the remote makes the branch look shorter than the pull request will.

Run `make check` on the regrouped tip before pushing, and do not claim the intermediate commits are individually green unless you checked each one out and ran the suite.

---

## Self-Review

**Spec coverage.** §4 two type spaces → Tasks 2, 6. §5 canonical state → Tasks 2, 4. §5.2.1 the movement layer and the topology reference → Task 4. §5.3 signal decoding and `permits_movement` → Task 2. §5.4 identity and `movement_definition_v1` → Tasks 2, 3. §6 ground truth → Task 6. §6.1 the halting residual → Task 6a. §7 extraction → Tasks 4, 5. §7.1 traversal, keyed on the outgoing edge, with the teleport rule → Task 5. §8 artifacts including `tls_program`, `teleport` and `evaluation/` → Tasks 6a, 7, 9. §9.1 run outcome with `aborted` → Task 8. §9.2 dirty digest → Task 8. §10.1 `sumolib` boundary → Task 6. §10.2 `_approach_pairs` → Task 1. §10.3 `s0_turning/v1` → Task 1. §11 testing → across all ten, with the architecture tests in Task 6 and the twelve per-movement integers, successor legality and conservation in Tasks 6a and 9.

**What this plan asserts because it was measured, not predicted.** 315 traversals and the twelve per-movement integers, both run against the fixture before the plan was written; 306 for the lane-pair key and 322 for the via-lane key, so an implementer who lands on either knows immediately which mistake they made; nine null connection ids; 121 same-approach lane changes; 16 lanes and 16 controlled connections; a drain at 558.0 s. Every number in a test here came from executing something.

**Deliberate omissions, recorded rather than dropped.** The spec's §11 asks that `mean_speed_mps` stay within the lane's maximum; SUMO reports the maximum for an empty lane, so the naive assertion fails on an empty lane and the useful one needs an occupancy guard that belongs with M1b's derived quantities. The lamp alphabet is checked character by character rather than by a Hypothesis strategy, which is stronger for a finite set where each member has a named expectation. `s0_turning/v1` has zero teleports, so Task 5's teleport rule is covered by a unit test against a fake binding and not by the integration fixture — the fixture cannot exercise it, and inventing a teleporting fixture to prove one rule is more scenario than the rule is worth.

**Type consistency — checked, not asserted.** The previous version of this paragraph claimed three things were consistent that were not, because it was written from what the author intended rather than from reading the plan. This one was produced by grepping the document for every construction and call site of every type it defines:

| Type or call | Defined | Every construction matches |
|---|---|---|
| `CanonicalTrafficState`, 7 fields | Task 4 | 3 of 3 carry `topology=`, `movements=`, `traversals=` |
| `NetworkTopology`, 4 fields | Task 3 | 2 of 2 carry `phases=` |
| `MovementState` | Task 4 | constructed by `StateExtractor._movements`, asserted in Tasks 4 and 7 |
| `Traversal`, 4 fields | Task 5 | written in Task 7 with a null-preserving `connection_id` |
| `TeleportEvent`, 4 fields | Task 6a | built in Task 5's `step()` from the detector's held lane |
| `StepResult` | Task 5 | no `traversals` field; every reader uses `result.state.traversals` |
| `extract(binding, time_s, events, traversals)` | Task 4 | 3 call sites, all four arguments |
| `RunRecorder.record(state, teleports, truth)` | Task 7 | 4 call sites, none passing `traversals` |
| `write_tripinfo(path)` | Task 7 | called once, in Task 9, after the `with` block |
| `tls_program.parquet` | Task 7 | writer emits phase × connection; Task 9 asserts `4 * 16` |
| `unmatched_traversals()` | Task 5 | defined on `SumoConnection`, read in Task 5's integration test |

`Traversal` and `TeleportEvent` are defined in `state.py`, not `events.py`. Defining them the other way makes `state.py` import `events.py` for `Traversal` while `events.py` imports `state.py` for `CanonicalTrafficState`, which is a top-level cycle. Imports run one direction: `events.py` → `state.py`.

**One thing the plan cannot check for itself.** Twenty-one findings were raised against the specification this plan implements, across two review rounds, and none of them were in code, because there was no code. Three of the eight in the second round were holes the first round's fixes had opened. An implementer who finds a number here that does not match reality has found the twenty-second, and the instruction throughout is the same: report it, do not adjust the expectation to match.
