# P2-02 The one write site and the signal event table

> Written 2026-11-11 · a record of decisions as of that date, never updated after close · the current domain lives in `CLAUDE.md`, `docs/roadmap/cadence.md` and `docs/learn/overview.md`

## Problem

The signal executor decides when a light may change, but its output goes nowhere: it returns
`SetPhase` and `SetRemainingDuration_s` commands as data and `SignalEvent`s as a record, and
nothing applies the first to SUMO or writes the second to the run directory. P2-03 cannot
drive a real run until both exist. What makes the shape non-obvious: `SIG-D04` allows exactly
one module to change a light in SUMO, so the write site needs a mechanical fence, not a
convention; and `SIG-D08` requires a run with no controller to stay byte-identical over the
M1 artifact set, so the new table must appear on every run without moving the golden digest.
Two carry-forwards land here because this job touches `artifacts.py`: its schema table becomes
public, and its `by_index` keeps only the last connection of a link index that controls
several (latent on `s0_turning`, which has one per index).

## Usage

P2-03's run loop, after the executors tick:

```python
from cadence.simulation.sumo.connection import SumoConnection

commands, events = executor.tick(result.state.intersections[intersection_id], now_s, request)
connection.apply_signal_commands(commands)   # the one write site, through the connection
recorder.record_signal_events(events)
```

A test that exercises the writer without SUMO:

```python
from cadence.control.executor import SetPhase, SetRemainingDuration_s
from cadence.simulation.sumo.signal_writer import apply_signal_commands

apply_signal_commands(fake_binding, (SetPhase(A0, 2), SetRemainingDuration_s(A0, 61.0)))
assert fake_binding.calls == [("setPhase", "A0", 2), ("setPhaseDuration", "A0", 61.0)]
```

A metrics test building a frame with a declared schema:

```python
from cadence.simulation.artifacts import SCHEMAS

frame = pl.DataFrame(rows, schema=SCHEMAS["state/network"])
```

## Shape

`simulation/sumo/signal_writer.py`:

```python
def apply_signal_commands(binding: ModuleType, commands: Iterable[SignalCommand]) -> None
```

- `SetPhase(i, k)` → `binding.trafficlight.setPhase(str(i), k)`;
  `SetRemainingDuration_s(i, s)` → `binding.trafficlight.setPhaseDuration(str(i), s)`.
  `IntersectionId` is the TLS id.
- Applies in the order given and never reorders. Ordering within a tick (`SetPhase` before
  `SetRemainingDuration_s`) is the executor's rule; the writer preserves it.
- It is the only module under `src/` whose code calls a `set…` method on a `trafficlight`
  attribute; an architecture test enforces it by AST, alongside the existing fences.
- Dependency direction: `simulation/sumo/signal_writer` imports the command types from
  `control/executor`; `control/` still imports nothing from `simulation/sumo/` (`SIG-D04`).

`SumoConnection.apply_signal_commands(self, commands: Iterable[SignalCommand]) -> None`
requires an open connection (`RuntimeError` otherwise, like every other method) and delegates
to the writer. The connection still exposes no binding.

`simulation/artifacts.py`:

```python
SCHEMAS: Final[Mapping[str, Mapping[str, type[pl.DataType]]]]   # was _SCHEMAS

class RunRecorder:
    def record_signal_events(self, events: Iterable[SignalEvent]) -> None
```

- `SCHEMAS["state/signal_event"]` = `time_s` Float64, `intersection_id` String, `kind`
  String, `from_phase_id` Int64, `to_phase_id` Int64, `reason` String; the three last
  nullable (M2 spec §5.4).
- `record_signal_events` appends one row per event and may be called any number of times.
  `record()` is unchanged. A run that never calls it writes an empty table with the declared
  columns and types.
- `write()` sorts `state/signal_event` rows by `(time_s, intersection_id)` with a stable
  sort, so rows of one intersection in one tick keep the executor's order and the file does
  not depend on the order executors were iterated.
- `topology/tls_program` attributes each lamp position to **every** connection at that
  `(intersection_id, link_index)`, one row each, in topology order.

## Decisions

- `RunRecorder` takes signal events through a new `record_signal_events`, because the
  `none` path and every existing caller of `record()` stay untouched and an unused method
  yields the empty table by construction (rejected: a `signal_events=()` parameter on
  `record()`, as the M2 spec's pseudocode sketches, because every caller and test of
  `record()` would have to know about events).
- The write site is proven at two seams: a recording fake binding for call order, and real
  SUMO on `s0_turning` under both bindings through `SumoConnection` for meaning, because a
  fake proves only that the calls happen in order, not that `setPhaseDuration` counts from
  now (rejected: fake only, as the roadmap first scoped it, because P2-03 would then meet
  every SUMO surprise at once). Measured by prototype on both bindings: `setPhaseDuration(A0, 20)` applied after the step to t = 10 s leaves phase 0 readable at t = 30 s and phase 1 first at t = 31 s (source: a throwaway run on `s0_turning` seed 1, checked against eclipse-sumo@1.27.1); the one-step boundary is P2-03's zero-margin question.
- `SumoConnection.apply_signal_commands` lands now, delegating to the writer, because the
  real-SUMO test reaches SUMO only through the connection (rejected: wiring it in P2-03).
- The architecture fence parses the AST for a `set…` attribute on a `trafficlight`
  attribute, because a text grep would fail on a docstring that names the call, and the
  existing fences are AST-based.
- `SCHEMAS` is typed read-only (`Mapping`, `Final`), because a public module constant that
  any importer can mutate would let a test change another test's schema.
- Event rows are stably sorted by `(time_s, intersection_id)` on write, because P2-03 ticks
  several executors and the file must not depend on their iteration order (`AP-06`).
- `by_index` keeps a list per `(intersection_id, link_index)`, like `plan.py`, because a
  grouped junction puts several connections behind one lamp position (`ST-D05`).

## Comps

none

## Out of scope

- Ticking executors inside `cadence run`, any `cadence run` option, controllers: P2-03 and
  later.
- `events.parquet`'s schema (`ST-D08`).
- Open issues #21–#27; #25 (cycle boundary) needs the executor on a real run first.

## Done when

Proven at seam: `make check`, including the writer against a recording fake and against SUMO
on `s0_turning` under both bindings.

### Agent checks
- [ ] `rtk proxy make check` → exit 0, Documentation consistency OK, pytest passes
- [ ] `uv run pytest tests/simulation/sumo/test_signal_writer.py -q` → passes on both bindings: after `SetPhase(A0, 1)` the next step reads phase 1; after `SetRemainingDuration_s(A0, 61.0)` at t = 1 s the intersection is still in phase 0 at t = 50 s, while an untouched run is not; after `SetRemainingDuration_s(A0, 20.0)` at t = 10 s it is in phase 0 at t = 29 s and phase 1 at t = 32 s
- [ ] `uv run pytest tests/test_architecture.py -q` → passes, including the write-site fence and its deliberate-violation test
- [ ] `uv run pytest tests/simulation/sumo/test_golden.py -q` → passes with the golden file unchanged (`git diff --exit-code tests/fixtures/golden`)
- [ ] `git grep -n "_SCHEMAS" -- src tests` → no output

### Smoke

none

## Issues closed
- #15

## CONTEXT.md changes

none

## Size

single job, because it is one slice (the path from an executor's output to SUMO and to the run directory) of four steps.
