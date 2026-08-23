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

That line is not a realism claim. It is a **parity** claim. `CanonicalTrafficState` still
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
| `ST-D03` | Canonical state carries only quantities the simulator reports directly. Every derived quantity belongs to M1b. |
| `ST-D04` | Signal state is a typed enum decoded inside `simulation/sumo/`. No lamp string leaves that package, including into an artifact. |
| `ST-D05` | `ConnectionId`, keyed on the ordered lane pair, is the lowest stable control grain. The TLS link index is recorded but is not an identity. |
| `ST-D06` | `movement_definition_v1`: a `MovementId` is the ordered edge pair; a movement groups one or more connections. |
| `ST-D07` | Traversal identity is the `(incoming lane, outgoing lane)` transition, not presence on a via lane. |
| `ST-D08` | Run artifacts are partitioned into `topology/`, `state/`, and `ground_truth/`. `events.parquet` keeps its M0 schema; traversals get a sibling table. |
| `ST-D09` | Ground truth is read through an explicitly named method. `step()` never returns it. |
| `ST-D10` | The manifest records the run outcome: terminal time, step count, and termination reason. |
| `ST-D11` | A dirty working tree is hashed, not rejected. |
| `ST-D12` | All three SUMO surfaces — `traci`, `libsumo`, `sumolib` — live under `simulation/sumo/`. |
| `ST-D13` | `s0_turning/v1` is a separate immutable scenario whose network file is byte-identical to `s0_single_intersection/v1`'s by construction. |

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
extractor uses subscriptions unconditionally. `libsumo` has no socket, so the round-trip
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
    sumo/extract.py    the only module importing both
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

## 5.1 The M1a / M1b line (`ST-D03`)

**M1a records what the simulator reports. M1b computes what we interpret.**

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
class CanonicalTrafficState:
    time_s: float
    lanes: Mapping[LaneId, LaneState]
    intersections: Mapping[IntersectionId, IntersectionState]
    network: NetworkState
```

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
opens:

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

PROVENANCE for `TurnDirection`: the `LINKDIR_*` constants in `sumolib.net.connection`,
which that module states are taken from `sumo/src/utils/xml/SUMOXMLDefinitions.cpp`. The
direction is read from SUMO rather than recomputed from geometry, so the project owns no
second opinion about what counts as a left turn.

There is no `MovementState` in M1a. A movement's state is its queue, and a movement queue
requires a versioned attribution rule for shared lanes. That is M1b.

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
    traversals: tuple[Traversal, ...]
    expected_remaining_veh: int
```

## 7.1 Traversal detection (`ST-D07`)

```python
@dataclass(frozen=True, slots=True)
class Traversal:
    time_s: float
    vehicle_id: VehicleId
    connection_id: ConnectionId
```

The extractor holds each active vehicle's last observed lane. A traversal is recorded when
that lane is an incoming lane of a controlled connection and the new lane is that
connection's outgoing lane; observation on the connection's via lane confirms the same
event but never generates one on its own.

Keying on the lane pair rather than the via lane is what makes the count exact (§3.5), and
it is also what makes detection independent of step length: a network whose internal links
are short enough to be skipped at a 1 s step still produces the transition.

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
    connection.parquet      connection_id, tls_id, link_index, from_lane_id, to_lane_id,
                            via_lane_id, from_edge_id, to_edge_id, turn_direction,
                            movement_id
  state/
    lane.parquet            time_s, lane_id, vehicle_count_veh, halting_count_veh,
                            mean_speed_mps, occupancy_ratio, waiting_total_now_s
    intersection.parquet    time_s, intersection_id, program_id, phase_index,
                            phase_elapsed_s
    signal.parquet          time_s, connection_id, signal
    network.parquet         time_s, active_veh, pending_insertion_veh, departed_total_veh,
                            arrived_total_veh, teleport_total_veh
    traversal.parquet       time_s, vehicle_id, connection_id
  ground_truth/
    lane_turn.parquet       time_s, lane_id, next_edge_id, count_veh, halting_count_veh,
                            waiting_total_now_s
    tripinfo.parquet        converted from SUMO's --tripinfo-output
```

`topology/` is written once per run rather than referenced from the scenario, so a run
directory is self-describing: reading it requires no access to the network file that
produced it.

Two tables at the two static grains rather than one, because a lane and a connection are
different things and a single table would leave outgoing lanes unrepresented.

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

---

# 9. Manifest

## 9.1 Run outcome (`ST-D10`)

`docs/DIRECTION.md` §7 item 2: the M0 manifest records nothing about how the run ended. S0
drains at 520 s of a 600 s horizon, and two runs differing in termination reason are
indistinguishable from their manifests. New fields:

```
terminal_time_s      float
step_count           int
termination_reason   "drained" | "horizon"
```

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
- `0.0 <= mean_speed_mps <= lane max speed`
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
- traversals total 315, not 322 — the direct regression test for `ST-D07`
- every artifact file is written and non-empty; `ground_truth/` and `state/` both present

## Reproducibility
- `libsumo` and `traci` produce byte-identical output for every artifact file
- the two scenarios' network files hash identically
- re-running `tools/build_s0_scenario.py` reproduces both scenario directories byte for byte

## Registry
- every `ST-D*` identifier referenced in code resolves, is `adopted`, and matches its
  recorded content

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

---

# 13. Out of Scope

- `PD-D06` layer 2, section content hashing. Documentation tooling, not on the traffic-state
  critical path, and deferred indefinitely rather than to M1b.
- Computational metrics — controller latency, solver timeout. No controller exists before M2.
- Any observation adapter, any controller, any reward. M2 and later.
- `SensorRealisticAdapter` and any realism modelling. Unscheduled.
- An oracle controller. If one is ever built it gets an explicit privileged adapter and its
  experiments are labelled as using privileged information.
