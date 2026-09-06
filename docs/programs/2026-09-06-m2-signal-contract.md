---
program: m2-signal-contract
status: active
phases: [signal-plan-and-executor, controller-contract]
repos: [cadence]
last-touched: 2026-09-06
---

# M2 — Signal Safety + Controller Contract

A thin map (maintainer's option B, 2026-09-06). It does not restate the roadmap, the rules or
the decisions — §0 points at them. It holds only what M2 owes later milestones (§3) and the
premises about SUMO that a grep of this repository cannot settle (§4). Steps, files and code
belong to each phase's plan under `docs/plans/`, in `CLAUDE.md` §14's format.

## §0 reference locations

| what | where | editable |
|---|---|---|
| roadmap, M2 row, what M1b carried forward | `docs/DIRECTION.md` §2, §7 | yes |
| working rules; the five §3 boundaries with no test yet | `CLAUDE.md` §3–§7 | yes |
| decision ids (`ARCH-D*`, `AP-*`, `ST-D*`, `TC-D*`, `MP-D*`) | `research/decisions.yaml` | governance only |
| controller contract, safety layer, timeout, masks | `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §9–§16, §25–§29 | no (research) |
| actuated control vocabulary; SUMO native actuated | `research/CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` Part II | no |
| RL adapter's expectation of the safety layer, decision interval | `research/CADENCE_RL_TSC_RESEARCH.md` §6–§8 | no |
| Max-Pressure's expectation: same transition layer (`MP-D03`), stage representation (`MP-D04`) | `research/CADENCE_MAX_PRESSURE_RESEARCH.md` | no |
| what the harness reads from TLS today | `src/cadence/simulation/sumo/{signals,topology_reader,extract}.py` | yes |
| SUMO TraCI TLS setters / getters / phase attributes (URLs, human-reachable) | `sumo.dlr.de/docs/TraCI/Change_Traffic_Lights_State.html` · `TraCI/Traffic_Lights_Value_Retrieval.html` · `Simulation/Traffic_Lights.html` | no |

## §1 กฎของโครง

| # | rule | goes red at | status |
|---|---|---|---|
| R1 | No `traci` / `libsumo` import outside `simulation/sumo/` (`ARCH-D02`) | `uv run pytest tests/test_architecture.py::test_only_the_binding_module_imports_the_simulator` | ✅ |
| R2 | No raw lamp string outside the signal safety layer, which the test already places at `src/cadence/control/` (`tests/test_architecture.py:12`) | `::test_no_raw_lamp_strings_outside_the_signal_safety_layer` | ✅ today; M2 fills the allowlisted package for the first time |
| R3 | A controller consumes canonical state, never raw simulator data (`ARCH-D03`): nothing under `control/` imports `simulation/sumo/` | a new test in `tests/test_architecture.py`, same shape as the metrics fence at `:245` | ⬜ phase 2 |
| R4 | Controllers request; the safety layer owns transitions (`ARCH-D04`, `AP-04`): exactly one module calls `trafficlight.set*`, and it is under `simulation/sumo/` | a new test: `git grep -n "trafficlight.set" src/` returns one file | ⬜ phase 1 |
| R5 | No RL concept in the simulation core or the safety layer (`AP-02`) | a new test: `git grep -n -i -E "torch|gymnasium|replay|ppo|dqn" src/cadence/{simulation,control}` returns nothing | ⬜ phase 2 |
| R6 | A run with `controller_id = "none"` is byte-identical before and after M2 over the M1 artifact set (`events.parquet`, `topology/`, `state/` minus `signal_event`, `ground_truth/`, `evaluation/tripinfo.parquet`) | `tests/simulation/sumo/test_reproducibility.py:71` on both bindings, plus a golden digest of that set for `s0_turning` seed 1 taken before any M2 code | ⬜ phase 1 task 1 records the golden digest first |
| R7 | The safety layer is a pure function of (plan, current signal, request, elapsed); no wall-clock inside it (`AP-06`) | a property test under `tests/control/` — see P9 for the one place the contract itself introduces a clock | ⬜ phase 1 |

## §2 phase map

**Phase 1 — `signal-plan-and-executor`** (repo `cadence`). Delivers: the domain signal plan
built from `topology/tls_program.parquet` (phases as sets of permitted connections, hence
movements; per-phase min/max green from configuration, not from the table — see P3); the
transition executor that turns "phase B requested" into a legal sequence (yellow for every
green that ends, all-red where the plan says so, then the target) and writes it to SUMO
through one binding call site; a `controller_id = "none"` path that still lets SUMO's static
program run untouched. Sets contracts C1, C2, C8. Must NOT touch: `metrics/`, scenarios,
`tls_program.parquet`'s schema. Prerequisites: none open — P9 answered (`SIG-D07`); P1, P2, P6 measured before the spec
(`SIM-D01`, `SIM-D02`); P7 measured for the setters used (`SIM-D03`) and hardened in phase 2.

**Phase 2 — `controller-contract`** (repo `cadence`). Delivers: the `TrafficController`
lifecycle (`initialize`, `reset`, `decide`, `on_transition`, `diagnostics`, `close` — `ARCH §9`),
`ControllerContext`, `ControllerObservation` v1 as a view over canonical state, the
`ControllerAction` variants M3/M4 need, the action mask derived from the same plan metadata,
the timeout/fallback rule (`ARCH-D09`), the contract test suite every controller must pass
(`CLAUDE.md` §7 "Contract"), and the fixed external test controller `ARCH §31` names — one that
reproduces the static program exactly, so R6 doubles as the acceptance test. Sets C3–C7. Must
NOT touch: reward, observation adapters beyond v1, anything under `studies/`. Prerequisite:
phase 1 merged.

### ยังไม่ชัด
- A cycle boundary the run directory does not mark (`DIRECTION` §7 row 5): whether the executor emits a cycle event — sharpened when phase 1's executor exists.
- SUMO-native actuated as a controller identity (`ARCH §16`, `TC-D05`): the contract must be able to *name* a controller that is configured in SUMO and never called; whether that is a `ControllerAction`-less lifecycle or a manifest-only identity is M3's question, sharpened by phase 2.
- Decision interval as experiment metadata (`RL §8`): the field belongs in the contract; its value and its interaction with min green are M4's — sharpened by phase 2.

## §3 สัญญาระหว่าง phase

| id | contract | set by | consumed by | concrete form | status |
|---|---|---|---|---|---|
| C1 | `SignalPlan`: phases keyed by `PhaseId`, each a set of connection signals from `tls_program`, with derived permitted movements and configured min/max green | phase 1 | phase 2, M3, M8 (`MP-D04` stage representation) | frozen dataclass in `control/`, built only from `topology/` | ❓ |
| C2 | Executor semantics: a request at time t yields a deterministic, logged transition sequence; SUMO is never left in an intermediate state longer than the plan's yellow/all-red; a request during min green is deferred, never silently dropped | phase 1 | phase 2, M3, M4 | events rows + a property test | ❓ |
| C3 | `TrafficController` lifecycle and `ControllerContext`; `decide` returns one action per controlled intersection, so one instance can see a corridor | phase 2 | M3, M4, M8 | `typing.Protocol` + contract test suite | ❓ |
| C4 | `ControllerAction` v1 = {`KeepPhase`, `RequestPhase(phase_id)`}; `ExtendPhase`, `SetGreenSplit` are not v1 (`ARCH §12` lists them as *possible*) | phase 2 | M3, M4 | tagged union, versioned `controller_action:v1` | ❓ |
| C5 | Legal action mask derived from C1 + executor state, never from a network file | phase 2 | M4 (`ARCH §15`) | function of (plan, executor state) → mask | ❓ |
| C6 | Timeout and fallback, per P9's answer: the deterministic budget is the decision interval; a wall-clock guard in the experiment runner **marks the run** — `controller_late_count`, a *non-reproducible* manifest field that `verify-run` reads as a refusal gate (amended from "comparability" by the spec review: a host-load count must not enter `reproducible_fields()`) — and never falls back mid-run; per-call latency goes to `controller.json`, never a parquet; the only fallback is for an *illegal* action and it is `KeepPhase`, logged (`SIG-D07`) | phase 2 | M4, M5 | manifest field + `controller.json` | ❓ |
| C7 | Manifest carries controller config digest and decision interval; `ST-D33`'s partition test forces their classification | phase 2 | M3 (`verify-run`), M6 | new `RunManifest` fields | ❓ |
| C8 | `controller_id = "none"` output is byte-identical to pre-M2 | phase 1 | every later milestone | R6's golden digest | ❓ |

## §4 premises

| id | premise | type | status | evidence / anchor | who can confirm |
|---|---|---|---|---|---|
| P1 | `setRedYellowGreenState` sets program id to `"online"` and holds the state "until the next call … or until setting another program"; SUMO "will not modify the state anymore" | external-api | ✅ measured 2026-09-06 → `SIM-D01`: `getPhase` freezes, `getSpentDuration` is unreliable, `setProgram` resumes the underlying clock | `TraCI/Change_Traffic_Lights_State.html`; spec §3 | — |
| P2 | `getSpentDuration` — "time spent in the current phase"; reset semantics after an override not stated. `phase_elapsed_s` (`state.py:87`, `extract.py:89`) inherits whatever it does | external-api · contested internal | ✅ measured → `SIM-D01` (reset on the first override, not on the second); resolved by `SIG-D01`, under which `online` never occurs | spec §3 | — |
| P3 | `minDur` / `maxDur` apply only to `type="actuated"`; for a static program `getAllProgramLogics` reports them equal to `duration`, so `tls_program.parquet`'s min/max columns carry no independent timing on `s0` | external-doc | ✅ | `Simulation/Traffic_Lights.html` phase attributes; `artifacts.py:57-66` | — |
| P4 | netconvert follows every green with a yellow sized from approach speed; all-red is **not** generated by default (`--tls.allred.time`). `s0` has 3 s yellow and no all-red | external-doc | ✅ | `Simulation/Traffic_Lights.html`; `scenarios/s0_turning/v1/network.net.xml:124-127` | — |
| P6 | `setPhase(index)` requires a valid index of the *current* program; whether it restarts the phase clock is not stated. Decides whether transitions run through program phases or through `online` states | external-api | ✅ measured → `SIM-D02`: applies in the same step, restarts the clock, program continues by its own sequencing | spec §3 | — |
| P7 | libsumo and traci agree on TLS **writes**. Reads are proven byte-identical (`test_reproducibility.py:71`); no write has been issued from CADENCE yet | external-api | ✅ for the four setters probed → `SIM-D03`; phase 2's byte-identical run under both bindings hardens it over a whole run | spec §3 | phase 2 (hardening) |
| P8 | `getControlledLinks` index == state-string index | external-doc | ✅ | `TraCI/Traffic_Lights_Value_Retrieval.html`; relied on at `topology_reader.py:99`, `ST-D05` | — |
| P9 | A controller timeout is a wall-clock deadline (`ARCH-D09`, `ARCH §25`) — but Zone A forbids wall-clock (`AP-06`, `CLAUDE.md` §4) | contested internal | ✅ answered 2026-09-06, option (c): the deterministic contract is a simulated budget (a decision is returned within the decision interval by construction); a wall-clock guard lives outside Zone A in the experiment runner and **marks the run** (manifest field, a comparability field under `ST-D33`, so `verify-run` refuses to compare across it) rather than falling back mid-run; latency is diagnostics (`ARCH §26`); a deterministic fallback exists only for an *illegal* action. → `SIG-D07`. | spec §2, §6.5 | maintainer — done |

## §5 verify

`docs/programs/verify-m2-signal-contract.sh` — `chk` lines for P1, P2, P6, P7, P9 on their
decision ids in `research/decisions.yaml`, for P3, P4, P8 on their file anchors, and for R2's
anchor. No `ask` line remains.
Decision ids are checked by `tools/check_decisions.py` inside `make check`.
