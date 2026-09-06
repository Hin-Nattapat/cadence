# M2 phase 1 — the signal plan and the executor

**Spec:** `docs/specs/2026-09-06-m2-signal-contract.md` (authority; this plan does not restate
it). **Program map:** `docs/programs/2026-09-06-m2-signal-contract.md`, phase
`signal-plan-and-executor`, contracts C1, C2, C8.

**Global constraints**
- Zone A throughout: TDD, `mypy --strict`, unit suffixes, frozen state (`CLAUDE.md` §2, §4).
- Nothing under `src/cadence/control/` imports `simulation/sumo/` (map R3, tested from Task 3).
- Exactly one module calls `trafficlight.set*` (map R4, tested from Task 5).
- No lamp string anywhere new: the executor selects program phases (`SIG-D01`).
- Every task ends with `rtk proxy make check` and its raw output; the gate was green at
  422 passed when this plan was written, plus the plan-status test this plan turns green.
- Status lines below are the only place phase position lives (`CLAUDE.md` §14). Flip them at
  task start and end and print `make status`.

**Interface pinned for the whole phase** (spec §4.3, §5.1):

```python
# control/plan.py
class Stage: phase_id, permitted_connections, permitted_movements, min_green_s, max_green_s,
             program_duration_s, transition_phase_indices, movement_signature
class SignalPlan: intersection_id, program_id, stages, transition_phase_duration_s,
             next_stage_in_program_order(phase_id) -> PhaseId
def build_signal_plans(topology: NetworkTopology, envelope: SignalPlanFile) -> Mapping[IntersectionId, SignalPlan]

# control/executor.py
class SignalCommand = SetPhase(intersection_id, phase_index) | SetRemainingDuration_s(intersection_id, remaining_s)
class SignalExecutor:
    def __init__(self, plan: SignalPlan, first: IntersectionState, now_s: float, step_length_s: float) -> None
    def tick(self, state: IntersectionState, now_s: float, request: PhaseId | None) -> tuple[tuple[SignalCommand, ...], tuple[SignalEvent, ...]]
    @property phase_state -> SignalPhaseState   # current stage / target, elapsed_s, pending, in_transition, max_green_reached

# simulation/sumo/signal_writer.py — the one write site
def apply_signal_commands(binding: ModuleType, commands: Iterable[SignalCommand]) -> None
```

---

### Task 1: The golden digest, before anything else lands
`status: todo`
**Files:** `tests/simulation/sumo/test_golden.py`, `tests/fixtures/golden/s0_turning-v1-seed1.json`

Map R6 / spec `SIG-D08`. The M1 artifact set (spec §7.3) of a `controller_id = "none"` run of
`s0_turning/v1` seed 1 under libsumo, hashed per file, committed as the expected value. Every
later task runs this test; it is the tripwire that says the layer changed nothing when nothing
was asked of it.

- [ ] **Step 1** — a test that runs the scenario, hashes each file in the M1 set, and compares
      against the committed JSON; on first run, with the JSON absent, it writes it and fails
      with "recorded, rerun" so a golden value is never recorded and trusted in one motion.
- [ ] **Step 2** — the same test under traci (the two bindings already agree, `test_reproducibility.py:71`).
- [ ] **Step 3** — `make check`, commit.

---

### Task 2: `signal_plan.yaml` and the manifest fields it needs
`status: todo`
**Files:** `src/cadence/simulation/signal_plan_file.py`, `src/cadence/simulation/scenario.py`
(loading the optional file), `src/cadence/simulation/manifest.py`, `scenarios/s0_turning/v1/signal_plan.yaml`,
`scenarios/s0_turning_oversaturated/v1/signal_plan.yaml`, `tests/simulation/test_signal_plan_file.py`,
`tests/simulation/test_manifest.py`, `tests/test_cli.py`

Spec §4.2, `SIG-D02`. The pydantic model (`extra="forbid"`, the two inequality rules), its
SHA-256, `signal_plan_sha256` in the manifest under `COMPARABILITY_FIELDS`, `None` when the
file is absent. Both s0 scenarios get the placeholder envelope from spec §4.2, with its
provenance comment, bracketing 42 s.

- [ ] **Step 1** — model + loader, test-first: refuses an unknown key, `min < step`, `max < min`.
- [ ] **Step 2** — `signal_plan_sha256` on `RunManifest`; the partition test and the
      hardcoded-field test both move deliberately; `verify-run` names it on mismatch.
- [ ] **Step 3** — `make check`, commit.

---

### Task 3: `SignalPlan` from the topology
`status: todo`
**Files:** `src/cadence/control/__init__.py`, `src/cadence/control/plan.py`,
`src/cadence/simulation/topology.py` (program `type` on the in-memory topology only),
`src/cadence/simulation/sumo/topology_reader.py`, `tests/control/test_plan.py`,
`tests/test_architecture.py` (R3)

Spec §4.1, §4.3, `SIG-D03`. Stages, transition chains, permitted connections and movements,
`program_duration_s`, `transition_phase_duration_s`, `movement_signature`; the three refusals
of spec §5.2 that are the plan's (stage after stage; a transition that turns a signal on;
envelope/program stage-set mismatch); refusal of a non-static program from the type read at
connection time. `tls_program.parquet`'s schema does not change.

- [ ] **Step 1** — unit tests on hand-built `PhaseInfo` tuples for every refusal, then on the
      real s0 topology: 2 stages `{0, 2}`, chains `[1]` and `[3]`, 8 connections and 6
      movements per stage, `movement_signature` disjoint between the two stages.
- [ ] **Step 2** — R3 architecture test: nothing under `control/` imports `simulation/sumo/`,
      in the shape of the metrics fence, with its own deliberate-violation test.
- [ ] **Step 3** — `make check`, commit.

---

### Task 4: The executor, without SUMO
`status: todo`
**Files:** `src/cadence/control/executor.py`, `src/cadence/control/events.py`
(`SignalEvent`, the kinds of spec §5.4), `tests/control/test_executor.py`

Spec §5.1, §5.3, `SIG-D04`–`SIG-D06`. The state machine exactly as written, including
seeding from the first `IntersectionState`, the transition-time definition of "current
stage", `pending` cleared on entering its target, `request_superseded`, forcing at maximum
green regardless of the action, and the hold command on stage entry.

- [ ] **Step 1** — known-answer tests: the review's double-serve scenario (request during a
      transition must not produce a second transition); a request at t = 3 of a 10 s minimum
      served at t = 10; back-to-back requests A then B during minimum green serve B once and
      log A superseded; nothing pending at maximum green forces program order; seeding inside
      a transition phase reconciles.
- [ ] **Step 2** — property tests (hypothesis) over random request sequences: the five
      invariants of spec §10, plus replay determinism.
- [ ] **Step 3** — the reconcile failure: an `IntersectionState` whose `phase_index` disagrees
      with `mode` raises, naming both.
- [ ] **Step 4** — `make check`, commit.

---

### Task 5: The one write site, and the signal event table
`status: todo`
**Files:** `src/cadence/simulation/sumo/signal_writer.py`, `src/cadence/simulation/sumo/connection.py`
(`apply_signal_commands`), `src/cadence/simulation/artifacts.py` (`state/signal_event`;
`_SCHEMAS` → `SCHEMAS`, `DIRECTION` §7 row 7), `tests/simulation/sumo/test_signal_writer.py`,
`tests/simulation/test_artifacts.py`, `tests/test_architecture.py` (R4), the test files that
import `_SCHEMAS`

Spec §5.4, `SIG-D04`. Commands become `setPhase` / `setPhaseDuration` calls here and nowhere
else. `RunRecorder` writes `state/signal_event.parquet` with a declared schema, empty under
`none`.

- [ ] **Step 1** — writer test against a fake binding recording the calls it received, in order.
- [ ] **Step 2** — R4 architecture test: `git grep "trafficlight.set" src/` names exactly one
      file, and it is this one.
- [ ] **Step 3** — the event table: schema, empty-table readability, one row per event kind.
- [ ] **Step 4** — `make check`, commit; Task 1's golden test must still pass — the empty new
      table is outside the M1 set by construction.

---

### Task 6: Driving the executor on a real run
`status: todo`
**Files:** `src/cadence/cli.py` (the loop gains an optional request source and the executor
wiring behind it; no controller yet), `tests/simulation/sumo/test_signal_transition.py`

Spec §5.1 on SUMO, §7.1's loop shape, and the two `CLAUDE.md` §7 rows M2 owns. Phase 1 has
no controller: a **request schedule** — `(time_s, intersection_id, phase_id)` tuples — stands
in for one so the executor can be exercised end to end without the phase-2 contract.

- [ ] **Step 1** — *signal transition*: a scheduled request for stage 2 at t = 20 on s0
      produces, in `state/intersection.parquet`, yellow phase 1 for exactly its program
      duration then stage 2, entered at the step the executor said; `state/signal_event.parquet`
      carries `stage_requested`, `transition_started`, `stage_entered` at those times.
- [ ] **Step 2** — *zero emergency stops*: `simulation.getEmergencyStoppingVehiclesIDList()`
      is empty on every step of that run; the same schedule replayed through a raw `setPhase`
      (a test-only path) is not — the detector is shown to fire, then the executor is shown to
      prevent it.
- [ ] **Step 3** — the M2 form of M1a's bound (spec §4.2): `phase_elapsed_s ≤ max_green_s +
      step_length_s` in stage rows, `≤ duration_s` in transition rows, on a run whose schedule
      holds stage 2 to 60 s; and the `none` run still satisfies `test_extract.py:54`.
- [ ] **Step 4** — reconciliation raises on a `type="actuated"` scratch program, before the
      first tick.
- [ ] **Step 5** — Task 1's golden test, both bindings, unchanged.
- [ ] **Step 6** — `make check`, commit.

---

### Task 7: Close phase 1
`status: todo`
**Files:** `docs/programs/2026-09-06-m2-signal-contract.md`, `docs/DIRECTION.md` §1 (pointer to
phase 2's plan when it exists), `docs/CODEBASE.md`

Map C1, C2, C8 → ✅ with `file:line`; `last-touched`; `CODEBASE.md` gains `control/` in the
folder map and the `signal_event` table in the layout (Thai). Then `notes-call` on the whole
phase, the STOP, and the git tail.

- [ ] **Step 1** — map and docs.
- [ ] **Step 2** — `make check`, commit.
