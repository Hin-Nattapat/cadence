# M2 — Signal Safety + Controller Contract

**Status:** proposed
**Registers `SIM-D01` .. `SIM-D03` (measured SUMO behaviour) and `SIG-D01` .. `SIG-D11`.**
**Program map:** `docs/programs/2026-09-06-m2-signal-contract.md` — two phases, eight
contracts, the premises this document rests on.
**Prior art:** `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §9–§16, §25–§29;
`research/CADENCE_RL_TSC_RESEARCH.md` §6–§8; `research/CADENCE_MAX_PRESSURE_RESEARCH.md`
Part IX–X; `docs/specs/2026-08-27-m1b-metrics.md` §9.2 (what M1b hands here).

---

# 1. What M2 is for

Every milestone from M3 onward puts a controller in front of a signal. M3 compares two
classical ones; M4 wraps one in Gymnasium; M8 puts Max-Pressure on a corridor. None of them
can exist until something answers two questions that no controller should answer for itself:
*which signal states are legal right now*, and *how a legal change is carried out*.

> **M2 puts one safety layer between every controller and the simulator, and one contract in
> front of every controller, so that from M3 on the only thing that differs between two runs
> in a table is the controller.**

That sentence is `AP-04` and `ARCH-D04` made operational. `DIRECTION` §2's M2 row names the
parts — controller interface, action types, safety and transition executor, action masks,
timeout and fallback — and §8 below derives the scope from this purpose.

## 1.1 The two failures this milestone must be immune to

**An unsafe transition is silent.** SUMO does not refuse a green-to-red jump. §3 measured
one: `setPhase(2)` from a running green produced two emergency stops in the same second and
a warning on stderr that no artifact records. A controller allowed to issue it would be
scored on the queues it cleared, and the collision it nearly caused would be invisible to
every metric M1b defined. The safety layer exists so that this transition **cannot be
requested**, not so that it is discouraged.

**Raw signal state couples every controller to one network file.** A lamp string
(`"GGGgrrrrGGGgrrrr"`) is a position-indexed encoding of one `netconvert` run (`ARCH §13`).
A controller that reads or writes it learns a network, not traffic control, and two
controllers compared on it are compared on their string handling. `ST-D04` already keeps
lamp strings inside `simulation/sumo/`; M2's decision `SIG-D01` goes further — CADENCE never
composes one at all.

---

# 2. Principles

Each is a decision; the section that grounds it is named.

**`SIG-D01` — Transitions are the program's own phases.** The executor changes a signal only
by selecting a phase index of the network's traffic-light program (`setPhase`). It never
writes a lamp state, so SUMO's `online` program never occurs and the canonical state's
`phase_index` and `phase_elapsed_s` stay truthful (§3, `SIM-D01`). Every transition phase a
plan needs — yellow, all-red — must exist in the program; `netconvert` generates them and
`cadence validate-scenario` refuses a program whose stage lacks one (§5.2).

**`SIG-D02` — The safety envelope is scenario data.** Per-stage minimum and maximum green
live in `signal_plan.yaml` beside `scenario.yaml`, hashed into the manifest as a
comparability field. They are not controller configuration: `AP-04` says every controller
shares the same envelope, and `ST-D33` says two runs that differ in it may not share a table
(§4).

**`SIG-D03` — A stage is a program phase that lets something move.** A phase with at least
one permissive signal and no yellow is a stage; its `PhaseId` is its program index; its
permitted movements derive from its connections. Transition phases are never stages and can
never be requested (§4).

**`SIG-D04` — The executor is a pure state machine that emits commands.** It lives in
`control/`, imports nothing from `simulation/sumo/`, and returns `SignalCommand`s as data.
Exactly one module under `simulation/sumo/` applies them (§5, the R4 fence). A controller
never sees a command.

**`SIG-D05` — A request is deferred, never dropped.** A stage requested during minimum green
or during a transition is held and served the first step it is legal; a newer request
replaces an older pending one, and the replacement is logged. Every request, deferral,
replacement, transition and forced switch is a row in `state/signal_event.parquet`;
`events.parquet` keeps its M0 schema (`ST-D08`) (§5.4).

**`SIG-D06` — Maximum green is enforced by the executor, in program order.** When a stage
reaches its maximum with no legal request pending, the executor transitions to the next
stage in program order and records `max_green_forced`. `KeepPhase` stays legal — it is the
contract's no-op — and the mask exposes `max_green_reached` so a controller sees the force
coming (§5.3, §6.4).

**`SIG-D07` — Lateness marks the run; illegality triggers the fallback.** (Program map P9,
answered 2026-09-06.) A controller's decision budget is the decision interval by
construction. The experiment runner measures wall-clock per `decide` outside Zone A and
records it — per call in `controller.json`, as a count in the manifest's non-reproducible set
that `verify-run` refuses to compare across — and never alters the run because of it. The
only fallback is for an action outside the mask, a request for a phase that is not a stage of
the plan or for the stage already current: it becomes `KeepPhase`, logged as
`action_rejected` (§6.5).

**`SIG-D08` — `controller_id = "none"` bypasses the layer, and the layer must be able to
disappear.** A run with no controller is byte-identical to pre-M2 output over the M1 artifact
set. The fixed-time test controller that replays the static program through the executor must
match it byte for byte over that set, under the two preconditions §7.3 states — that equality
is the acceptance test of the whole milestone.

**`SIG-D09` — `ControllerAction` v1 is `KeepPhase | RequestPhase(PhaseId)`.** `ARCH §12`'s
other four are not v1: `NoOp` *is* `KeepPhase`; `RequestNextPhase` is
`RequestPhase(plan.next_stage_in_program_order(current))` at the call site; `ExtendPhase` and
`SetGreenSplit` are M4's and M3's questions. The version string is `controller_action:v1` (§6.3).

**`SIG-D10` — The decision interval is run metadata.** `decision_interval_s`, a multiple of
`step_length_s`, recorded in the manifest as a comparability field. Controllers are called
only at interval boundaries; the executor runs every step (§6.1).

**`SIG-D11` — Controller configuration is hashed and stored.** `controller_config_sha256`
joins the manifest's controller-identity fields, so two runs of one controller under two
configurations are a controller comparison, not a reproducibility check; the configuration
itself is written to `controller.json` in the run directory, so a run names the controller
that produced it the way it names the scenario (§7.4).

---

# 3. What measurement decided

Measured on 2026-09-06, SUMO 1.27.1, `s0_turning/v1`, seed 1, one write sequence replayed
under both bindings. Program `0` is four phases: stage `0` (42 s), yellow `1` (3 s), stage
`2` (42 s), yellow `3` (3 s); no all-red (`network.net.xml:123-128`).

| t (s) | call | `getProgram` | `getPhase` | `getSpentDuration` | `getPhaseDuration` | `getNextSwitch` |
|---|---|---|---|---|---|---|
| 10 | before | `0` | 0 | 10.0 | 42 | 42 |
| 10 | `setRedYellowGreenState(all red)` | `online` | 0 | **0.0** | **86400** | 86410 |
| 15 | `setRedYellowGreenState(stage 0)` | `online` | 0 | **15.0** | 86400 | 86410 |
| 20 | `setProgram("0")` | `0` | 0 | **20.0** | 42 | **42** |
| 30 | `setPhase(2)` | `0` | 2 | 0.0 | 42 | 72 |
| 36 | `setPhaseDuration(4)` | `0` | 2 | 6.0 | 42 | **40** |
| 50 | `setPhase(1)` (the yellow) | `0` | 1 | 0.0 | 3 | 53 |
| 54 | — | `0` | 2 | 1.0 | 42 | 95 |

**`SIM-D01` — Under `setRedYellowGreenState`, SUMO switches to a one-phase program named
`online` whose phase lasts a day, and `getPhase` / `getSpentDuration` stop describing the
signal.** `getPhase` froze at the last program index; `getSpentDuration` reset to 0 on the
first override and to a *different origin* on the second — 5.0 before the call, 15.0 after it,
the whole elapsed simulation time, while `getNextSwitch` still said the phase began at t = 10.
`setProgram("0")` returned to the
program with its clock intact — phase 0, 20 s spent, next switch still at 42 — as if the
override had never happened. A design that composed lamp states would therefore have to keep
its own phase clock and would leave the canonical state's `phase_index` and
`phase_elapsed_s` (`extract.py:88-89`) describing a program that was not running.

**`SIM-D02` — `setPhase(i)` applies within the same step, restarts the phase clock, and the
program continues from `i` by its own sequencing; `setPhaseDuration(d)` sets the remaining
time once.** Selecting the yellow phase ran it for its 3 s and advanced to the next stage
unaided (t = 50 → 53 → 54). This is the mechanism `SIG-D01` builds on.

**`SIM-D03` — libsumo and traci produce identical state under the same write sequence.**
A digest over (time, program, phase, spent, next switch, lamp state) at every probed step plus
every lane's halting count at t = 60 was identical under both bindings. That is one write
sequence, one intersection, sixty seconds: `SIM-D03` is registered as a **hypothesis** until
phase 2's whole-run artifact comparison under both bindings promotes it.

**The emergency stops.** `setPhase(2)` at t = 30 jumped stage 0's greens straight to red.
SUMO logged, for two vehicles, "performs emergency braking … decel=9.00, wished=4.50" and
"emergency stop at the end of lane … because of a red traffic light". Nothing in the run
directory records this. `simulation.getEmergencyStoppingVehiclesIDList()` exposes it per
step; §10 makes "zero emergency stops caused by a transition" a test, not a hope.

---

# 4. The signal plan (`SIG-D02`, `SIG-D03`)

## 4.1 Stages, from the program

The plan is built from `NetworkTopology.phases` (`PhaseInfo`: program index, durations,
decoded signals) and `NetworkTopology.connections`. For one intersection and its active
program:

```
stage            a program phase with ≥ 1 permissive signal (SignalState.permits_movement)
                 and no YELLOW / RED_YELLOW anywhere in it
transition phase every other phase
PhaseId          the stage's program index (types.py already declares PhaseId = NewType(int))
permitted        connections whose signal in the stage permits movement; movements derived
                 through ConnectionInfo → MovementDefinition
successor        the transition phases that follow the stage in program order up to the
                 next stage — on s0: stage 0 → [1] → stage 2 → [3] → stage 0
```

The plan refuses to build — loudly, at connection time — when a stage's successor chain
contains another stage before any transition phase (a program with no yellow), or when a
transition phase turns a signal *on* that the preceding stage did not have (a program whose
"yellow" is a different stage in disguise). Both are `cadence validate-scenario` checks as
well (§5.2), because a scenario that fails them is not controllable and should say so before
a run starts.

On `s0_turning/v1`: 2 stages, 2 transition phases, 8 permitted connections per stage, 6
movements per stage (the third movement on each approach is the permissive `g`).

## 4.2 The envelope, from `signal_plan.yaml`

```yaml
# scenarios/<id>/v<N>/signal_plan.yaml — optional; absent means "not controllable"
signal_plan_version: 1
intersections:
  A0:
    stages:
      # placeholders for M2 (M3 tunes and freezes them, TC-D11); they bracket the static
      # program's 42 s so the acceptance test of §7.3 can hold
      0: {min_green_s: 10.0, max_green_s: 60.0}
      2: {min_green_s: 10.0, max_green_s: 60.0}
```

Rules: every stage the program has must appear, and no other index may (`extra="forbid"` on
the model, a stage-set equality check against the built plan); `min_green_s ≥ step_length_s`;
`max_green_s ≥ min_green_s`. For a scenario whose static program must be reproducible under a
controller, each stage's `[min_green_s, max_green_s]` brackets its program duration (§7.3).
The file's SHA-256 becomes `signal_plan_sha256` in the manifest,
`None` when the file is absent, and joins `COMPARABILITY_FIELDS`: two runs under different
envelopes are two experiments (`ST-D33`).

`min`/`max` do **not** come from `tls_program.parquet`'s `min_duration_s` / `max_duration_s`.
Those are SUMO's actuated-only attributes and on a static program equal `duration`
(program-map P3); on s0 they say 42 / 42, which is a cycle plan, not an envelope.

Under a controller, `tls_program.parquet`'s `duration_s` is the program's static timing, not
what ran: the executor holds a stage anywhere between `min_green_s` and `max_green_s`, so
M1a's invariant `phase_elapsed_s <= phase duration` (`tests/simulation/sumo/test_extract.py:54`)
holds only for `controller_id = "none"`. M2 restates it: under a controller,
`phase_elapsed_s <= max_green_s + step_length_s` for a stage and `<= duration_s` for a
transition phase (§10). What ran is in `state/intersection.parquet` and
`state/signal_event.parquet`.

Yellow and all-red durations are *not* in this file: they are the program's own transition
phases, and the program is the network file. A scenario that wants all-red regenerates its
network with `--tls.allred.time` (program-map P4). s0 keeps its 3 s yellow and no all-red.

## 4.3 What the plan exposes

```python
@dataclass(frozen=True)
class Stage:
    phase_id: PhaseId
    permitted_connections: frozenset[ConnectionId]
    permitted_movements: frozenset[MovementId]
    min_green_s: float
    max_green_s: float
    program_duration_s: float                     # what the static program would run
    transition_phase_indices: tuple[int, ...]     # the successor chain, program order
    movement_signature: frozenset[MovementId]     # the network-independent identity, see below

@dataclass(frozen=True)
class SignalPlan:
    intersection_id: IntersectionId
    program_id: str
    stages: Mapping[PhaseId, Stage]               # program order
    transition_phase_duration_s: Mapping[int, float]
    def next_stage_in_program_order(self, phase_id: PhaseId) -> PhaseId: ...
```

`PhaseId` is a program index, and a program index is network-file-specific in exactly the way
`ST-D05` records for a link index: regenerate the network and it may change. The stage's
identity across networks is its permitted movement set, `movement_signature`, and anything
that must survive a regeneration — a tuned plan in M3, a learned policy in M4 — keys on that,
not on the index.

This is what M8's Max-Pressure reads as its legal stage set (`MP-D04`): a stage is a set of
movements, which is exactly the `S(l,m)` indicator the original formulation needs, and it
comes from the program rather than from a controller's own idea of compatibility.

---

# 5. The executor (`SIG-D01`, `SIG-D04`, `SIG-D05`, `SIG-D06`)

## 5.1 State machine

One executor per controlled intersection, one `tick` per simulation step — after
`connection.step()` has returned the state for time t and before the next step, which is where
`SIM-D02` measured a command taking effect. Its whole state:

```
mode          IN_STAGE(phase_id) | IN_TRANSITION(target phase_id, remaining chain)
entered_at_s  simulated time the current stage or transition phase began
pending       PhaseId | None      the deferred request (SIG-D05)
```

It is seeded from the first extracted `IntersectionState`, not assumed: `mode` from
`phase_index` (a stage → `IN_STAGE`, a transition phase → `IN_TRANSITION` with the remainder
of the chain and the next stage in program order as target), `entered_at_s = now_s -
phase_elapsed_s`. A program with a non-zero `offset`, or a scenario with `begin_s > 0`,
starts mid-cycle; s0 starting in stage 0 at t = 0 is a coincidence of `offset="0"`. During a
transition, "the current stage" means the transition's target.

`elapsed_s = now_s - entered_at_s` is the executor's own clock. It is cross-checked, not
replaced, by `phase_elapsed_s` from canonical state: the two must agree to within one step
while `SIG-D01` holds, and a disagreement is a loud failure — it would mean SUMO changed
phase without being asked (a program with `type="actuated"`, or an `online` override from
somewhere else).

Per tick, given the current canonical `IntersectionState` and, on a decision boundary, the
controller's action:

```
1. reconcile   SUMO's phase_index must equal what mode says; else raise.
2. absorb      action == RequestPhase(p): p must be a stage of this plan and ≠ the current
               stage (the target, during a transition), else it is illegal (→ §6.5). Legal:
               if pending is set and ≠ p, record request_superseded; pending = p;
               record stage_requested (or request_deferred with its reason when it cannot
               be served this tick).
               action == KeepPhase: nothing.
3. transition  IN_TRANSITION and the current transition phase has run
               plan.transition_phase_duration_s[index]:
                 more chain → SetPhase(next in chain)
                 chain done → SetPhase(target); mode = IN_STAGE(target); entered_at_s = now;
                              pending = None if pending == target; record stage_entered
4. serve       IN_STAGE and pending is not None and pending ≠ current and
               elapsed_s >= min_green_s:
                 mode = IN_TRANSITION(pending, stage.transition_phase_indices)
                 SetPhase(first in chain); pending = None; record transition_started
5. force       IN_STAGE and pending is None and elapsed_s >= max_green_s:
                 same as 4 with target = plan.next_stage_in_program_order(current);
                 record max_green_forced
6. hold        on entering a stage: SetRemainingDuration_s(max_green_s + step_length_s), so
               SUMO's own switch — which would fire at stage.program_duration_s — never
               pre-empts the executor. Transition phases keep the program's own timing.
```

Every command is data: `SetPhase(intersection_id, phase_index)` and
`SetRemainingDuration_s(intersection_id, remaining_s)`. `simulation/sumo/signal_writer.py` applies
them with `trafficlight.setPhase` / `setPhaseDuration` and is the one module allowed to
(R4). The executor never imports it, never sees a binding, and is tested without SUMO.

Determinism (`AP-06`, R7): `tick` is a function of (plan, mode, pending, `now_s`,
`IntersectionState`, action). No clock, no randomness, no dict iteration whose order matters
— the chain is a tuple, the stages a mapping in program order.

## 5.2 What the plan and `validate-scenario` refuse

| refused when | where |
|---|---|
| a stage is followed by another stage with no transition phase between | plan build; `validate-scenario` |
| a transition phase turns on a signal its preceding stage had off | plan build; `validate-scenario` |
| `signal_plan.yaml` names a stage the program lacks, or omits one it has | plan build; `validate-scenario` |
| `min_green_s < step_length_s` or `max_green_s < min_green_s` | model validation |
| a scenario has no `signal_plan.yaml` and a controller other than `none` is requested | `cadence run` |
| the program's `type` is not `static` | plan build, from the program logic's `type` read at connection time (kept on the in-memory topology; `tls_program.parquet`'s schema is unchanged) — an actuated program switches by itself and `SIG-D01`'s reconciliation would fire on the first cycle; M3's SUMO-native actuated runs as `controller_id = "sumo_actuated:v1"` without an executor (program-map "ยังไม่ชัด" 2) |

## 5.3 Minimum and maximum green

Minimum green protects the stage that just started: a request arriving before `min_green_s`
is held (`SIG-D05`), and the mask says so (§6.4). Maximum green protects everyone else: at
`max_green_s` with nothing pending the executor forces program order (`SIG-D06`) whatever the
controller said, including `KeepPhase` — which stays legal, because a contract with no legal
no-op would log every indifferent controller as a violator. There is no third case: a pending
request at maximum green is simply served, since it was legal already.

Program order as the forced target is a choice, and a conservative one: it is what the
static program would have done, so a controller that never speaks reproduces the network's
own plan (this is also why §7.3's fixed-time controller can match `none` byte for byte).

## 5.4 `state/signal_event.parquet`

A sibling of `events.parquet` (`ST-D08`), one row per executor decision:

| column | type | meaning |
|---|---|---|
| `time_s` | Float64 | step at which the executor acted |
| `intersection_id` | String | |
| `kind` | String | `stage_requested` · `request_deferred` · `request_superseded` · `transition_started` · `stage_entered` · `max_green_forced` · `action_rejected` |
| `from_phase_id` | Int64 (nullable) | stage or transition phase being left |
| `to_phase_id` | Int64 (nullable) | stage requested / entered |
| `reason` | String (nullable) | for `request_deferred`: `min_green` or `in_transition`; for `action_rejected`: `not_a_stage` or `already_current` |

Nothing wall-clock is ever written here (§6.5): every row is a function of simulated time.

Written by `RunRecorder` like every other state table, with a declared schema so a run with
no controller still has a readable, empty table.

---

# 6. The controller contract (`SIG-D07`, `SIG-D09`, `SIG-D10`, `SIG-D11`)

## 6.1 Lifecycle and cadence

```python
class TrafficController(Protocol):
    controller_id: ControllerId          # "fixed_time_program", "max_pressure_original", …
    controller_version: str              # "v1"
    def initialize(self, context: ControllerContext) -> None: ...
    def reset(self, episode: EpisodeContext) -> None: ...
    def decide(self, observation: ControllerObservation) -> Mapping[IntersectionId, ControllerAction]: ...
    def on_transition(self, transition: SignalTransition) -> None: ...
    def diagnostics(self) -> ControllerDiagnostics: ...
    def close(self) -> None: ...
```

`ARCH §9`'s six methods, as a `typing.Protocol` so an external controller need not inherit
anything. `decide` is called at every decision boundary — every `decision_interval_s` of
simulated time, a multiple of `step_length_s` (`SIG-D10`) — with one observation covering
every controlled intersection, and returns one action per intersection; an intersection the
mapping omits gets `KeepPhase`. One controller instance therefore sees a whole corridor in
M8, which is what coordination will need; the executor ticks every step in between, one per
intersection. `on_transition` is called
when a stage is entered, whether by request or by force, so a controller can track what the
layer actually did with its request. `reset` exists for M4's episodes and is called once
before the first `decide` in M2.

## 6.2 Context and observation

`ControllerContext` (`ARCH §10`): the `SignalPlan`s of the controlled intersections, the
topology view (`NetworkTopology`), `decision_interval_s`, `step_length_s`, the controller's
own configuration mapping, and the seed. Nothing else — no binding, no run directory.

`ControllerObservation` v1 (`controller_observation:v1`) is a view over canonical state
(`ARCH-D03`): the intersection's `IntersectionState`, its approach `LaneState`s and
`MovementState`s, the executor's `SignalPhaseState` (current stage, `elapsed_s`, pending
request, in-transition flag, `max_green_reached`), the legal action mask (§6.4), and `now_s`,
for every controlled intersection. It is **O1** in `RL §4`'s fidelity ladder — lane-level
virtual detection: counts, halting, occupancy, waiting; no vehicle positions, routes or
turning intentions, which are privileged (`ST-D01`, `ST-D09`) — and every M2 run records that
as `observation_version` (`ARCH-D08`, `ST-D14`). Adapters that degrade it further are M4's.

## 6.3 Action

```python
@dataclass(frozen=True)
class KeepPhase: ...
@dataclass(frozen=True)
class RequestPhase:
    phase_id: PhaseId
ControllerAction = KeepPhase | RequestPhase            # controller_action:v1
```

Domain semantics, not indices (`ARCH §12`). An RL action index becomes one of these in M4's
adapter, never before the safety layer.

## 6.4 The legal action mask (`ARCH §15`)

Derived from the plan and the executor's state, nowhere else:

```
KeepPhase        always legal — the no-op; at max green it does not prevent SIG-D06's force,
                 and `max_green_reached` says so
RequestPhase(p)  legal  iff  p is a stage of the plan and p ≠ the current stage (the target,
                 during a transition); a legal request during min green or a transition is
                 accepted and deferred, and the mask exposes `deferred_until_s`
```

The mask is part of the observation, so a controller — or M4's policy — never has to learn
the envelope from rewards (`RL §7`). Two intersections with different programs get different
masks from the same code, which is what makes heterogeneous networks possible in M8.

## 6.5 Timeout, lateness and fallback (`SIG-D07`)

- **Budget.** A controller has until the end of the decision step to return; there is no
  simulated "late" because `decide` is synchronous.
- **Lateness.** The runner wraps each `decide` in a monotonic wall-clock measurement outside
  Zone A. It never enters a parquet: `tests/simulation/sumo/test_reproducibility.py:71`
  compares every parquet in the run directory, and a host-load-dependent float would make two
  faithful runs unequal. Per-call latencies and the configured `decide_deadline_s` go to
  `controller.json` (provenance, like the manifest's timestamps); the number of calls over the
  deadline goes to the manifest as `controller_late_count`, in `NON_REPRODUCIBLE_FIELDS`
  (§7.4). The run continues unchanged: the action that arrived is the action that is used.
  `verify-run` refuses to compare when either run's `controller_late_count` is non-zero — the
  same refusal gate as a dirty tree, read explicitly rather than through a field set.
- **Illegal action.** A `RequestPhase` for a phase that is not a stage of the plan, or for
  the stage already current, is rejected: `action_rejected` is logged with the reason and the
  action becomes `KeepPhase`. A controller that is rejected is still called next boundary;
  nothing is retried on its behalf.
- **Exceptions.** A controller that raises ends the run with `termination_reason = aborted`
  and the exception recorded in `controller.json`; the layer does not guess what it meant.
  Today `run_scenario` writes no manifest when the loop raises (`cli.py`); phase 2 restructures
  it so an aborted run still leaves an honest manifest (`ST-D10`'s reason for `aborted`).

## 6.6 Diagnostics (`ARCH §26`)

`ControllerDiagnostics` is a frozen mapping the controller fills as it likes — pressure per
stage, solver status, value estimates — and it must be a function of what the controller saw,
never of a clock. The runner writes one row per boundary to
`evaluation/controller_diagnostics.parquet`, its one home; latency is not in it (§6.5). It is
not a metric input: `ARCH-D05` and `AP-05` keep KPI code away from controller internals, and
`RunDirectory.evaluation(table)` would happily read it, so the fence is a test in the shape
`ST-D30` already uses — the metrics package never names `controller_diagnostics` (§10).

---

# 7. Wiring

## 7.1 The run loop

`cadence run` gains `--controller <id:version>` (default `none`), `--decision-interval-s`
(required when a controller is named), `--controller-config <path>` (optional JSON).
`run_scenario` becomes:

```
plans        = build_signal_plans(topology, signal_plan_yaml)    # None when controller is none
controller   = registry[controller_id](...)                      # M2 registry: none, fixed_time_program
executors    = {id: SignalExecutor(plan) for each intersection}
loop:
    state  = connection.step()                                   # unchanged
    if boundary(now_s):  action = timed(controller.decide)(observation(state, executors))
    commands, events = executors.tick(state, action)
    connection.apply_signal_commands(commands)                   # the one write site
    recorder.record(state, teleports, ground_truth, signal_events)
```

With `controller_id = "none"` there are no plans, no executors and no write: the loop is the
M1 loop (`SIG-D08`).

## 7.2 Controller identity and registry

Controllers are declared the way metrics are (`ST-D24`'s registry pattern, `M1b` §6.2): a
decorator beside the class, `controller_id` and `controller_version` on the class,
`registered_controllers()` for the CLI. M2 ships two: `none` (the absence, `NO_CONTROLLER_ID`
as today) and `fixed_time_program:v1`.

## 7.3 The fixed-time test controller, and the acceptance test (`SIG-D08`)

`fixed_time_program:v1` requests, at each boundary, the stage the static program would be
in at that time — computed from `tls_program.parquet`'s durations and nothing else. Under the
executor it reproduces the program's own switching times exactly **under two preconditions**,
both measured (review, 2026-09-06): `decision_interval_s` divides every switch time of the
static program (on s0: 1 s and 3 s hold, 5 s misses the switch at 42 and serves it at 45), and
each stage's `[min_green_s, max_green_s]` brackets its program duration (a `max_green_s` of 40
against a 42 s stage fires `max_green_forced` every cycle). The acceptance run uses
`decision_interval_s = step_length_s` and s0's placeholder envelope, which brackets 42.

Under those, a run under `fixed_time_program:v1` is **byte-identical to the same run under
`none` over the M1 artifact set** — `events.parquet`, every parquet under `topology/`,
`state/` except `state/signal_event.parquet`, `ground_truth/`, and `evaluation/tripinfo.parquet`
— on both bindings. Outside that set the two runs legitimately differ: `manifest.json`
(controller fields), `controller.json` (exists on one side), `state/signal_event.parquet` (rows
on one side, an empty table on the other) and `evaluation/controller_diagnostics.parquet`. A
difference inside the set means the executor changed a signal at a time the program did not,
which is a defect, not a tolerance. `verify-run` will refuse the pair — `decision_interval_s`
is `None` under `none` — and that is right: they are the same simulation, not the same
experiment; the acceptance test is a byte comparison, not a `verify-run` call.

This is the whole milestone's acceptance test because it exercises every part at once — plan,
executor, mask, commands, writer, recorder, manifest — and its expected value was fixed
before M2 existed.

## 7.4 Manifest (`SIG-D10`, `SIG-D11`, program-map C7)

| field | set (`ST-D33`) | value |
|---|---|---|
| `decision_interval_s` | comparability | `None` under `none` |
| `signal_plan_sha256` | comparability | `None` when the scenario has no plan |
| `observation_version` | comparability | `controller_observation:v1`; `None` under `none` (`ARCH §27`, `ARCH-D08`) |
| `action_version` | comparability | `controller_action:v1`; `None` under `none` |
| `controller_config_sha256` | controller identity (⊂ intended difference) | SHA-256 of the canonical JSON of the config; `None` for `none` |
| `controller_decide_count` | outcome | 0 under `none` |
| `controller_late_count` | non-reproducible — a refusal gate `verify-run` reads explicitly | 0 under `none` |

Two tests fail until each is classified: `test_the_five_field_sets_partition_the_manifest_exactly`
and `test_manifest_declares_every_reproducibility_field` (its hardcoded `FIELDS` set). That is
the point of the partition. `controller.json` holds the config, `decide_deadline_s`, the
per-call latencies, and the controller's `diagnostics()` at close; nothing in it is compared.

Two carry-forwards from `DIRECTION` §7 land here by their own rule: row 7 (`artifacts._SCHEMAS`
becomes public with the next change to `artifacts.py`, which §5.4's new table is) is taken in
phase 1. Row 6 (splitting `cadence_dirty_digest` into tracked and untracked, "with the next
milestone that changes the manifest") is **declined for M2** and its wording amended at
close-out: M2's manifest change is additive, the split changes the meaning of an existing
field and the refusal text `verify-run` prints, and M3 — the first milestone that compares
runs for a claim — is its first consumer.

---

# 8. Scope

## 8.1 In

| | why |
|---|---|
| `SignalPlan` from topology + `signal_plan.yaml`; `validate-scenario` checks | §4, `SIG-D02`, `SIG-D03` |
| The executor, its commands, the one SUMO write site, `state/signal_event.parquet` | §5 |
| `TrafficController` protocol, context, observation v1, action v1, mask, diagnostics | §6 |
| Timeout as lateness; illegal-action fallback | §6.5, `SIG-D07` |
| `cadence run --controller`, the controller registry, `none` and `fixed_time_program:v1` | §7 |
| Five manifest fields and `controller.json` | §7.4 |
| Architecture tests R3, R4, R5; the contract test suite; the byte-identical acceptance test | §10 |

## 8.2 Out

| | where it goes |
|---|---|
| Any controller that decides anything (tuned fixed-time, Max-Pressure, RL) | M3, M8, M4 |
| SUMO-native actuated as a runnable controller identity | M3 (map "ยังไม่ชัด" 2); `SIG-D01` already says it runs without an executor |
| Observation adapters below O0, `SensorRealisticAdapter` | M4 (`ARCH §7`) |
| Reward of any kind | M4 (`AP-05`) |
| `ExtendPhase`, `SetGreenSplit` | M4 / M3 (`SIG-D09`) |
| Cycle-boundary events for `ARCH §17`'s cycle-failure and network-progress metrics | Taken, as a derivation rather than an event: for *every* run — `none`, `sumo_actuated`, or under an executor — a cycle boundary is a `phase_index` transition back into the program's first stage in `state/intersection.parquet`, so `DIRECTION` §7 row 5's "cycle boundary the run directory does not mark" is already marked. Naming and computing the two metrics is M3's, when there are two controllers to compare on them (map "ยังไม่ชัด" 1) |
| Splitting `cadence_dirty_digest` into tracked and untracked (`DIRECTION` §7 row 6) | M3 — see §7.4 |
| Multi-intersection coordination, offsets | M8 |
| Composing lamp states for programs that lack transition phases | never (`SIG-D01`); such a network is regenerated |

## 8.3 The line between M2 and M3

M2 proves the layer can carry a controller without changing what the simulator does when the
controller says what the program would have said. M3 is the first controller that says
something else. Tuning — Webster splits, min/max values worth defending — is M3 (`TC-D04`
superseded by `TC-D09`–`TC-D11`); s0's `signal_plan.yaml` values in M2 are placeholders,
labelled so, chosen only to bracket the static program's 42 s stages — the one property §7.3's
acceptance test depends on. `DIRECTION` §2 calls M3 "the acceptance test for M2": M3 is the
first *use* of the contract by controllers that decide; §7.3 is M2's own proof that the layer
changes nothing when nothing should change. Both sentences stand.

---

# 9. What M2 hands forward

1. **M3 — the envelope values.** `signal_plan.yaml` exists; its numbers are M3's to tune and
   freeze (`TC-D11`).
2. **M3 — the SUMO-native actuated identity.** `sumo_actuated:v1` needs a program of
   `type="actuated"`, which `SIG-D01`'s executor refuses; M3 decides whether it is a controller
   with an empty `decide` or a manifest-only identity.
3. **M4 — decision interval versus minimum green.** With `decision_interval_s < min_green_s`
   most boundaries see a deferred request; M4 chooses the interval and whether the mask's
   `deferred_until_s` enters the observation.
4. **M4 — action semantics beyond v1** (`ExtendPhase`), and observation fidelity below O0.
5. **M8 — stages across intersections.** A `SignalPlan` per intersection is enough for a
   corridor; a shared cycle or offset is not in the plan and not in the contract.
6. **M3 — the dirty-digest split** (`DIRECTION` §7 row 6), declined here for the reason in §7.4.
7. **A network whose program lacks transition phases** is refused, not repaired. If M7's OSM
   import produces one, the fix is at `netconvert`, recorded as a scenario decision.

---

# 10. Testing

| kind | what | fixture |
|---|---|---|
| **Unit** | plan from s0: 2 stages, successor chains `[1]`, `[3]`, 6 movements each; refusal on a stage-after-stage program, on a yellow that turns a signal on, on a mismatched `signal_plan.yaml`; mask values in every executor mode; command sequences for request-during-min-green, request-in-transition, max-green-forced | hand-built `PhaseInfo` tuples + s0 topology |
| **Property** (hypothesis) | over random legal request sequences, including requests during transitions and back-to-back requests: two consecutive `SetPhase` commands never name two stages; `elapsed_s ≤ max_green_s + step_length_s`; a stage is never left before `min_green_s`; a pending request is served within one step of becoming legal and never served against the stage it named (the review's double-serve); a replaced request is logged; `tick` is deterministic under replay; seeding from a mid-transition `IntersectionState` reconciles on the first tick. On a real controller run, `phase_elapsed_s ≤ max_green_s + step_length_s` in every stage row of `state/intersection.parquet` and `≤ duration_s` in every transition row — the M2 form of M1a's `test_extract.py:54` bound, which keeps its `none`-only form | executor without SUMO; both s0 fixtures |
| **Architecture** | R3: nothing under `control/` imports `simulation/sumo/`; R4: exactly one module calls `trafficlight.set*`; R5: no RL vocabulary under `simulation/` or `control/`; the metrics package never names `controller_diagnostics` (§6.6); the existing R1/R2 fences | none |
| **Contract** | the suite every controller passes (`CLAUDE.md` §7): `initialize`, `reset`, a `decide` result inside the mask for every controlled intersection, `on_transition` receives what the executor did, `close`; run against `fixed_time_program:v1` and against a deliberately misbehaving controller (requests a transition phase; omits an intersection; raises — the run ends `aborted` with a manifest) | s0 plan |
| **SUMO integration** | *signal transition* (`CLAUDE.md` §7 table): a requested stage produces the program's yellow then the stage in `state/intersection.parquet`; `getEmergencyStoppingVehiclesIDList()` is empty on every step under the executor, and non-empty under a raw `setPhase(2)` replay of §3 — the detector must be shown to fire; reconciliation raises on a `type="actuated"` program | both s0 fixtures; a scratch actuated program |
| **Reproducibility** | `SIG-D08`: `none` before/after M2 against a golden digest of the M1 artifact set recorded before any M2 code lands; `fixed_time_program:v1` versus `none` byte-identical over that set on both bindings, at `decision_interval_s = step_length_s`; `SIM-D03` promoted from hypothesis by the second | `s0_turning` seed 1 |
| **Manifest** | the five-set partition and the hardcoded field set both fail until the seven new fields are classified; `verify-run` refuses a run with `controller_late_count > 0` | none |

The acceptance test is the reproducibility row. Everything above it exists so that when the
row fails the reason is already localised.

---

# 11. What the review changed

One Opus review on 2026-09-06 against the first draft: twenty findings, four blocking, every
one verified by running something. What moved:

| finding | change |
|---|---|
| **Blocking.** The executor never cleared `pending` after a transition, so a request absorbed during one was served a second time against the stage it named (measured: a spurious yellow at t = 55). | §5.1 steps 2–4 rewritten; "current stage" defined during a transition; property test added (§10). |
| **Blocking.** The acceptance test's byte-identity had two unstated preconditions, and §8.3 denied one (measured: 5 s interval and `max_green_s = 40` both break it). | §7.3 states both; §4.2 and §8.3 say the placeholder envelope must bracket the program. |
| **Blocking.** Wall-clock latency was written into a parquet the reproducibility test compares. | Latency lives in `controller.json`; the count is `controller_late_count`, non-reproducible, read by `verify-run` as a refusal gate (§6.5, §7.4). Map C6 amended. |
| **Blocking.** `controller_deadline_exceeded_count` was an outcome field, which `compare_manifests` never reads and `reproducible_fields()` compares. | Replaced as above. |
| The plan exposed no durations the executor needs. | `Stage.program_duration_s`, `SignalPlan.transition_phase_duration_s` (§4.3). |
| Executor initialisation unspecified; a non-zero offset starts mid-cycle. | Seeded from the first `IntersectionState`, may start `IN_TRANSITION` (§5.1). |
| Contract was single-intersection while claiming plural. | `decide` returns a mapping per intersection; an omitted one is `KeepPhase` (§6.1). |
| Observation labelled O0; it is O1. | §6.2; recorded as `observation_version`. |
| Cycle boundary re-deferred against two written handoffs. | Taken as a derivation valid for every run (§8.2). |
| Manifest set incomplete; `controller_config_sha256` mislabelled M3's own comparison. | Seven fields, two tests named; config hash joins controller identity (§7.4, `SIG-D11`). |
| Diagnostics had two homes and no fence. | One home; a fence test in `ST-D30`'s shape (§6.6). |
| `SIM-D03` adopted on 60 s of evidence with a future tense inside it. | Registered as a hypothesis; narrowed to what was measured (§3). |
| "Never dropped" was false for a superseded request. | `request_superseded`; `SIG-D05` reworded. |
| `DIRECTION` §7 rows 6 and 7 triggered and unaddressed. | Row 7 taken in phase 1; row 6 declined with the reason (§7.4). |
| No legal no-op at max green. | `KeepPhase` always legal; `SIG-D06` and `SIG-D07` reworded (§5.3, §6.4, §6.5). |
| Smaller: `SIM-D01`'s description of the second reset; tick ordering; four omitted action variants, not two; a unit-less parameter; unprovenanced YAML numbers; the abort path writes no manifest today; M3 versus §7.3 as "the acceptance test". | Each fixed where it stood. |

The review also found `test_a_finished_milestone_is_not_still_marked_current` red on `main`
since M1b's close-out merged: every task in the pointed-at plan was done while M2 was marked
current. Phase 1's plan, pointed at from `DIRECTION` §1, is what clears it; it ships on the
same branch as this document.
