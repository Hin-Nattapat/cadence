# CADENCE roadmap

Definitions only; status lives in the GitHub issues and milestones. Phase `P<n>` is
milestone `M<n>` of the ladder (`PD-D02`), so P0 and P1 (M0, M1, both finished) have no
entry. A phase gets tickets when `/menu` revises it; until then it holds its goal,
done-when and out-of-scope. The reasoning behind the ladder is in
`docs/specs/2026-08-22-project-direction.md`; what each phase means in plain words is in
`docs/learn/overview.md`.

## P2 Signal Safety + Controller Contract
Goal: a controller drives SUMO's signals only through one contract, and the safety layer owns every transition.
Done when: the fixed external test controller runs through the contract on `s0_turning` under both bindings and the run directory equals the `controller_id = "none"` golden digest; `make check` passes.
Out of scope: reward, observation adapters beyond v1, tuned timings (M3), anything under `studies/`, `metrics/` and scenario changes.
Gate: G2 Does a controller that reproduces SUMO's static program, driven through the contract, produce exactly the `none` run? If it fails, the executor or the contract misses a transition rule, and M3 does not start until it is found.

Authority for every P2 ticket: `docs/specs/2026-09-06-m2-signal-contract.md`.

### P2-01 Status moves to the tracker
Issue: #14
th: ย้ายสถานะงานไปไว้ใน GitHub issues
Goal: the roadmap and GitHub become the only places work is defined and tracked.
Scope:
- Remove `tools/plan_status.py`, `make status`, the `SessionStart` hook and `tests/test_plan_status.py`.
- `docs/DIRECTION.md` §1 and §2 become a pointer to this roadmap; §3–§9 stay.
- `CLAUDE.md` "Where the work stands" says: definitions here, status in GitHub, read both live.
- Delete `docs/plans/2026-09-06-m2-signal-plan-and-executor.md` and `docs/programs/` (with `verify-m2-signal-contract.sh`); what P2-02 and P2-03 still need from them is in their entries below.
Done when: `make check` passes; `git grep -n "plan_status\|make status\|docs/programs" -- . ':!docs/specs'` prints nothing.
Slices: none
Decisions: none
Blocked by: none

### P2-02 The one write site and the signal event table
Issue: #15
th: จุดเขียนไฟจุดเดียว และตาราง signal event
Goal: executor commands reach SUMO through exactly one module, and every executor event is recorded.
Scope:
- `simulation/sumo/signal_writer.py`: `apply_signal_commands` turns `SetPhase` / `SetRemainingDuration_s` into `setPhase` / `setPhaseDuration`, preserving order within a tick (`SetPhase` first).
- Architecture test: `trafficlight.set` appears in exactly one file under `src/`, this one.
- `state/signal_event.parquet` with a declared schema, written by `RunRecorder`, empty under `none`; `_SCHEMAS` becomes public `SCHEMAS`.
- Fix `artifacts.py`'s `by_index`, which keeps only the last connection per `(tls, link_index)` while `plan.py` keeps all: a list per index, tested on a hand-built two-connection group.
Done when: `make check` passes, including the writer test against a recording fake binding, the architecture test, the empty-table and one-row-per-event-kind tests, and the unchanged golden digest.
Slices: none
Decisions: SIG-D04, SIG-D08
Blocked by: none

### P2-03 The executor on a real run
Issue: #16
th: ให้ executor ขับไฟบนการรันจริง
Goal: a request schedule drives the executor on SUMO end to end, and the transitions are shown safe.
Scope:
- `cadence run` accepts an optional request schedule (`(time_s, intersection_id, phase_id)` tuples) standing in for a controller; no controller contract yet.
- Signal transition: a request for stage 2 at t = 20 on `s0_turning` yields yellow for its full program duration then stage 2, at the steps the executor reported, with `stage_requested`, `transition_started` and `stage_entered` rows.
- Zero emergency stops on every step of that run; the same schedule through a raw test-only `setPhase` path does produce them.
- `phase_elapsed_s ≤ max_green_s + step_length_s` in stage rows and `≤ duration_s` in transition rows on a run holding stage 2 to 60 s; the `none` run still meets M1a's bound.
- Reconciliation raises on a `type="actuated"` program before the first tick.
- The zero-margin race: at the step a transition phase's timer expires, measure under libsumo and traci over every transition of a 600 s run whether SUMO's own advance or the executor's `SetPhase` wins; record the answer as a new `SIM-D` and, if SUMO wins, issue one step early or hold transition phases.
- `docs/CODEBASE.md` gains `control/` and the `signal_event` table (Thai).
Done when: `make check` passes with the transition, emergency-stop, elapsed-bound, reconciliation and golden-digest tests on both bindings, and the race's `SIM-D` is registered.
Slices: none
Decisions: SIG-D01, SIG-D03, SIG-D04, SIM-D01, SIM-D02, SIM-D03
Blocked by: P2-02

### P2-04 Controller lifecycle and action v1
Issue: #17
th: วงจรชีวิตของ controller และ action v1
Goal: the narrowest complete controller path: a controller decides, the contract carries it, the executor applies it, and G2 is answered.
Scope:
- `TrafficController` lifecycle (`initialize`, `reset`, `decide`, `on_transition`, `diagnostics`, `close`) as a `Protocol`, and `ControllerContext`; `decide` returns one action per controlled intersection.
- `ControllerObservation` v1 as a view over canonical state.
- `ControllerAction` v1 = `KeepPhase` | `RequestPhase(phase_id)`, versioned `controller_action:v1`.
- The contract test suite every controller passes.
- The fixed external test controller that reproduces the static program; its run equals the `none` golden digest (G2).
- Architecture tests: nothing under `control/` imports `simulation/sumo/` (`ARCH-D03`); no RL concept in `simulation/` or `control/` (`AP-02`).
Done when: `make check` passes with the contract suite and the G2 digest test on both bindings.
Slices: none until its recipe; split there if it exceeds one session.
Decisions: ARCH-D01, ARCH-D03, ARCH-D04, AP-02, SIG-D07
Blocked by: P2-03

### P2-05 Legal action mask
Issue: #18
th: action mask ที่ถูกกฎ
Goal: a controller can ask which actions are legal now, derived only from the signal plan and the executor's state.
Scope:
- A function of (plan, executor state) → mask; never read from a network file.
- Property test: an action the mask allows never makes the executor violate min green, max green or transition order.
Done when: `make check` passes with the mask's property test.
Slices: none
Decisions: none
Blocked by: P2-04

### P2-06 Timeout, fallback and manifest fields
Issue: #19
th: timeout, fallback และ field ใน manifest
Goal: a slow or illegal controller is handled deterministically and visibly.
Scope:
- The deterministic budget is the decision interval; a wall-clock guard in the experiment runner counts late decisions into `controller_late_count`, a non-reproducible manifest field that `verify-run` refuses to compare across, and never falls back mid-run.
- Per-call latency goes to `controller.json`, never a parquet.
- An illegal action falls back to `KeepPhase`, logged.
- `RunManifest` carries the controller config digest and decision interval, classified by `ST-D33`'s partition test.
Done when: `make check` passes with tests for the late count, the `verify-run` refusal, the illegal-action fallback and the manifest partition.
Slices: none
Decisions: ARCH-D09, SIG-D07, ST-D33
Blocked by: P2-04

## P3 Validation Controllers
Goal: tuned fixed-time and SUMO native actuated run through the M2 contract, as the acceptance test for M2 and the Tier 0 baselines.
Done when: both controllers run on S0 through the contract with frozen timings, and their metrics are reproducible across seeds.
Out of scope: RL, Max-Pressure, real-world scenarios.
Gate: G3 Is the tuned fixed-time controller a fair baseline (not deliberately weak) and does actuated respond to demand? If not, M6's comparison would be meaningless; retune before M4.

## P4 RL Adapter
Goal: a Gymnasium adapter exposes the contract to RL: observation builder v1, action mapping, reward v1.
Done when: a random policy runs episodes through the adapter on S1 with versioned observation and reward.
Out of scope: training algorithms (P5), reward shaping beyond v1.
Gate: none

## P5 PPO (+ DQN reference)
Goal: training and evaluation pipelines for PPO, with DQN as a reference, checkpointed and multi-seed.
Done when: PPO and DQN train and evaluate on S1 over several seeds with checkpoints and reproducible evaluation.
Out of scope: hyperparameter search beyond what convergence needs, multi-intersection RL.
Gate: none

## P6 Single-Intersection Experiments
Goal: fixed-time vs actuated vs RL on controlled synthetic demand.
Done when: a study under `studies/` reports the comparison across regimes A–C with seeds and confidence intervals.
Out of scope: real-world networks, corridors.
Gate: G6 Does RL beat tuned fixed-time and actuated in regime C on S1? If not, revisit observation and reward before P7.

## P7 Real-World Intersection
Goal: an OSM-derived, validated single intersection: the demonstration milestone.
Done when: the S2 scenario passes its validation checks and the P6 comparison reruns on it.
Out of scope: corridors, city scale.
Gate: G7 Does the real-world intersection validate against its observed data? If not, the site or demand source (`PD-Q01`) is revisited.

## P8 Corridor + Max-Pressure
Goal: a 3–5 signal corridor with finite downstream storage, a spillback metric, turn-ratio estimation, and Max-Pressure as the network-aware baseline.
Done when: Max-Pressure runs on S3 through the contract and the spillback metric is registered and tested.
Out of scope: network-aware RL (P9), MARL, capacity-aware pressure variants.
Gate: none

## P9 Network-Aware RL vs Max-Pressure
Goal: Study 1: network-aware RL against Max-Pressure in oversaturation and spillback regimes.
Done when: the Study 1 study reports the comparison in regimes C and D with seeds and confidence intervals.
Out of scope: MARL, GNN, city scale, deployment.
Gate: G9 Does network-aware RL beat Max-Pressure in regimes C and D? Either answer is the Study 1 result; a no is reported, not hidden.
