---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Python style

How Python is written in CADENCE. This file is the single source for it: Claude Code loads it
whenever a Python file is touched (`.claude/rules/style.md` links here), and `CLAUDE.md` sends
every other agent here before any Python. The project rules it serves (zones, boundaries,
anti-rot) are in `CLAUDE.md`; the reasoning behind both is in
`docs/specs/2026-08-22-project-direction.md`.

- **Scope.** Rules here bind Zone A (`src/cadence/`) and `tools/`. Zone B (`studies/`) is
  formatted and linted only. Tests follow the naming and comment rules; they are exempt from
  annotations.
- **Linter first.** Whatever ruff, mypy or a test can check lives in `pyproject.toml` or
  `tests/`; the table at the end lists what is already covered.
- **New and touched code.** Rules marked *(forward)* were adopted on 2026-11-10 from the
  owner's phinit style. They bind new code and any function you edit; existing code is not
  retrofitted for them.
- Baselines: [PEP 8](https://peps.python.org/pep-0008/), [PEP 20](https://peps.python.org/pep-0020/),
  the [Scientific Python Development Guide](https://learn.scientific-python.org/development/).

---

## 1. Principles *(forward)*

**Simple over clever.** Solve the problem the plainest way that works. A loop a reviewer can
check beats a vectorised one-liner nobody can.

**Two concrete cases before an abstraction.** A class, `Protocol`, generic, option or base
class appears when a second real case needs it. The controller contract (`ARCH-D01`) is the
designed exception.

**Functions before classes.** Code without state is a module-level function. A class holds
state or implements a `Protocol`.

**Pure core, thin edges.** Computation is pure functions on plain data. SUMO, files, the
clock and the environment are reached at the edges and passed in.

---

## 2. Layout

- **Name a module for what it provides** *(forward)*: `queue.py`, `executor.py`,
  `topology.py`. Generic names (`utils`, `helpers`, `common`, `misc`) are never used.
- **Order inside a module** *(forward)*: constants → public types → public functions →
  private helpers.
- **A helper used by one module lives in that module**, prefixed `_` *(forward)*. When a
  second module needs it, it moves to a module named for what it does.
- **Absolute imports** *(forward)*: `from cadence.types import LaneId`.
- Every SUMO surface (`traci`, `libsumo`, `sumolib`) is imported only under
  `cadence.simulation.sumo` (`ST-D12`); everything else reaches the simulator binding through
  `cadence.simulation.sumo.binding` (`ARCH-D02`).

---

## 3. Data and types

**Frozen state.** Value types are frozen dataclasses (an accumulator such as `EventLog` is
the exception); new ones are `@dataclass(frozen=True, slots=True)` *(forward)*. Return new
values instead of mutating arguments; a mutable default argument is never written.

**Optional means `X | None`,** and `None` means "not applicable", never "failed" *(forward)*.
A failure raises.

**Types everywhere.** Every function in `src/` and `tools/` has full annotations and passes
`mypy --strict`. Use 3.12 syntax: `list[str]`, `X | None`, `type Alias = ...`. Use `cast`
only where a library's stubs are wrong, never to silence a real error.

**No magic numbers.** Every numeric constant is a named `UPPER_CASE` constant with a
provenance comment (§10).

---

## 4. Units, identifiers, versions, scope (`PD-D04`)

**Units are part of the name.** Every physical quantity carries its unit as a suffix:

```
length_m  time_s  speed_mps  accel_mps2  queue_count_veh  flow_vehph
occupancy_ratio (0-1)  saturation_pct (0-100)
```

Bare `length`, `speed`, `time`, `queue` are rejected. The failure this prevents is a `km/h`
value used as `m/s`, staying plausible and wrong until it reaches a report.

**Identifiers are distinct types.** In SUMO `"e1"` is an edge and `"e1_0"` is a lane; both
are `str`. Use the `NewType`s in `cadence.types` (`LaneId`, `EdgeId`, `MovementId`,
`IntersectionId`, `PhaseId`, …) and add one there when a new kind of identifier appears.

**Anything with an interpretation carries a version:** `"ppo:v1"`, `"corridor_peak:v2"`,
`"spillback_event_v1"`. Changing observation or action semantics requires a version bump. A
metric definition is never edited; add `_v2`.

**Temporal scope is explicit:** `halting_count_now`, `arrived_count_window_60s`,
`waiting_total_episode_s`. Never `avg_waiting`: averaged over what?

---

## 5. Determinism (`AP-06`)

Zone A has no wall-clock reads, no unseeded randomness and no dependence on dict or set
iteration order. Every source of randomness is seeded from experiment metadata. Time comes in
as an argument, in simulation seconds.

---

## 6. Errors *(forward)*

- **Raise, don't return error values.** No `None`, `False` or sentinel string signals failure.
- **Chain the cause** with `raise … from err` when translating a library error.
- **Catch narrowly, and only where you can handle it.** `except Exception` appears only at the
  CLI edge, to turn an error into an exit code. A caught error is handled or re-raised.
- Built-in exceptions (`ValueError`, `LookupError`) carry programming and input errors;
  CADENCE has no exception hierarchy of its own.

---

## 7. Naming

| What | Rule | Example |
|---|---|---|
| Modules, functions, variables | `snake_case` | `queue_length_m`, `as_of_s` |
| Classes, Protocols, type aliases | `PascalCase`, no `Base`/`Abstract`/`Impl` affixes | `SignalPlan` |
| Constants | `UPPER_CASE` | `CAR_MAX_SPEED_MPS` |
| Private | leading `_` | `_approach_pairs` |
| Tests | `test_<unit>_<behaviour>`, the scenario in words | `test_queue_length_peak_never_exceeds_the_lane_it_is_measured_on` |

**Abbreviations** are limited to the whitelist `id, tls, veh, osm, rl, mp, mpc`.

---

## 8. Functions and call sites *(forward)*

**Keyword-only arguments beyond the obvious first one or two:**

```python
def discharge_time_s(queue: LaneQueue, *, saturation_flow_vehph: float, lost_time_s: float) -> float: ...
```

**Return a named type, not a bare tuple,** when there is more than one value: a frozen
dataclass or `NamedTuple`.

**Extract by responsibility, not line count.** A helper earns its place when its block has a
nameable job with its own invariants. A helper that only renames one call is inlined.

- `Any` appears in a signature only when no concrete type, `Protocol` or `TypeVar` fits.
- Comprehensions over `map`/`filter` with lambdas; a plain loop over a nested comprehension.
- `pathlib.Path` for every path.

---

## 9. Seams *(forward)*

Seams are `typing.Protocol`s, declared next to the code that consumes them. Implementations do
not inherit from the `Protocol`; mypy checks them structurally. Dependencies are constructed
at the edge and passed in; module-level singletons and hidden registry lookups stay out of
computation. The metric registry's `register` decorator is the accepted module-level
registry.

---

## 10. Comments (`PD-D05`)

**The default is no comment.** Each one earns its place by carrying one of:

| Kind | Content | Typical length |
|---|---|---|
| provenance | where a number, formula or definition came from | 1-2 lines |
| gotcha | counter-intuitive behaviour, a SUMO quirk | 1-2 lines |
| decision | why this approach rather than the obvious one | 1-2 lines |
| contract | what a module or public interface guarantees | up to ~5 lines, module docstrings and public interfaces only |

- Lengths are guidance, not a limit enforced by counting. The binding test is whether every
  line carries information the code and its types do not. A comment that keeps growing past
  its guidance belongs in `docs/` or `research/` behind a decision ID; it is not a signal to
  compress it into something cryptic.
- Every numeric constant carries a provenance comment.
- The kinds are a test, not a tagging syntax. The one written label is `GOTCHA:`, for
  behaviour that looks wrong but is not.
- Names and type hints carry arguments and returns; `Args:` / `Returns:` blocks are never
  written, nor is a comment that restates the code in English.
- Expect roughly 80% of Zone A functions to carry no comment.
  `compute_queue_length_m(lane: LaneState) -> float` already says everything.
- Citations and claims follow `CLAUDE.md`'s anti-rot rules (`PD-D06`).

---

## 11. Testing

Write the test first in Zone A. pytest, with tests under `tests/` mirroring the package they
cover.

| Kind | What |
|---|---|
| Unit | storage-capacity calculation, queue normalisation, action validation, phase-transition generation, metric aggregation |
| Property (hypothesis) | physical invariants for any input: queue length never exceeds lane length, occupancy stays in `[0, 1]`, phase elapsed time never exceeds max green |
| Architecture | every boundary in `CLAUDE.md`'s boundary table, as an executable test in `tests/test_architecture.py` |
| Contract | every controller, internal or external, passes `initialize`, `reset`, a valid `decide` result, timeout behaviour, `close` |
| Registry | every emitted metric has a registry entry with name, version, unit and definition; every decision reference resolves and is not superseded or retracted |

**SUMO integration** (`@pytest.mark.sumo`):

| Test | Asserts |
|---|---|
| network smoke | the simulation starts and progresses |
| queue discharge | a known queue under green clears within expected bounds |
| downstream storage | a finite downstream link can reach congestion and spillback |
| signal transition | a requested phase produces a valid yellow / clearance sequence |
| reproducibility | the same seed and config produce matching output |

- **Parametrize branching cases** with `ids` that describe the behaviour.
- **No mocks of our own code** *(forward)*. Use a fake that satisfies the `Protocol`;
  `monkeypatch` only at a third-party boundary.

---

## 12. Tooling

`pyproject.toml`, `Makefile` and `.pre-commit-config.yaml` are the source of truth.

- **`make check`** runs ruff (lint and format check), mypy, the decision check and pytest. It
  passes before anything is called done.
- **uv** manages Python and dependencies.

## 13. What the tools already cover

| Concern | Tool / rule |
|---|---|
| Formatting, import order | `ruff format`, ruff `I` |
| PEP 8 naming | ruff `N` |
| Missing annotations | ruff `ANN`, `mypy --strict` on `src/` and `tools/` |
| Mutable defaults, loop-variable capture, raising without `from` | ruff `B` (`B006`, `B023`, `B904`) |
| Outdated syntax (`Optional`, `List`) | ruff `UP` |
| Simplifiable code | ruff `SIM` |
| `traci` / `libsumo` / `sumolib` / `studies` imported in `src/` outside their owner (`tools/` is exempt) | ruff `TID251` banned-api, `tests/test_architecture.py` |
| Raw lamp strings anywhere in Zone A | `tests/test_architecture.py` |
| Decision IDs in `src/`, `tools/` or `docs/` that are unregistered, superseded or retracted | `tools/check_decisions.py` |
| Metric names, versions and the registry set | `tests/metrics/test_registry.py` |

---

## Appendix: why these choices

| Decision | Why |
|---|---|
| Unit suffixes, `NewType` ids, versions, temporal scope | `PD-D04`: wrong units stay plausible until a report; ids of different kinds are all `str` in SUMO. |
| No `Args:`/`Returns:` docstrings | `PD-D05`: type hints already state them, and docstring boilerplate rots. |
| Decision IDs, never headings | `PD-D06`: headings get renamed; IDs cannot change meaning. |
| No wall-clock, seeded randomness | `AP-06`: a run that cannot be reproduced cannot be compared. |
| `Protocol`, not ABC | Structural typing: implementations need no import of the seam. |
| `raise … from err` | The original error stays attached for debugging. |
| Keyword-only arguments | A call with three bare numbers cannot be read without the signature. |
| Forward-only adoption of phinit's rules | The maintainer chose it on 2026-11-10: the gain is in new code, and a retrofit is churn with no behaviour change. |
