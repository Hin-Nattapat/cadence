# P2-03 The executor on a real run

> Written 2026-11-11 · a record of decisions as of that date, never updated after close · the current domain lives in `CLAUDE.md`, `docs/roadmap/cadence.md` and `docs/learn/overview.md`

## Problem

The signal executor has been tested against a fake simulator. Its write site and its event table
(P2-02) have each been tested on their own. No run has yet let the executor drive SUMO's
lights from start to finish, so nothing shows that its transitions are safe on a real
network. A controller does not exist until P2-04, so this ticket uses a **request schedule**
in its place: a list of timed stage requests. Three facts make the shape non-obvious, all
measured on `s0_turning` under both bindings.

- **SUMO's emergency-stop list cannot fail here.** On s0 it stays empty even when a raw
  `setPhase` skips the yellow ten times. It takes switching every 2 s with no yellow, or an
  all-red, to fill it (27 and 3 vehicles, decelerating at exactly `emergencyDecel` = 9 m/s²).
  A safety test built on it would pass whatever the executor did.
- **Per-step braking is in no artifact.** So the safety test cannot read it from a run
  directory.
- **A transition's timer expires on the same step the executor acts.** This is the
  zero-margin race: who switches first was unknown.

## Usage

A test drives a scheduled run end to end and reads the run directory:

```python
from cadence.cli import ScheduledRequest, run_scenario

run_dir = run_scenario(
    S0_TURNING, tmp_path, seed=1, binding=BindingKind.LIBSUMO,
    request_schedule=(ScheduledRequest(20.0, IntersectionId("A0"), PhaseId(2)),),
)
# state/intersection.parquet: phase 1 at t = 21, 22, 23; phase 2 from t = 24
# state/signal_event.parquet: stage_requested and transition_started at 20, stage_entered at 23
# manifest.json: controller_id "request_schedule", controller_version "v1"
```

The safety test opens the connection itself and runs the same control step as `run_scenario`,
reading braking every step:

```python
from cadence.cli import start_executors, tick_executors

with SumoConnection(config, paths, seed=1, binding=binding) as connection:
    plans = build_signal_plans(connection.topology, envelope)
    result = connection.step()
    executors = start_executors(plans, result.state, step_length_s=config.step_length_s)
    while not connection.is_finished():
        tick_executors(connection, executors, state=result.state, requests=requests_due_now)
        result = connection.step()
        assert connection.hard_braking_vehicles() == ()
```

## Shape

In `cli.py`, which is the experiment runner today, beside `run_scenario`:

```python
@dataclass(frozen=True, slots=True)
class ScheduledRequest:
    time_s: float
    intersection_id: IntersectionId
    phase_id: PhaseId

REQUEST_SCHEDULE_CONTROLLER_ID = "request_schedule"
REQUEST_SCHEDULE_CONTROLLER_VERSION = "v1"

def run_scenario(scenario_root: Path, output_root: Path, *, seed: int, binding: BindingKind,
                 request_schedule: Sequence[ScheduledRequest] | None = None) -> Path

def start_executors(plans: Mapping[IntersectionId, SignalPlan], first: CanonicalTrafficState,
                    *, step_length_s: float) -> Mapping[IntersectionId, SignalExecutor]

def tick_executors(connection: SumoConnection, executors: Mapping[IntersectionId, SignalExecutor],
                   *, state: CanonicalTrafficState,
                   requests: Mapping[IntersectionId, PhaseId]) -> tuple[SignalEvent, ...]
```

**`request_schedule=None` is the `none` run, unchanged.** It builds no plan, no executor and
makes no write. Its run directory and manifest are byte-identical to today's (`SIG-D08`).

**With a schedule:**
1. Before the first step, `run_scenario` refuses three cases, each raising `ValueError`:
   - the scenario has no `signal_plan.yaml`;
   - the schedule names an intersection that has no plan;
   - the plan build refuses, for example a program whose `type` is not `static`.
2. After the first step, it starts one executor per plan from that step's state.
3. Every step, including the first, it calls `tick_executors` with the requests due, then
   `recorder.record_signal_events` with the events it returns.
4. The manifest and the run directory name carry `request_schedule` / `v1`.

**Requests due.** A request is due at the first step whose `now_s ≥ time_s`, and it is passed
exactly once. If more than one request for an intersection is due at a step, the earliest is
passed now and the rest wait for the following steps. A request is deferred, never dropped,
as `SIG-D05` treats a pending request.

**`tick_executors`** walks the executors in sorted `IntersectionId` order. For each one it
calls `tick` with that intersection's state, `now_s` and its request, if any. It applies the
commands through `connection.apply_signal_commands`, then returns all events in tick order.

`SumoConnection.hard_braking_vehicles() -> tuple[VehicleId, ...]` returns, sorted, the
vehicles whose acceleration in the step just taken is below the negative of their own
`decel`. It requires an open connection, like every other method. It is read-only; the run
directory does not record it.

`SIM-D04` registers the race's answer: at the step a transition phase's program duration
elapses, SUMO still reports that phase, and the executor's `SetPhase`, applied before the next
`simulationStep`, takes effect first. SUMO's own switch never fires. So the executor issues
transitions on time and holds no transition phase.

Dependency direction is unchanged:
- `cli.py` imports `control/`, `simulation/` and `simulation/sumo/`;
- `control/` imports nothing from `simulation/sumo/`.

## Decisions

- **The safety test asserts no hard braking:** no vehicle decelerates harder than its own
  `decel` while the executor drives. A raw `SetPhase` that skips the yellow ten times does
  produce hard braking, which proves the test can fail.
  - Why: SUMO enforces `emergencyDecel ≥ decel`, so no hard braking implies no emergency stop.
  - Why: the comfortable-stop threshold is the question a yellow interval answers.
  - Rejected: SUMO's emergency-stop list, because on s0 it fires only under faults far worse
    than a skipped yellow. Rejected: both, because the second assertion adds nothing.
  - Source: throwaway runs on `s0_turning` seed 1, checked against eclipse-sumo@1.27.1.
    - Ten raw switches: hard braking 2, emergency stops 0, peak deceleration 6.07 m/s².
    - Switching every 2 s: emergency stops 27.
    - Executor-driven and `none` runs: 0 of each.
    - A copy with `emergencyDecel = 5.0` makes SUMO's list count the same 2 vehicles.
- **The schedule enters through a `run_scenario` parameter only**, because P2-04's
  `--controller` replaces it. Rejected: a `--request-schedule` CLI flag, a public interface
  that would live one ticket.
- **A scheduled run records `controller_id = "request_schedule"`, version `v1`**, so the
  manifest does not claim there was no controller. Rejected: keeping `none`, which
  `verify-run` would take for the same controller. Rejected: a schedule digest field, which is
  P2-06's `controller_config_sha256`. Until then two different schedules are not told apart
  by their manifests.
- **The control step is one function** (`tick_executors`), called by `run_scenario` and by
  the safety test, so the test exercises the loop that runs. Rejected: writing hard braking to
  the run directory, a schema change for a test-only reading. Rejected: a loop of the test's
  own, which could drift from the real one.
- **The race is answered by measurement and pinned by a test.** Over a whole scheduled run on
  both bindings, every complete transition phase lasts exactly its program duration and
  reconciliation never raises. The answer is registered as `SIM-D04`.
  - Source: the prototype run of 600 s with a request for stage 2 at 20 s.
    - SUMO reported phase 1 at t = 21, 22 and 23 (elapsed 1, 2, 3).
    - The executor's `SetPhase(2)` at 23 was read back as phase 2 at 24.
    - Identical on traci and libsumo.
- **`SIM-D03` stays a hypothesis**, because its stated condition is a whole controller run.
  P2-04's G2 run meets it.

## Comps

none

## Out of scope

- A CLI flag, a controller and the contract (P2-04).
- A schedule digest in the manifest (P2-06).
- Recording braking in the run directory.
- Issue #25 (cycle boundary).

## Done when

Proven at seam: `run_scenario` with a request schedule on `s0_turning` under both bindings,
read from its run directory. The safety test reaches SUMO through `SumoConnection` and the
same `tick_executors`.

### Agent checks
- [ ] `rtk proxy make check` → exit 0, Documentation consistency OK, pytest passes
- [ ] `uv run pytest tests/simulation/sumo/test_signal_transition.py -q` → passes on both bindings. Each binding must show four things.
  - **The transition.** Stage 2 requested at 20 s gives phase 1 at t = 21–23 and phase 2 from 24.
  - **The events.** `stage_requested`, `transition_started` and `stage_entered` at 20, 20 and 23.
  - **The durations.** Every complete transition phase lasts its program duration.
  - **The elapsed bounds.** `phase_elapsed_s ≤ max_green_s + step_length_s` in stage rows, and `≤` the phase's duration in transition rows.
- [ ] `uv run pytest tests/simulation/sumo/test_signal_safety.py -q` → passes on both bindings: no hard braking at any step of the executor-driven run, and some under the raw path
- [ ] `uv run pytest tests/test_cli.py -q -k schedule` → the three refusals raise `ValueError` before the first tick: no signal plan, an unknown intersection, and an `actuated` program
- [ ] `uv run pytest tests/simulation/sumo/test_golden.py -q` → passes, with `git diff --exit-code tests/fixtures/golden`
- [ ] `grep -n "^SIM-D04:" research/decisions.yaml` → one line, status `adopted`

### Smoke

none

## Issues closed
- #16

## CONTEXT.md changes

none

## Size

single job, because it is one slice (a scheduled run from request to safe transition) in four steps.
