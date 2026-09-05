# M1a — Canonical State and Ground-Truth Foundation

**Status:** adopted
**Milestone:** M1a (first half of `PD-D02` M1)
**Supersedes nothing.** Resolves `docs/DIRECTION.md` §7 items 1-4.

M1 is split in two. **M1a** builds the state layer and the run artifacts. **M1b** builds
the metric registry, the turn-ratio estimator, the derived metrics, and `cadence
verify-run`. M1b is deliberately gated on inspecting real M1a Parquet output rather than
designing against an assumed schema — the same discipline that made M0 hand M1 four
decisions it was not yet qualified to take.

---

# 1. What M1a Is For

A controller cannot be written until there is a domain state to consume, and a result
cannot be trusted until the run that produced it is fully described on disk. M1a delivers
both, and it draws one line that everything after it depends on: **which information a
controller is allowed to see.**

That line is not a realism claim. It is a **parity** claim (`ST-D14`).
`CanonicalTrafficState` still
contains quantities no field deployment could measure — the halting count over an entire
lane is not what a single loop detector returns. What the line guarantees is that every
controller CADENCE compares receives the same information, so a difference in outcome is a
difference in policy. Realism is a separate, later concern belonging to the
`SensorRealisticAdapter` sketched in `ARCH §7`, which is not in any current milestone.

---

# 2. Decisions

| ID | Statement |
|---|---|
| `ST-D01` | Canonical state and simulation ground truth are two distinct type spaces in two modules. Controller-facing code cannot reach the second. |
| `ST-D02` | That separation is enforced by three mechanisms together — banned-api lint, an import architecture test, and `mypy --strict`. No one of them is sufficient. |
| `ST-D03` | *Superseded by `ST-D17`.* Canonical state carries only quantities the simulator reports directly. Every derived quantity belongs to M1b. |
| `ST-D04` | Signal state is a typed enum decoded inside `simulation/sumo/`. No lamp string leaves that package, including into an artifact. |
| `ST-D05` | `ConnectionId`, keyed on the ordered lane pair, is the lowest stable control grain. The TLS link index is recorded but is not an identity. |
| `ST-D06` | `movement_definition_v1`: a `MovementId` is the ordered edge pair; a movement groups one or more connections. |
| `ST-D07` | *Superseded by `ST-D16`.* Traversal identity is the `(incoming lane, outgoing lane)` transition, not presence on a via lane. |
| `ST-D08` | *Extended by `ST-D18`, which adds `evaluation/`.* Run artifacts are partitioned into `topology/`, `state/`, and `ground_truth/`. `events.parquet` keeps its M0 schema; traversals get a sibling table. |
| `ST-D09` | Ground truth is read through an explicitly named method. `step()` never returns it. |
| `ST-D10` | The manifest records the run outcome: terminal time, step count, and termination reason. |
| `ST-D11` | A dirty working tree is hashed, not rejected. |
| `ST-D12` | All three SUMO surfaces — `traci`, `libsumo`, `sumolib` — live under `simulation/sumo/`. |
| `ST-D13` | `s0_turning/v1` is a separate immutable scenario whose network file is byte-identical to `s0_single_intersection/v1`'s by construction. |
| `ST-D14` | Canonical traffic state is a controller-parity layer, not a claim of deployment or sensor realism. |
| `ST-D15` | Canonical state carries a movement layer and the step's traversals, so a controller can estimate turn ratios online without reaching for privileged data. |
| `ST-D16` | Traversal identity is the `(incoming lane, outgoing edge)` transition. The connection is recorded when the exit lane resolves to one, and left null when the vehicle changed lane inside the junction. |
| `ST-D17` | Canonical state carries only quantities the simulator reports directly. Every derived **interpretive** quantity — one whose definition could reasonably differ — belongs to M1b. Topology identity and observable traversal are derivations M1a owns. |
| `ST-D18` | Post-hoc per-trip evaluation data is not privileged. `tripinfo` lives in `evaluation/`, and `--tripinfo-output` is enabled from M1a. |
| `ST-D19` | The run records the signal program definition, the lane a teleport left from, and the cross-tab's unattributed residual, so no question M1b through M9 can ask requires re-running the simulation. |

---

# 3. Evidence

Every decision below rests on a measurement taken on this repository's own S0 network
before the decision was made. They are recorded because re-deriving them is expensive and
because two of them contradict what a reasonable person would assume.

## 3.1 Extraction is nearly free, and subscriptions are for TraCI only

520 steps, 16 lanes, five variables per lane.

| binding | mode | µs/step | delta |
|---|---|---|---|
| libsumo | no extraction | 54.8 | — |
| libsumo | individual getters | 67.6 | +12.8 |
| libsumo | subscriptions | 76.7 | +21.9 |
| traci | no extraction | 202.9 | — |
| traci | individual getters | 2497.1 | +2294 |
| traci | subscriptions | 390.3 | +187 |

Subscriptions cost 9 µs/step under `libsumo` and save 2100 µs/step under `traci`. The
extractor uses subscriptions unconditionally — not because the table says so for `libsumo`,
where it does not, but because §11 requires the two bindings to produce byte-identical
artifacts and two extraction paths would put that at risk for a saving of 9 µs. Anyone
optimising the `libsumo` path later on the strength of this table alone will break the
reproducibility test without understanding why. `libsumo` has no socket, so the round-trip
saving that motivates subscriptions does not exist there — only their bookkeeping does.

## 3.2 Recorded state is small enough that offline metrics are the cheap option

A per-step lane-state table written to Parquet measures **3.4 bytes per row**: dictionary
encoding collapses the lane id and most columns are zero for most of the run.

| | rows | size |
|---|---|---|
| S0, whole run | 8,320 | 28 KB |
| M8 corridor, 60 lanes, 1 h | 216,000 | ~0.7 MB |
| 200-lane network, 1 h | 720,000 | ~2.4 MB |

For contrast, SUMO's `--fcd-output` measures 135 bytes per vehicle-record, which is 73-244
MB for one M8 corridor run. Recording canonical state is three orders of magnitude cheaper
than the artifact the project already considered acceptable.

**What this measurement does not support.** 3.4 bytes/row comes from S0, where most columns
are zero for most of the run — and that sparsity is precisely what disappears under regimes
C and D, where every row carries a non-zero speed, occupancy and waiting time. The realistic
M8 figure is more like 15-30 B/row, so a corridor hour is single-digit megabytes rather than
0.7. The conclusion survives that by two orders of magnitude; the number quoted for it does
not, and citing 3.4 B/row as an M8 estimate would be wrong.

## 3.3 A TLS link index is not an identity

`netconvert -s network.net.xml --tls.group-signals true`, run on the committed S0 network:

```
                            lamp width   indices   connections
as committed                        16        16            16
with --tls.group-signals             8         8            16

  idx 0 <- top0A0_0->A0left0_0, top0A0_0->A0bottom0_0, top0A0_1->A0bottom0_1
  idx 2 <- right0A0_0->A0top0_0, right0A0_0->A0left0_0, right0A0_1->A0left0_1
  idx 4, idx 6  likewise
```

The same physical junction yields two different index sets depending on a conversion flag.
Signal grouping is how real signal heads are wired, so an OSM import at M7 is likely to use
it. A `MovementId` derived from a link index would not survive re-importing the same site
(`ST-D05`, `ST-D06`).

## 3.4 Turn intent is affordable, and is privileged information

Resolving every active vehicle's next edge from its route, at ~28 vehicles per step:

| binding | mode | µs/step | delta |
|---|---|---|---|
| libsumo | none | 54.6 | — |
| libsumo | resolve every step | 76.9 | +22.3 |
| libsumo | route cached at departure | 66.9 | +12.3 |
| traci | resolve every step | 2566.7 | +2337 |

0.44 µs per vehicle per step under `libsumo` with the route cached. An M8 corridor at 800
active vehicles costs ~0.35 ms/step, or ~1.3 s over a one-hour run.

Affordable, and not observable. On a shared lane no sensor reports how many of the queued
vehicles intend to turn. This is why it is `SimulationGroundTruth` and not canonical state
(`ST-D01`).

## 3.5 Via-lane presence over-counts traversals

Counting a discharge as "seen on an internal lane" was tested against the vehicle ledger:

| fixture | vehicles | via-lane detections | error |
|---|---|---|---|
| `s0_single_intersection/v1` (all straight) | 320 | 321 | +0.3% |
| `s0_turning/v1` candidate | 315 | 322 | +2.2% |

The excess is vehicles that change lane inside the junction and are therefore observed on
two internal lanes. Turning traffic makes it seven times worse. No vehicle was ever missed
— every one of the 320 was seen on an internal lane at a 1 s step — so the failure is
over-counting, not under-counting. Keying on the `(incoming lane, outgoing lane)` pair is
exact, because no two connections share that pair (`ST-D07`).

## 3.6 S0 exercises half of its own network

`s0_single_intersection/v1` has four flows, all straight through. Eight of the sixteen
controlled links never carry a vehicle, and the shared approach lanes the network defines —
every one of them serves two movements — are never exercised by the demand. A fixture whose
stated purpose includes metric verification cannot verify a movement metric on data that
contains no movements (`ST-D13`).

---

# 4. Two Type Spaces

```
src/cadence/simulation/
    state.py           CanonicalTrafficState    what a controller may consume
    ground_truth.py    SimulationGroundTruth    privileged simulator truth
    sumo/extract.py    builds both from one step
```

`SimulationGroundTruth` exists for validation, debugging, and — later, explicitly labelled —
oracle experiments. It is never an input to a controller or to a normal observation adapter.

## 4.1 Enforcement (`ST-D02`)

Three mechanisms, because each covers a hole the others leave open.

| Mechanism | Catches | Misses |
|---|---|---|
| ruff `TID251` banning `cadence.simulation.ground_truth` outside `simulation/` | a direct import | an import laundered through a re-export |
| architecture test scanning every module under `src/cadence/` that is not under `simulation/` | any import path, including re-exports | passing the object in as an argument |
| `mypy --strict`, which rejects an unannotated parameter | the argument path: annotating the parameter requires the import the first two forbid | nothing relevant, while `--strict` holds |

The third is the one that matters and the one that is easiest to lose. If `--strict` is
ever relaxed for a package, this boundary silently relaxes with it. The architecture test
therefore also asserts that `mypy` strictness is not disabled for any package under
`src/cadence/`.

More than one module legitimately holds both types: anything that writes the run directory
touches both spaces at once. The privileged set is `simulation/ground_truth.py`,
`simulation/artifacts.py`, `simulation/sumo/extract.py`, `simulation/sumo/connection.py`
and `cli.py`. That list, asserted exactly, is the load-bearing guard — a sixth entry
appearing without a deliberate edit is the finding, and describing the set as "the metrics
and validation paths" would have been wrong on the day it was written.

The architecture test is written as a scan of everything under `src/cadence/` outside
`simulation/`, not as a list of directory names. `control/` does not exist yet; a test
naming it would pass vacuously today. Written as a scan, the test has real subjects now
(`cli.py`, `types.py`) and acquires `control/` automatically on the day it appears.

## 4.2 The artifact boundary

An import ban does not constrain a file read. An offline dataset loader at M5 could read
ground-truth Parquet without importing anything. The run directory is therefore partitioned
along the same line as the type space (`ST-D08`), and a test asserts that no module outside
the metrics and validation paths references the `ground_truth` directory name.

---

# 5. Canonical State

## 5.1 The M1a / M1b line (`ST-D17`, superseding `ST-D03`)

**M1a records what the simulator reports. M1b computes what we interpret.**

`ST-D03` said "every derived quantity belongs to M1b", which this document then contradicts
twice: `movement_definition_v1` in §5.4 and traversal detection in §7 are both derivations
M1a performs. The line is not derivation, it is **interpretation**. A derived quantity whose
definition could reasonably differ — how a shared lane's queue divides, what window a turn
ratio uses — carries a version and belongs to the registry at M1b. A derived quantity with
one defensible answer — which edge pair a connection belongs to, which movement a vehicle
just completed — is structure, and M1a owns it.

`ARCH §6` lists `queue_length_m`, `storage_capacity_estimate`, and
`available_storage_ratio` as candidate `LaneState` fields. All three are derived — from
halting-vehicle positions, from lane length against vehicle length and minimum gap, from
both — and every one of them embeds an interpretation that `PD-D04` requires to carry a
version. They belong to M1b, where the registry that versions them exists.

The consequence is that `LaneState` in M1a holds exactly the quantities with a direct
getter, and nothing that needs an argument about how it was computed.

## 5.2 Types

All state objects are frozen slotted dataclasses. They are constructed once per step per
entity, so Pydantic's validation cost is not warranted; `SimulationEvent` already
established this pattern in M0.

```python
@dataclass(frozen=True, slots=True)
class LaneState:
    lane_id: LaneId
    vehicle_count_veh: int
    halting_count_veh: int
    mean_speed_mps: float
    occupancy_ratio: float
    waiting_total_now_s: float


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

`topology` is the same immutable object for every step of a run, held by reference rather
than copied. Its mappings are `MappingProxyType`, not bare dicts: a frozen dataclass freezes
its fields, not what they point at, and an adapter that mutated `state.topology.movements`
would corrupt every later step of the run and every step already recorded. And
`CanonicalTrafficState` is declared `eq=False`: with structural equality it would deep-compare
the whole topology on every comparison, for a value that is identical by construction. Without it the movement layer is decorative: `MovementState` names a movement
and `LaneState` names a lane, and nothing in canonical state connects the two, so an
adapter still cannot find the lanes incident to a movement. It would have had to reach into
`topology/connection.parquet` — which is not canonical state — or into
`SimulationGroundTruth`, which is the outcome §5.2.1 exists to prevent. One reference makes
"a controller consumes canonical state" literally true rather than nearly true.

For the same reason `LaneState` carries no `edge_id`: `topology.lanes[lane_id].edge_id`
already answers it, and a duplicated field is a field that can disagree.

`lanes` covers the network's ordinary lanes and excludes SUMO's internal (`:junction`)
lanes. S0's sixteen in §3.1 and §3.2 are that set, and the sizing figures follow from it.
Junction occupancy is not lost: a vehicle inside the junction has already produced the
traversal that says which movement it is completing.

## 5.2.1 Why the movement layer is here and not at M1b (`ST-D15`)

`ARCH §7` defines an `OriginalMaxPressureAdapter` that reads movement queues, turn ratios
and service rates **from canonical state**, and `ARCH-D03` requires every controller to
consume canonical state rather than raw simulator data. Max-Pressure runs online at M8.

Without a movement layer there are exactly two ways to reach M8, and both are bad: reopen
this interface — the central type every controller depends on — after three milestones have
been built on it, or let Max-Pressure read `SimulationGroundTruth`, which is the invisible
information advantage that voids the M9 comparison the project exists to make. Closing the
gap now costs one mapping and one tuple.

`MovementState` carries no queue. A movement queue needs an attribution rule for shared
lanes, that rule is an interpretation, and interpretations are versioned at M1b — the
boundary of `ST-D17` holds. What it carries is the signal each contributing connection
shows, which is measured, and which is what a controller needs to know whether a movement
is being served at all. `SignalState` gains a `permits_movement` property so no adapter has
to reinvent which of the eight values is a go; the classification is SUMO's, not ours.

`traversals` carries the completed movements of the step just taken. This is the stream a
turn-ratio estimator consumes, and putting it in canonical state is what lets that estimator
run online at M8 from observable data alone. A traversal is observable — one camera at the
junction sees which way a vehicle went — so it is canonical, not privileged.

GOTCHA, and the reason `NetworkState` carries `_total_` fields the extractor must
accumulate: `simulation.getDepartedNumber()` and `getLoadedNumber()` report the count for
the step just taken, not a running total. Measured at t=120 on a run with 100+ departures
already behind it, both returned 0.

## 5.3 Signal state without lamp strings (`ST-D04`)

`ARCH §13` forbids raw lamp strings outside the signal safety layer. Decoding at extraction
extends that rule to the artifacts as well: nothing downstream, in code or in Parquet, ever
sees `"GGGgrrrrGGGgrrrr"`.

PROVENANCE for the character set: SUMO's own `data/xsd/types/base.xsd`, shipped with the
`eclipse-sumo` distribution, restricts a phase state to `[ruyYgGoOs]+`. The meanings below
are from SUMO's Traffic Lights documentation.

```python
class SignalState(StrEnum):
    RED = "red"                                  # r
    YELLOW = "yellow"                            # y
    RED_YELLOW = "red_yellow"                    # u  about to turn green; may not proceed
    GREEN_PROTECTED = "green_protected"          # G  green with priority
    GREEN_PERMISSIVE = "green_permissive"        # g  green, must yield to priority foes
    GREEN_STOP_THEN_GO = "green_stop_then_go"    # s  green arrow, must stop first
    OFF_YIELDING = "off_yielding"                # o  off, blinking; must yield
    OFF_PRIORITY = "off_priority"                # O  off, no signal; has right of way
```

GOTCHA: the XSD permits a ninth character, `Y`, that SUMO's documented table does not
describe. The decoder raises on it rather than mapping it to a guess. If a network ever
produces one, that must be a loud failure, because the safety layer at M2 will act on
whatever this enum says.

S0 uses only `G g y r`. The remaining values are covered because an OSM import at M7 is
where the others appear.

## 5.4 Connection and movement identity

```python
ConnectionId = NewType("ConnectionId", str)   # "top0A0_0|A0bottom0_0"
MovementId   = NewType("MovementId", str)     # "top0A0->A0bottom0"
```

A `ConnectionId` is the ordered lane pair, which is unique by construction: two connections
cannot share both endpoints. It derives from lane ids, which derive from edge ids, which
derive from OSM way ids — so it survives a re-conversion of the same site, which a link
index does not (§3.3).

`movement_definition_v1` (`ST-D06`) is a static derivation performed once when a connection
opens. It carries a version despite `ST-D17` calling it structure, and the two are
reconcilable but only just: grouping by edge pair has one defensible answer *given that a
movement is an edge pair*, and that premise is itself a choice — movement as
`(approach, turn direction)` is the other one, and a network with two parallel edges between
the same junctions would separate them. The version is there so that choice can be revisited
without silently reinterpreting every metric computed under the first. Structure that could
have been drawn differently still earns a version; structure with genuinely one answer, like
which edge a lane belongs to, does not.

```python
class TurnDirection(StrEnum):
    STRAIGHT = "straight"                 # s
    TURN = "turn"                         # t   u-turn
    TURN_LEFTHAND = "turn_lefthand"       # T
    LEFT = "left"                         # l
    RIGHT = "right"                       # r
    PARTIALLY_LEFT = "partially_left"     # L
    PARTIALLY_RIGHT = "partially_right"   # R


@dataclass(frozen=True, slots=True)
class MovementDefinition:
    movement_id: MovementId
    from_edge_id: EdgeId
    to_edge_id: EdgeId
    turn_direction: TurnDirection
    connection_ids: tuple[ConnectionId, ...]
```

```python
@dataclass(frozen=True, slots=True)
class NetworkTopology:
    lanes: Mapping[LaneId, LaneInfo]
    connections: Mapping[ConnectionId, ConnectionInfo]
    movements: Mapping[MovementId, MovementDefinition]
    phases: tuple[PhaseInfo, ...]
```

PROVENANCE for `TurnDirection`: the `LINKDIR_*` constants in `sumolib.net.connection`,
which that module states are taken from `sumo/src/utils/xml/SUMOXMLDefinitions.cpp`. The
direction is read from SUMO rather than recomputed from geometry, so the project owns no
second opinion about what counts as a left turn.

`MovementState` exists in M1a and carries no queue, for the reasons in §5.2.1. A movement
queue requires a versioned attribution rule for shared lanes; that rule is M1b's.

---

# 6. Ground Truth

```python
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

A cross-tab of lane against intended next edge, rather than one row per vehicle. It is what
every movement-queue definition needs, it is an order of magnitude smaller than per-vehicle
rows, and only rows with a non-zero count are written.

The intent comes from the vehicle's route, cached at departure and discarded on arrival.
**Rerouting is out of scope for M1a and the cache assumes a static route.** A scenario that
reroutes would make this stream silently stale, and since it is the stream M1b validates the
non-privileged estimator against, the error would propagate into the estimator's accuracy
claim rather than being caught by it. Any milestone that enables rerouting must invalidate
the cache on `VEHICLE_REROUTE` and say so.

## 6.1 Two definitions of halting, and the residual that reconciles them

`LaneState.halting_count_veh` is SUMO's own `getLastStepHaltingNumber`.
`LaneTurnCount.halting_count_veh` cannot be a getter — a cross-tab has to be built by
iterating vehicles — so it compares each vehicle's speed against a project constant. The two
can disagree in four ways, and matching the numeric threshold removes only the first:

1. **Threshold ownership.** SUMO's is internal and can change across versions; ours is in
   the source. Two numbers that agree today are not the same number.
2. **Sampling point.** SUMO aggregates over the step; a Python loop reads end-of-step speed.
3. **Lane membership.** `getLastStepHaltingNumber` uses SUMO's last-step occupancy;
   `vehicle.getLaneID()` returns the lane the front occupies at the end of the step.
4. **Vehicle scope.** A vehicle on its final edge has no next edge and appears in no
   `LaneTurnCount` row, while `getLastStepHaltingNumber` counts it. **No threshold choice
   fixes this one.**

Forcing agreement would mean computing the canonical count per vehicle too, which moves
`halting_count_veh` from a direct getter to a derived quantity with an embedded
interpretation and pushes it to M1b. That is the wrong trade. Instead the difference is recorded (`ST-D19`), and **it needs a row of its own**. Attaching
a per-lane residual to every per-`(lane, next_edge)` row double-counts it the moment a lane
serves two movements, and a lane whose vehicles are *all* on their final edge emits no row
at all under the non-zero rule — which on `s0_turning` is every one of the eight exit lanes,
so the residual would go unrecorded for half the network and the conservation test would
silently skip them.

So: one row per `(lane, next_edge)` with a non-zero count, **plus one row per lane in
`topology` with `next_edge_id` null**, carrying the unattributed counts and written whether
or not they are zero. §11's identity is then a sum over all rows of a lane, and a missing
null row is itself a failure. When M1b validates `movement_queue_proportional_split_v1` against this stream and a
residual appears, the recorded column says immediately whether it is an attribution error or
a definitional artefact. Without it that distinction is unrecoverable and the estimator's
accuracy claim is unfalsifiable.

`HALTING_SPEED_MPS` carries a provenance comment naming SUMO's own threshold as its source,
so the coupling is documented rather than coincidental.

---

# 7. Extraction

```python
result = connection.step()                # observable only
truth  = connection.read_ground_truth()   # privileged, named, greppable
```

`step()` deliberately does not return ground truth (`ST-D09`). Reaching for privileged
information should be an act visible in a diff and findable with `grep`, not a field that
arrives whether or not anyone wanted it. The cost is a second pass over the active vehicle
list, measured at roughly 0.5 µs per vehicle per step (§3.4) — below the noise floor of the
step itself.

`StepResult` grows to carry the state alongside the events, resolving the first half of
`docs/DIRECTION.md` §7 item 1:

```python
@dataclass(frozen=True, slots=True)
class StepResult:
    time_s: float
    events: tuple[SimulationEvent, ...]
    state: CanonicalTrafficState
    teleports: tuple[TeleportEvent, ...]
    expected_remaining_veh: int
```

Traversals live on `state`, not here. Carrying them in both places would be two sources for
one fact with nothing asserting they agree.

## 7.1 Traversal detection (`ST-D16`, superseding `ST-D07`)

```python
@dataclass(frozen=True, slots=True)
class Traversal:
    time_s: float
    vehicle_id: VehicleId
    movement_id: MovementId
    connection_id: ConnectionId | None
```

`ST-D07` said the key is the `(incoming lane, outgoing lane)` pair. **Measured, that key
loses nine of 315 vehicles.** A vehicle that changes lane inside the junction leaves
`left0A0_1` and arrives on `A0right0_0`, and that pair is not a declared connection, so it
matches nothing and is dropped in silence:

```
key = (from_lane, to_lane)      matched 306 of 315 departed,  9 dropped
key = (from_lane, to_edge)      matched 315 of 315 departed,  0 dropped
```

The key is therefore the **movement**: the incoming lane and the outgoing *edge*. That pair
resolves to exactly one movement by construction, since a movement *is* the edge pair and
every connection from a given lane to a given edge belongs to the same one. It does not
always resolve to one connection — SUMO permits a lane to connect to two lanes of the same
edge, and on a multi-lane exit at M7 it will — which is the other reason the connection is
nullable rather than merely unavailable after a lane change. The exact connection is recorded when the exit lane matches a declared one and left
null otherwise — nine times in 315 on the turning fixture, and a reader that needs
connection-level detail can see precisely how often it is unavailable rather than inferring
it from a shortfall.

Five rules make the detection complete rather than merely unique:

- The last observed lane is held while a vehicle is on an internal lane. An internal lane is
  a waypoint, not a destination. §3.5 measured that a vehicle is *usually* seen on the via
  lane, so a rule that compares the immediately preceding lane would almost never fire.
- A transition between two lanes of the same edge is a lane change, not a traversal. There
  are 121 of them on the turning fixture.
- A transition out of an approach lane that matches no movement is counted as unmatched and
  reported. §3.5 measured the via-lane method's over-count; it never measured detection
  completeness, and a silent undercount at M8 with multi-lane exits would look like light
  demand rather than a defect.
- **A teleport clears the vehicle's held lane** — after the held lane has been read.
  `getLaneID()` returns an empty string for a vehicle mid-teleport, so the lane it left is
  recoverable only from what the detector is already holding, and reading it after clearing
  would put an empty string in the one column `state/teleport.parquet` exists for. SUMO removes a stuck vehicle and reinserts
  it downstream, so without this the detector compares an approach lane against a lane the
  vehicle never drove to, and either fabricates a traversal that never happened — if the
  downstream edge happens to be a legal successor — or trips the unmatched counter. The
  turning fixture has zero teleports, so M1a would pass either way; under regimes C and D
  teleports are routine and they would pollute the very stream M1b validates the
  non-privileged estimator against. The same clearing covers a vehicle removed mid-junction.

Keying above the lane also makes detection independent of step length: a network whose
internal links are short enough to be skipped at a 1 s step still produces the transition.

The twelve per-movement totals this yields on `s0_turning/v1` are exactly the twelve the
demand was built from (§10.3), which is the check §11 now makes.

A traversal is observable — a single camera at the junction sees which way a vehicle went —
so it is canonical, not privileged, and the M1b estimator that consumes it stays on the
non-privileged path from end to end.

---

# 8. Run Artifacts (`ST-D08`)

```
run_dir/
  manifest.json
  events.parquet            unchanged from M0
  topology/
    lane.parquet            lane_id, edge_id, lane_index, length_m, max_speed_mps
    connection.parquet      connection_id, intersection_id, link_index, from_lane_id,
                            to_lane_id, via_lane_id, from_edge_id, to_edge_id,
                            turn_direction, movement_id
    tls_program.parquet     intersection_id, program_id, phase_index, duration_s,
                            min_duration_s, max_duration_s, connection_id, signal
  state/
    lane.parquet            time_s, lane_id, vehicle_count_veh, halting_count_veh,
                            mean_speed_mps, occupancy_ratio, waiting_total_now_s
    intersection.parquet    time_s, intersection_id, program_id, phase_index,
                            phase_elapsed_s
    signal.parquet          time_s, connection_id, signal
    network.parquet         time_s, active_veh, pending_insertion_veh, departed_total_veh,
                            arrived_total_veh, teleport_total_veh
    movement.parquet        time_s, movement_id, connection_id, signal
    traversal.parquet       time_s, vehicle_id, movement_id, connection_id (nullable)
    teleport.parquet        time_s, vehicle_id, from_lane_id, kind
  ground_truth/
    lane_turn.parquet       time_s, lane_id, next_edge_id (null = unattributed),
                            count_veh, halting_count_veh, waiting_total_now_s
  evaluation/
    tripinfo.parquet        converted from SUMO's --tripinfo-output
```

`topology/` is written once per run rather than referenced from the scenario, so a run
directory is self-describing: reading it requires no access to the network file that
produced it. `tls_program.parquet` is what makes that claim true rather than aspirational.
Without it `phase_index` is an integer with no recorded meaning, §11's `phase_elapsed_s <=
phase duration` has no source, minimum and maximum green are recoverable from nothing, and
a phase that is never served leaves no row in `state/signal.parquet` at all — which is
exactly the starvation case §12 flags as needing a test. M2's action mask and M3's
fixed-time tuning both need the phase set.

`teleport.parquet` records the lane a teleport left from. Under regimes C and D a teleport
fabricates discharge on one specific approach, and at M9 the question "did Max-Pressure's
advantage come from service, or from gridlock removal on the blocked approach?" has to be
answerable from the run directory rather than by re-running it.

**`tripinfo` is not privileged, and belongs in `evaluation/` (`ST-D18`).** It is post-hoc
per-trip data — travel time, time loss, waiting time — that no controller could see under
any design, because the trip has ended. Filing it under `ground_truth/` would force every
M1b, M3 and M6 metric module into §4.2's allowlist, and a privileged partition that the
whole metrics package must read has stopped meaning anything. `--tripinfo-output` is added
to the SUMO command at M1a: it is absent today, and M1b's trip metrics have no other source.

**With `--tripinfo-output.write-unfinished`**, which is not optional here. SUMO writes no
row for a vehicle still in the network when the run ends, and under regimes C and D a run
ends at the horizon with exactly the most delayed trips unfinished. Censoring those is not a
small bias — it removes the tail the whole research question is about, and it would make
`ST-D19`'s "no question requires re-running" false for the one metric family M6 compares
controllers on.

Two tables at the two static grains rather than one, because a lane and a connection are
different things and a single table would leave outgoing lanes unrepresented.

The column is `intersection_id` in every table. An earlier draft called it `tls_id` in
`connection.parquet` and `intersection_id` in `intersection.parquet`, which are the same
entity under two names with no stated join key. At M8 a joined signal program controlling
more than one junction would make them genuinely distinct; until a milestone needs that
distinction, one name is one entity.

`traversal.parquet` is a sibling table, not a fourth column on `events.parquet`. This is
what `docs/DIRECTION.md` §7 item 1 asked for in its own words, and it keeps every M0
artifact readable under the schema it was written with.

Per-step rows are written for signal state rather than a change log. A change log would be
roughly twenty times smaller — S0's program changes state four times per 90 s cycle — but
per-step rows need no forward-fill to read, and the table is 30 KB. At M8 corridor scale it
is still under 2 MB (§3.2).

This artifact set satisfies the four reconstruction requirements M1b depends on:

| M1b needs | comes from |
|---|---|
| service opportunity | `state/signal.parquet` and `state/intersection.parquet` |
| completed movements | `state/traversal.parquet` |
| connection identity | `topology/connection.parquet` |
| canonical state | `state/` |
| privileged exact intent | `ground_truth/lane_turn.parquet` |
| the phase set, including phases never served | `topology/tls_program.parquet` |
| where a teleport removed a vehicle from | `state/teleport.parquet` |
| per-trip travel time, time loss, waiting | `evaluation/tripinfo.parquet` |

---

# 9. Manifest

## 9.1 Run outcome (`ST-D10`)

`docs/DIRECTION.md` §7 item 2: the M0 manifest records nothing about how the run ended. S0
drains at 520 s of a 600 s horizon, and two runs differing in termination reason are
indistinguishable from their manifests. New fields:

```
terminal_time_s      float
step_count           int
termination_reason   "drained" | "horizon" | "aborted"
```

`aborted` covers every other way a run can stop — a simulator error, an external kill, a
gridlock the harness declines to sit through. Two values would have meant that a run ending
any other way produces no manifest at all rather than an honest one, and under
oversaturation a run that neither drains nor reaches the horizon is a normal outcome.

`SumoConnection.is_finished()` currently collapses two conditions into one boolean. It gains
a companion that reports which one fired.

## 9.2 Dirty working tree (`ST-D11`)

`docs/DIRECTION.md` §7 item 3: `cadence_dirty` is a boolean, so two runs from two different
uncommitted trees compare equal across every reproducible field.

```
cadence_dirty_digest   str | None
```

`sha256` over the combined output of `git diff HEAD` and `git status --porcelain -uall`,
and `None` when the tree is clean. The two together cover modified tracked files and the
presence of untracked ones.

**The limit, stated rather than discovered:** `git status --porcelain` lists untracked
*paths*, not their content. Two runs launched from two materially different versions of the
same untracked Zone B study script produce identical digests. Closing that would mean
hashing arbitrary untracked content, which sweeps in every scratch file and cache; the
digest is a strong signal for tracked work and a weak one for untracked, and M1b's
`verify-run` should say which it had.

The digest joins `reproducible_fields()`, which means two runs from different dirty trees
already compare unequal in M1a. `verify-run` at M1b therefore adds the *refusal* and the
explanation, not the detection.

Hash rather than fail. Research is conducted from dirty trees; most runs are exploratory and
most exploratory runs are never cited. A hard failure would be routed around with junk
commits, which destroys the history that makes `cadence_commit` worth recording in the
first place. The stderr warning added in M0 stays. Refusing to *compare* two runs when either
carries a digest is `cadence verify-run`, in M1b.

---

# 10. Carried-In Fixes

## 10.1 `sumolib` joins the boundary (`ST-D12`)

`docs/DIRECTION.md` §7 item 4. §3 of `CLAUDE.md` bans `traci` and `libsumo` outside
`simulation/sumo/` but says nothing about `sumolib`, and `validation.py` sits in
`simulation/` handling `sumolib.net.Net` directly.

The extraction path needs none of it — `trafficlight.getControlledLinks()` returns the
link-index-to-lane-triple mapping and `lane.getLinks()` carries the direction character, so
topology comes from the live binding. `sumolib` survives in exactly one place: validating a
scenario *before* SUMO is started, which is the whole point of that module.

`validation.py` moves to `simulation/sumo/validation.py` and `sumolib` is banned outside
`simulation/sumo/` by the same mechanism as the other two. The rule becomes one sentence:
every SUMO surface lives under `simulation/sumo/`.

## 10.2 `_approach_pairs`

`docs/DIRECTION.md` §7 records this in bold as something that "must be fixed before it is
reused". Generating the `s0_turning` demand reuses it — now, at M1a, not at M7 as the note
assumed. Three fixes, each with a named constant and a provenance comment:

- `_unit_direction` divides by `math.hypot` with no zero-length guard.
- The winning alignment is never checked to be near 1, so on a T-junction or an irregular
  angle the least-bad turn is silently labelled straight-through. It must clear a named
  minimum.
- The winner must beat the runner-up by a named margin, or the pairing is ambiguous and the
  function raises rather than choosing.

## 10.3 `s0_turning/v1` (`ST-D13`)

A separate scenario, not a version of the existing one: the straight-only fixture and the
turning fixture have different enduring purposes, and a version number would incorrectly
imply replacement.

`tools/build_s0_scenario.py` grows to write both scenario directories from one `main()`.
The network file is duplicated into each rather than shared by path. It is 14 KB, and the
generator already reproduces it byte for byte on any machine, so the source of truth is the
generator and a second copy is not a maintenance burden. What it buys is that a scenario
directory stays self-contained and immutable — the property the whole manifest scheme rests
on — and no scenario needs a path that reaches outside itself. A test asserts the two
network files hash identically.

The demand is deterministic (`sigma="0.0"`, fixed departure periods) and asymmetric on
purpose, so that a movement-mapping error cannot hide behind symmetry:

| approach | vehicles | right | straight | left |
|---|---|---|---|---|
| `top0A0` | 90 | 11.1% | 66.7% | 22.2% |
| `right0A0` | 82 | 36.6% | 48.8% | 14.6% |
| `bottom0A0` | 71 | 21.1% | 45.1% | 33.8% |
| `left0A0` | 72 | 55.6% | 33.3% | 11.1% |

No two approaches share a volume, and no two movements within an approach share a share.
Measured behaviour of the candidate, run before adoption:

```
steps 558, terminal time 558.0 s   drains before the 600 s horizon
departed 315, arrived 315, teleports 0, collisions 0
controlled links carrying traffic  16/16       (s0_single_intersection/v1: 8/16)
peak halting across approach lanes 18, max 6 per lane
```

---

# 11. Testing

## Architecture
- no module outside `simulation/` imports `simulation.ground_truth`
- no module outside `simulation/sumo/` imports `traci`, `libsumo`, or `sumolib`
- no lamp string literal outside `simulation/sumo/`
- `mypy` strictness is not disabled for any package under `src/cadence/`
- the set of modules containing the literal `ground_truth` equals a declared allowlist, so
  extending it is a deliberate edit rather than a side effect

## Property (hypothesis)
- `0.0 <= occupancy_ratio <= 1.0`
- `halting_count_veh <= vehicle_count_veh`
- `0.0 <= mean_speed_mps <= max(lane max speed, fleet vType max speed)`. The second term is
  not slack: a vehicle's speed is bounded by its own vType as well as by the lane, and
  `s0_turning/v1`'s fleet is set to 13.9 m/s against the 13.89 m/s `netgenerate` posts, so
  16.8% of measured rows clear the posted limit by up to 0.01 m/s. The bound has bite —
  one row in six is within a hundredth of it
- `phase_elapsed_s <= phase duration`
- decoding every character of `[ruyYgGoOs]` either yields a `SignalState` or raises; never
  returns a default

## Unit
- `ConnectionId` and `MovementId` construction from a known topology
- `movement_definition_v1` groups the expected connections per movement on both fixtures
- traversal detection on a synthetic lane sequence, including the mid-junction lane change
  that makes via-lane counting wrong
- `_approach_pairs` raises on a zero-length edge, on an alignment below the minimum, and on
  an ambiguous pairing

## Integration, on `s0_turning/v1`
- all 16 controlled links carry traffic
- zero teleports, zero collisions
- the run drains at 558.0 s with 315 departed and 315 arrived
- traversals total 315 — 322 means the via lane is the key, 306 means the lane pair is
  (`ST-D16`)
- **per-movement traversal totals equal the twelve integers the demand was built from**:
  `top0A0` 10 right / 60 straight / 20 left, `right0A0` 30 / 40 / 12, `bottom0A0`
  15 / 32 / 24, `left0A0` 40 / 24 / 8. The total of 315 is invariant under every possible
  movement-mapping error; these twelve are not, and they are the only test that catches a
  swapped `MovementId` derivation. This is why §10.3's demand is asymmetric.
- **the cross-tab attributes every vehicle within its own approach** (`ST-D21`, which
  supersedes `ST-D20`), in three checks, because no one of them is sufficient. A cross-tab that attributed vehicles to the
  wrong edge passes every structural check — non-empty, counts positive, halting within
  count — so this is the group that catches it.

  1. *Every `next_edge_id` is reachable from its lane's **edge*** per
     `topology/connection.parquet`. At the edge and not the lane, because a vehicle can
     legitimately occupy a lane its route cannot use: `departLane="free"` inserts it
     wherever there is room and the lane-changer moves it across afterwards. **On
     `s0_turning/v1` this check alone has no turn resolution at all**: every lane serves two
     of its approach's three movements, so the union over sibling lanes is all three. It
     catches an edge outside the approach entirely, and nothing finer. A wider approach at
     M7 makes it weaker still, not stronger.
  2. *Off-lane presence stays below 5% of attributed vehicle-steps.* Standing on a lane your
     route cannot use is transient — one step. Measured 227 of 10351, 2.2%. A read that
     scattered next edges across an approach's three movements lands near a third off-lane,
     so the bound sits two orders of magnitude from the failure it exists to catch and is
     not fitted to the observation. Verified by mutation: rotating each vehicle's next edge
     among its own approach's movements — the mis-attribution check 1 cannot see — takes
     off-lane presence to 26.4% and fails this.
  3. *The off-lane pairs are exactly the pre-positioning ones*, by identity and volume: each
     of the eight approach lanes against the single movement its sibling serves, at the
     measured count. A pinned count of eight would survive a bug that changed which eight.

  **What the three still miss (`ST-D22`, superseded by `ST-D31`, which splits its
  deadline: the writer change at M1b, the estimator at M8).** A permutation confined to the two movements a
  single lane serves leaves the vehicle on-lane, so check 1 sees a reachable edge, and
  checks 2 and 3 are bit-identical — the off-lane rows are never touched. Per-lane
  conservation sums over next edges and cannot see a permutation either, and the twelve
  per-movement integers come from the traversal detector, a different code path that never
  reads the cross-tab. Measured: permuting within-lane relabels 11080 of 14982 vehicle-steps,
  74% of the table, and changes no assertion in the suite. This is the shared-lane split
  itself — the thing `ST-D01` says the privileged stream exists to record — and M1a does not
  verify it. `LaneTurnCount` carries no vehicle key, so the two independent measurements of
  the same physical quantity, route look-ahead and realised exit, cannot be reconciled. The
  fix is a distinct-vehicle count per `(lane, next_edge)`, which makes
  `distinct_veh >= traversals(lane -> edge)` checkable; it is a schema change to the
  privileged stream and belongs with M1b's first real consumer, not to a fix round at the
  end of M1a.
- **conservation, per lane per step**: `sum(count_veh) + unattributed_count_veh` equals
  `LaneState.vehicle_count_veh`. Not halting: §6.1 argues that halting cannot conserve
  exactly, and the code follows §6.1. The earlier wording here claimed both and contradicted
  its own §6.1. Vehicles whose
  `getLaneID()` returns an internal lane are outside `lanes` and outside the cross-tab
  alike, so they appear in neither side of the identity; the reader iterates the lanes
  `topology` knows, not the vehicles SUMO reports
- unmatched approach transitions total zero, and the counter exists so a future undercount
  is visible rather than silent
- every artifact file is written and non-empty; `topology/`, `state/`, `ground_truth/` and
  `evaluation/` all present

## Reproducibility
- `libsumo` and `traci` produce byte-identical output for every **Parquet** artifact.
  `manifest.json` is excluded: it carries `started_at_utc` and `finished_at_utc`, so
  "every artifact file" was never achievable and the narrowing is a decision, not an
  implementation shortcut
- the two scenarios' network files hash identically
- re-running `tools/build_s0_scenario.py` reproduces both scenario directories byte for byte

## Registry
- every `ST-D*` identifier referenced in code resolves, is `adopted`, and matches its
  recorded content

## 14.3 What the whole-branch review found

The branch was reviewed once more as a whole, on the question a per-task reviewer
structurally cannot answer: what breaks in this code with every test still passing.

| Finding | Resolution |
|---|---|
| **Critical.** The `ST-D21` group misses a permutation confined to one lane's own movements — 74% of the table relabelled, not one assertion moved. | Recorded as `ST-D22`, with the schema change that would fix it, and handed to M1b. Not patched at the end of M1a. |
| `topology/tls_program.parquet` keyed phase rows on `link_index` alone. `link_index` is scoped per traffic light, so on a two-signal network the later signal wins every collision and the earlier one's rows vanish. Invisible on a one-signal fixture. | Keyed on `(intersection_id, link_index)`, with a two-signal unit test the fixture cannot provide. |
| The run directory is a three-way split described as two-way: `state/traversal.parquet` and `evaluation/tripinfo.parquet` together reconstruct 89% of the privileged cross-tab's vehicle-steps. The import ban fences code; nothing fences a file read. | Recorded as `ST-D23`. `ST-D18`'s justification is an online argument and the partition's purpose is an offline loader; reconciling the two is M1b's, with its first real consumer. |
| `evaluation/tripinfo.parquet` was the one table with no declared schema — a nought-column file on a run that loads no vehicle, and an attribute first appearing late in a long run dropped silently. | Schema built from the union of keys across all rows, with a measured floor for the empty case. |
| `unmatched_traversals()` was counted and discarded. Its own comment said *"Counted, never silent"*; nothing in production read it. | A manifest field, which is what §6 says a claim like that has to be. |
| The mypy-strictness guard tested for `key = false` and so could not see `ignore_errors = true`, the one directive that actually switches mypy off. | Widened, with a test that feeds it the directive it used to miss. |
| §11 listed four tests that did not exist: the `mean_speed_mps` bound, all-16-links-carry-traffic, halting conservation, and the generator's byte-reproducibility. | Three written. The fourth was a contradiction with §6.1 rather than a missing test, and §11 was wrong; it now says so. |

The pattern across all three rounds is worth stating once. The specification reviews found
twenty-one defects in a document. Execution found one the document could not have found.
This round found what neither could: defects that need two tasks in view at once, or a
fixture the project does not have. Three different reviews, three disjoint failure classes,
and the branch would have shipped with all of the third class intact.

---

# 12. What M1a Hands to M1b

M1b is gated on reading real Parquet output from a completed M1a run, not on this document.
The questions it inherits, unanswered on purpose:

1. **The queue attribution rule.** `movement_queue_proportional_split_v1` — how a shared
   lane's queue divides between the movements it serves.
2. **`turn_ratio_sliding_window_v1`.** Its window length and prior weight are configuration
   recorded in the manifest, not part of the semantic version, which only holds if something
   refuses to aggregate runs whose relevant configuration differs. That implies a
   `config_dependencies` field on each registry entry, which `ARCH §18` does not list, and
   `cadence verify-run` as its enforcement.
3. **The starvation guard.** A movement that is never served produces no traversals, and a
   naive estimator reads that as no demand and starves it further. A pseudo-count prior does
   not fix it: with `n_m` fixed at zero while other movements accumulate, the posterior share
   still converges to zero. Evidence must accumulate only over intervals in which the
   movement was served, with unserved movements holding their prior rather than being
   diluted. This requires an explicit starvation test.
4. **The residual bias, which is not fixable.** A movement that *is* served but oversaturated
   discharges at capacity rather than at demand, so observed discharge cannot identify latent
   arrival demand. This is a limitation to state, not a defect to remove.
5. **The derived lane quantities** deferred from `ST-D03`: `queue_length_m`,
   `storage_capacity_veh`, `available_storage_ratio`.
6. **Verifying the per-lane turn split** (`ST-D22`). It is unverified at M1a and M1b's turn
   ratio estimator is its first consumer, so this is a precondition of item 2, not an
   improvement to schedule after it. A distinct-vehicle count per `(lane, next_edge)` makes
   the cross-tab reconcilable against `state/traversal.parquet`; a per-lane split validated
   against an unverified cross-tab measures agreement, not correctness.
7. **Whether the privilege split is real** (`ST-D23`). `state/` and `evaluation/` together
   reconstruct most of `ground_truth/`, so the directory boundary bounds nothing today. The
   decision belongs with the first code that loads a run directory rather than being taken
   in the abstract here — but it has to be taken before that code exists, not after.

---

# 13. Out of Scope

- `PD-D06` layer 2, section content hashing. Documentation tooling, not on the traffic-state
  critical path, and deferred indefinitely rather than to M1b.
- Computational metrics — controller latency, solver timeout. No controller exists before M2.
- Any observation adapter, any controller, any reward. M2 and later.
- `SensorRealisticAdapter` and any realism modelling. Unscheduled.
- An oracle controller. If one is ever built it gets an explicit privileged adapter and its
  experiments are labelled as using privileged information.

---

# 14. What the Reviews Changed

Two independent reviews read this document before any code was written: one Codex agent with
no conversational context, checking every `ST-D` identifier against the ninety-eight adopted
decisions in `research/decisions.yaml`; one reading it adversarially as a design. They found
thirteen defects. Four were structural.

| Finding | Where | Resolution |
|---|---|---|
| No path from a traversal or a movement to a controller. `ARCH §7`'s Max-Pressure adapter reads movement queues and turn ratios *from canonical state*; canonical state had neither, and `Traversal` sat on `StepResult`, which controllers never receive. At M8 the only exits were reopening this interface or letting Max-Pressure read privileged data. | §5.2, §7 | `ST-D15`. Canonical state gains a movement layer and the step's traversals. |
| `(incoming lane, outgoing lane)` as the traversal key **loses nine of 315 vehicles**, measured. A vehicle that changes lane inside the junction exits on a lane that pair does not name. | §7.1 | `ST-D16` supersedes `ST-D07`. Key on the outgoing *edge*; record the connection when it resolves. |
| `tripinfo` was filed as privileged, and dropped: `--tripinfo-output` appears in no SUMO command and no writer emits it. M1b's trip metrics had no source and would have required re-running every experiment. | §8 | `ST-D18`. `evaluation/tripinfo.parquet`, and the flag is enabled at M1a. |
| No signal program table, so `phase_index` had no recorded meaning, `phase_elapsed_s <= phase duration` had no source, and a phase that is never served — the starvation case §12 flags — left no trace at all. | §8 | `ST-D19`. `topology/tls_program.parquet`. |
| `ST-D03`'s "every derived quantity belongs to M1b" contradicted this document twice: `movement_definition_v1` and traversal detection are derivations M1a performs. | §5.1 | `ST-D17` supersedes it. The line is interpretation, not derivation. |
| Two definitions of "halting" that can disagree four ways, one of which no threshold choice fixes. M1b would have read the residual as an attribution error. | §6.1 | `ST-D19`. Record the unattributed residual and assert conservation. |
| Teleports lost their location, so M9 could not ask whether an advantage came from service or from gridlock removal. | §8 | `ST-D19`. `state/teleport.parquet`. |
| The twelve exact per-movement counts this document supplies in §10.3 were never checked against anything. A cross-tab attributing every vehicle to the wrong edge passed every structural test. | §11 | Two integration assertions, per-movement totals and successor legality. |
| §4's "the only module importing both" is false by construction: anything writing the run directory holds both. | §4 | The allowlist is stated exactly, and it is the guard. |
| §3.1's heading said subscriptions are for TraCI only; its conclusion used them unconditionally. | §3.1 | The real reason — one extraction path, for byte-identical artifacts — is now stated. |
| 3.4 bytes/row was measured on a sparse fixture and cited as an M8 estimate. | §3.2 | The conclusion stands; the number is corrected to 15-30 B/row for regimes C and D. |
| `termination_reason` admitted no aborted run, and the derived plan raised rather than writing a manifest. | §9.1 | A third value. |
| "Byte-identical output for every artifact file" is unachievable — `manifest.json` carries timestamps. | §11 | Narrowed to Parquet, deliberately. |
| Two mechanisms for refusing to compare dirty runs; the digest in `reproducible_fields()` already does it in M1a. | §9.2 | M1b's `verify-run` adds the refusal and the explanation, not the detection. |
| No rerouting policy, so the cached intent would go silently stale. | §6 | Out of scope for M1a, stated, with the invalidation any later milestone must add. |

Every one of these was in work its own author had already reviewed. Two — the traversal key
and the missing `tripinfo` — were invisible to reasoning and surfaced only by running
something: the first by executing the detection rule against the fixture and counting, the
second by grepping the SUMO command for a flag the document assumed was there.

## 14.1 What the second review found in the first revision

The revision was reviewed again, on the explicit question of whether the fixes had opened
new holes. Three of the four had.

| Finding | Resolution |
|---|---|
| **Critical.** `ST-D15`'s movement layer was decorative. `MovementState` named a movement, `LaneState` named a lane, and nothing in canonical state connected them, so an M8 adapter still could not find the lanes incident to a movement — the exact outcome §5.2.1 claims to prevent. | `CanonicalTrafficState` carries `topology` by reference. |
| §7.1's `Traversal` still had the old shape while §8's schema had the new one, so the type could not express the nullable connection the fix exists for. | Both now read `movement_id` plus `connection_id \| None`. |
| A teleport left the detector holding an approach lane while the vehicle reappeared downstream, so it fabricated a traversal or tripped the unmatched counter. Zero teleports on the fixture meant M1a would have passed; regimes C and D are where it bites. | A teleport clears the held lane. |
| SUMO writes no `tripinfo` row for a vehicle still in the network, and under C and D the run ends with the most delayed trips unfinished — removing exactly the tail the research question is about. | `--tripinfo-output.write-unfinished`. |
| "A lane serves at most one connection to any given edge" is false in SUMO. The movement conclusion survives; the stated reason did not. | Corrected, and it is a second reason the connection is nullable. |
| `traversals` appeared on both `CanonicalTrafficState` and `StepResult`. | One source. |
| `movement_definition_v1` carries a version while `ST-D17` calls it structure. | Reconciled explicitly in §5.4: structure that could have been drawn differently still earns a version. |
| Per-lane conservation had no defined behaviour for a vehicle on an internal lane. | The identity iterates the lanes `topology` knows. |

## 14.2 What execution found

`ST-D20`. §11 required every `next_edge_id` in the cross-tab to be a legal successor of
**its lane**. Run against the fixture, that is false, and the run is the first time anyone
tried it: 227 vehicle-steps of 10351 sit on a lane their route cannot use, in eight pairs,
one per approach lane. The cause is `departLane="free"` — SUMO inserts a vehicle on
whichever lane has room, not on one that serves its route, and the lane-changer moves it on
the following step. Switching the fixture to `departLane="best"` removes all 227, which is
how the cause was confirmed.

The fixture was not switched. A vehicle queued on a lane it must change out of is normal
traffic, and a real multi-lane approach at M7 produces it without any help from
`departLane` — the phenomenon is representative whatever the fixture's reason for producing
it, and `departLane="free"` was chosen in §10.3 to hit target volumes rather than for this.
Removing it would have been fitting the world to the assertion, and would have bought a
claim true only on a toy network.

The assertion moved to the edge — and the review of that move found the move insufficient.
At the edge the check has no turn resolution on this network at all, because every lane
serves two of its approach's three movements and the union over siblings is all three. A
mis-attribution *within* an approach passed it, passed per-lane conservation (which sums
over next edges and so cannot see them permuted), and never touches the twelve per-movement
integers, which come from the traversal detector on a different code path. §11's second and
third checks close that: a bound on off-lane presence, verified by mutation to fail at 26.4%
against a 5% threshold, and the off-lane pairs pinned by identity and volume rather than by
count.

This is the twenty-second finding, and the twenty-third is the review of its fix. Both could
only be found by running the code — the first by executing the fixture, the second by
mutating the extractor and watching the new assertion fail to notice. The three sections
above argue that reviewing a specification before implementing it is worth it; this one is
the other half of that argument, and the part of it that says a correction is not finished
until it has been attacked as hard as the thing it corrects.

Two rounds, twenty-one findings, none of them in code — because there is no code yet. That
is the whole argument for reviewing a specification before implementing it: the traversal
key alone would have been found at M1b, after the extractor, the artifacts, the CLI and
every integration test had been built on top of a key that loses nine vehicles in 315.
