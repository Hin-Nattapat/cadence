# CADENCE — Research Agent Knowledge Handoff (Delta Only)

**Purpose:** Knowledge carried from the research/design conversation into the Codex research agent.  
**Scope rule:** This file intentionally contains only information that is **not already captured in the current `research/` documents**, or that **clarifies/corrects** those documents. It is not a replacement for `research/`.

## Migration status

This is a temporary delta ledger, not a decision source. `research/decisions.yaml` remains
authoritative. Pending items stay here until their milestone has a specification backed by
repository evidence.

| Items | Status |
|---|---|
| KH-001 | resolved by `PD-D01`/`PD-D02`; wording corrected below |
| KH-002–KH-004 | migrated to `ST-D05`/`ST-D06`; retain the OSM cases as M7 input |
| KH-005 | movement definition migrated to `ST-D06`; queue semantics pending M1b |
| KH-006–KH-008 | migrated to `ST-D01`, `ST-D02`, and `ST-D08` |
| KH-009 | migrated to `ST-D14` |
| KH-010–KH-014 | pending M1b; KH-010 is a mandatory anti-leakage rule |
| KH-015–KH-018 | migrated to `ST-D07`/`ST-D13` and M1a evidence |
| KH-019 | pending reproduction, then M1b evidence |
| KH-020 | prerequisite migrated to M1a; noisy-geometry case remains pending |
| KH-021–KH-024 | migrated to `ST-D08`/`ST-D13` and the M1a scope |
| KH-025–KH-026 | resolved by `PD-Q02`; KH-025 evidence corrected below |

---

## KH-001 — CADENCE v1's controller focus is RL

- **Type:** decision
- **Statement:** CADENCE v1 is a deliberate RL revisit of the original university thesis project. `PD-D02` still sequences foundation and validation controllers before RL at M4–M6, with Max-Pressure later at M8.
- **Supporting reasoning or source:** Conversation decision after the broad research phase. The user wants v1 to “แก้มือ” with RL first, then later plug in/compare Max-Pressure, MPC, hybrid, or other controllers without changing the SUMO foundation. Existing research establishes controller agnosticism, but does not fully capture this **v1 sequencing decision**.
- **Confidence:** high
- **Resolved by:** `PD-D01` and `PD-D02`

---

## KH-002 — `MovementId` must not mean SUMO TLS `linkIndex`

- **Type:** correction
- **Statement:** The current architecture documents use `MovementState` without a sufficiently precise identity definition. `MovementId` should be a CADENCE traffic-engineering/domain grouping, **not** a direct alias for a SUMO TLS `linkIndex`.
- **Supporting reasoning or source:** SUMO controls lane-to-lane **connections/links**, and a signal/TLS index may control more than one connection when signal grouping is used. SUMO documentation explicitly describes a one-to-many relationship between a signal index and controlled links. Therefore `linkIndex` is a SUMO signal-addressing concept, not a stable domain definition of a traffic movement. Source: SUMO Traffic Lights documentation, `https://eclipse.dev/sumo/docs/Simulation/Traffic_Lights.html`.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` and `CADENCE_SUMO_SIMULATION_RESEARCH.md`

---

## KH-003 — Add a lower-level connection/control identity beneath `MovementId`

- **Type:** decision
- **Statement:** Introduce a SUMO-facing identity such as `ConnectionId` / `ControlledLinkId` for the lowest stable control grain, representing the lane-to-lane controlled connection plus its TLS addressing metadata. Derive versioned domain movements from one or more of these connections.
- **Supporting reasoning or source:** This cleanly separates SUMO addressing from traffic-engineering interpretation. Proposed shape from the conversation:
  ```text
  SUMO lane-to-lane connection
          ↓
  ConnectionId / ControlledLinkId
          ↓
  MovementDefinition:v1
          ↓
  MovementId / MovementState
  ```
  This avoids embedding a versionless interpretation into the storage layer.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`

---

## KH-004 — `(from_edge, to_edge)` is a grouping key, not a universal movement identity

- **Type:** clarification
- **Statement:** A `(from_edge, to_edge)` pair may be a useful traffic-movement grouping rule, especially for Original Max-Pressure-like semantics, but it should not be the universal low-level identity.
- **Supporting reasoning or source:** Real OSM-derived networks can contain multiple receiving lanes, internal connections, lane-specific restrictions, slip lanes, and unusual geometry. Collapsing directly to edge pairs can hide physically/control-distinct connections. Conversation design review after inspecting S0 shared lanes.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-005 — Movement definition and movement-queue semantics must be versioned separately

- **Type:** decision
- **Statement:** Do not make `MovementState.queue_count_veh` an implicit side effect of movement grouping. Maintain separate semantics such as:
  - `movement_definition_v1`: what connections belong to the same movement;
  - a separate movement-queue estimator/metric version: how queue is allocated to that movement.
- **Supporting reasoning or source:** Shared lanes make movement identity and movement queue estimation different problems. A lane can serve multiple turn movements, so the lane queue cannot be uniquely assigned to movements from aggregate lane count alone. This was identified in Max-Pressure research, but the **separate versioned registry decision** arose during implementation design.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-006 — Exact per-vehicle intent is privileged runtime ground truth, not canonical controller state

- **Type:** decision
- **Statement:** Split runtime traffic information into two typed state spaces:
  ```text
  CanonicalTrafficState
  - controller-accessible
  - no exact per-vehicle future route/turn intent

  SimulationGroundTruth
  - privileged simulator truth
  - exact route/next-edge/intent where available
  - validation/debug/oracle use only
  ```
- **Supporting reasoning or source:** Keeping exact intent inside canonical state and relying only on adapter discipline creates an architectural footgun. Removing it entirely from runtime prevents live validation/oracle experiments. Two typed streams retain validation capability while preventing accidental controller access.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`

---

## KH-007 — Ground-truth access must be enforced by types **and** dependency rules

- **Type:** clarification
- **Statement:** An import ban alone is insufficient. The intended enforcement mechanism is a combination of:
  1. dependency/import restrictions preventing normal modules from importing `simulation.ground_truth`, and
  2. strict typing (`mypy --strict` or equivalent) so observation/controller adapters cannot accept untyped privileged objects passed by a runner that happens to hold both state streams.
- **Supporting reasoning or source:** The runner/extractor may legitimately construct both canonical and privileged state at the same simulation step. A pure import rule would not stop it from passing ground truth into a loosely typed adapter. Strict typed interfaces make the prohibited path testable. Conversation implementation review.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`

---

## KH-008 — Ground-truth leakage must also be prevented at the artifact/dataset boundary

- **Type:** decision
- **Statement:** Separate normal and privileged run artifacts structurally, e.g.:
  ```text
  run_dir/
    manifest.json
    events.parquet
    state/
      lane.parquet
      intersection.parquet
    ground_truth/
      lane_turn.parquet
      tripinfo.parquet   # if treated as privileged in the implemented schema
  ```
  Observation/dataset code used for normal controllers must not reference/read the `ground_truth/` subtree.
- **Supporting reasoning or source:** Import/type restrictions do not prevent a future RL dataset loader from directly reading privileged Parquet files. File-level separation gives the same architectural boundary to offline pipelines. Conversation implementation review.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`

---

## KH-009 — Canonical state provides controller parity, not deployment realism

- **Type:** clarification
- **Statement:** `CanonicalTrafficState` should be described as the **Study-1 parity layer** between CADENCE controllers, not as a claim of sensor realism. Exact whole-lane halting counts, queue length, etc. can still be more informative than a real detector installation.
- **Supporting reasoning or source:** This distinction is important for scientific claims and advisor review. A controller can be fair relative to another CADENCE controller while all compared controllers still receive simulator-rich observations. Real deployment realism belongs in a future `SensorRealisticAdapter`/observation-fidelity study.
- **Confidence:** high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` and `CADENCE_RL_TSC_RESEARCH.md`

---

## KH-010 — Normal turn-ratio estimation must not read scenario demand definitions

- **Type:** decision
- **Statement:** Reject scenario-demand proportions as an input to the normal runtime turn-ratio estimator. Scenario demand files are privileged generation truth and would leak non-stationary/generalization changes into the controller immediately.
- **Supporting reasoning or source:** If demand changes from 70/30 to 30/70 at time T, an estimator reading the demand specification learns the change at exactly T without observing traffic. This would falsely improve Max-Pressure or RL generalization results. Conversation decision on turn-ratio source alternatives.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-011 — Preferred turn-ratio source is historical observed movement service, with an explicit prior

- **Type:** decision
- **Statement:** The normal estimator should derive turn ratios from historical observed movement events, using a configurable sliding window. A configured static ratio may exist only as an explicit **prior/cold-start fallback**, not as hidden truth.
- **Supporting reasoning or source:** This preserves the distinction between “past observed behavior” and “future per-vehicle intent.” It also naturally exposes the controller to estimation lag when demand changes. The earlier candidate name `turn_ratio_observed_window_300s_v1` was refined: algorithm version and parameter should be separate, e.g. `turn_ratio_*_v1` plus `window_seconds=300` in manifest/config.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-012 — Correction: naive discharged-turn-ratio estimation creates a self-reinforcing starvation loop

- **Type:** correction
- **Statement:** Treat lack of discharge as evidence only when the movement had a real service/observation opportunity. **No service opportunity ≠ no demand.** A naive estimator that divides all movements by total observed discharged counts can drive an unserved movement's estimated share toward zero, causing the controller to deprioritize it further.
- **Supporting reasoning or source:** Closed-loop reasoning found during implementation review:
  ```text
  movement receives no green
      → no discharged samples
      → estimated share falls
      → Max-Pressure priority falls
      → even less green
  ```
  A pseudo-count prior alone does not prevent this because observations on other movements continually increase the denominator.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-013 — Minimum estimator invariant: unobserved/unserved movement retains prior support

- **Type:** decision
- **Statement:** The turn-ratio estimator must preserve prior support for a movement that received no service opportunity during the relevant evidence interval. At minimum, starvation of service must not mathematically erase the movement from the estimated demand distribution.
- **Supporting reasoning or source:** Proposed directly as a testable invariant: intentionally deny green to one movement for a run/window and assert that its estimated ratio does not fall below its configured prior solely because other movements accumulated samples. Future refinement may weight evidence by **service exposure** rather than a simple green/no-green boolean.
- **Confidence:** high for the invariant; medium for the exact estimator formula
- **Suggested destination:** M1b specification

---

## KH-014 — Open estimator limitation: served discharge still does not identify latent arrival demand under saturation

- **Type:** open question
- **Statement:** Even if a movement receives green, discharged traffic can be capacity-limited. Therefore observed served movement proportions can underestimate latent arrival intentions under oversaturation. The initial estimator should not be described as an exact arrival turn-ratio estimator.
- **Supporting reasoning or source:** Example reasoning: latent demand may be 20 vehicles while service capacity permits only 8 to discharge. This is not solvable from discharge observations alone without additional sensing/model assumptions. A more honest semantic name would emphasize **service-observed/discharged** turning proportions.
- **Confidence:** high
- **Suggested destination:** M1b specification

---

## KH-015 — `s0_turning/v1` should exist as a separate enduring scenario, not `s0_single_intersection/v2`

- **Type:** decision
- **Statement:** Add a distinct deterministic scenario `s0_turning/v1` exercising turning and shared lanes. Keep `s0_single_intersection/v1` as the minimal straight-only fixture; do not use versioning to imply that one replaces the other.
- **Supporting reasoning or source:** The two fixtures serve different long-lived purposes. The straight-only fixture remains useful for smoke/regression checks; the turning fixture is needed for movement extraction, shared-lane semantics, turn-ratio estimation, and exact-vs-estimated validation. Using `v2` would misleadingly imply supersession.
- **Confidence:** high
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` and/or a new `CADENCE_SCENARIO_FIXTURES.md`

---

## KH-016 — Scratchpad evidence supporting `s0_turning/v1`

- **Type:** fact
- **Statement:** A scratchpad run of the proposed asymmetric turning fixture produced:
  - 315 departed / 315 arrived;
  - drain completed at simulation time 558 s (before 600 s cap);
  - 0 teleports;
  - 0 collisions;
  - all 16/16 TLS controlled links exercised (straight-only S0 exercised 8/16);
  - peak total halting count 18, maximum 6 on a lane.
  Reported generated approach totals/turn shares were:
  - `top0A0`: 90 vehicles — r 11.1%, s 66.7%, l 22.2%;
  - `right0A0`: 82 — r 36.6%, s 48.8%, l 14.6%;
  - `bottom0A0`: 71 — r 21.1%, s 45.1%, l 33.8%;
  - `left0A0`: 72 — r 55.6%, s 33.3%, l 11.1%.
- **Supporting reasoning or source:** Developer-agent scratchpad run reported by the user in this conversation. This is implementation evidence, not an independently rerun result by this research agent.
- **Confidence:** high that this was the reported result; medium until reproduced in the repository test suite
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` or `CADENCE_SCENARIO_FIXTURES.md`

---

## KH-017 — Turning fixture should be deterministic and asymmetric

- **Type:** decision
- **Statement:** The small turning fixture should deliberately use asymmetric turn patterns across approaches rather than a symmetric/random mix.
- **Supporting reasoning or source:** Asymmetric test data exposes identity/mapping errors that symmetric traffic can hide. It also provides stable expected ground truth for estimator validation. The scratchpad fixture above demonstrated this property.
- **Confidence:** high
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` or `CADENCE_SCENARIO_FIXTURES.md`

---

## KH-018 — Connection traversal identity must not be inferred from via-lane presence

- **Type:** correction
- **Statement:** For exact completed movement detection, use the actual incoming→outgoing lane/connection identity (e.g. `(incoming_lane, outgoing_lane)` / `ConnectionId`), not merely “vehicle entered a via/internal lane.”
- **Supporting reasoning or source:** In the turning scratchpad run, via-lane counting produced 322 observations from 315 vehicles (2.2% overcount), compared with only a 1-vehicle/0.3% discrepancy in the straight-only fixture. Turning/lane-changing inside the junction makes via-lane presence non-unique. This empirically supports connection-pair identity.
- **Confidence:** high for the observed fixture; high for the architectural correction
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` and `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`

---

## KH-019 — Link-level observations are not sufficient substitutes for movement-level demand estimates

- **Type:** fact
- **Statement:** In the scratchpad turning run, two TLS links belonging to the same straight traffic movement carried 30 and 2 vehicles respectively, while their aggregate matched the intended movement total of 32. This is an example of why traffic-demand estimation should not treat individual TLS link indices as independent movements.
- **Supporting reasoning or source:** Developer-agent scratchpad result reported by the user. It reinforces KH-002/KH-003: TLS addressing grain and domain movement grain are different.
- **Confidence:** high that this was the reported result; medium until reproduced in repository tests
- **Suggested destination:** M1b specification or `CADENCE_SCENARIO_FIXTURES.md`

---

## KH-020 — `_approach_pairs` is a blocking prerequisite before reusing the network generator for turning fixtures

- **Type:** decision
- **Statement:** Fix `_approach_pairs` before it is reused to generate `s0_turning/v1` or later real-world scenarios.
- **Supporting reasoning or source:** The current helper reportedly (a) divides by `hypot` without guarding a zero-length vector and (b) accepts the best alignment without checking that the winning alignment is sufficiently plausible or unambiguous. This was already warned about in the development direction/spec but was not scheduled. Required tests should include zero-norm geometry, ambiguous pairing, a clear orthogonal cross, and mildly noisy geometry.
- **Confidence:** high based on developer inspection reported in conversation
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` or a scenario-generation/validation research note

---

## KH-021 — Scenario directories should remain self-contained and immutable; duplicate generated network artifacts when appropriate

- **Type:** decision
- **Statement:** Prefer storing a generated network copy inside each immutable scenario directory rather than sharing a mutable/external relative path between scenarios, even when the network is byte-identical. Verify expected equality via network hashes.
- **Supporting reasoning or source:** The generator is the source of truth and already strips generation timestamps for deterministic output. The duplicate network is small (~14 KB in the reported fixture). Self-contained scenario directories preserve manifest/hash semantics and prevent a single external network edit from silently changing multiple historical scenarios.
- **Confidence:** high
- **Suggested destination:** `CADENCE_SUMO_SIMULATION_RESEARCH.md` and architecture/reproducibility documentation

---

## KH-022 — Split M1 into M1a (state foundation) and M1b (metrics/derived semantics)

- **Type:** decision
- **Statement:** Do not implement the entire original M1 basket in one pass. Split it:

  **M1a — Canonical State & Ground-Truth Foundation**
  - canonical state types + extractor;
  - `SimulationGroundTruth` + access-ban tests;
  - `ConnectionId` / `movement_definition_v1`;
  - `state/` vs `ground_truth/` artifact layout;
  - run-outcome manifest changes;
  - `cadence_dirty` policy work already assigned to this basket;
  - validation/sumolib boundary cleanup already assigned to this basket;
  - `_approach_pairs` fix;
  - `s0_turning/v1`.

  **M1b — Metrics & Derived Traffic Semantics**
  - turn-ratio estimator;
  - movement-queue estimator;
  - registry + `config_dependencies`;
  - trip/queue/network/failure metrics;
  - `cadence verify-run`.

- **Supporting reasoning or source:** The M0→M1 process benefited from observing real raw state before freezing abstractions. Movement/metric semantics have already changed after scratchpad data inspection. M1b should therefore be designed against real M1a Parquet artifacts instead of assumed schemas.
- **Confidence:** high
- **Resolved by:** the M1a specification header and scope

---

## KH-023 — M1a must capture evidence needed by M1b without interpreting it yet

- **Type:** decision
- **Statement:** M1a should not implement turn-ratio/movement-queue estimators, but its artifacts must preserve enough evidence to reconstruct and validate them later. Before M1b begins, real artifacts should allow answering:
  1. which incoming lane a vehicle came from;
  2. which outgoing lane/connection it used;
  3. which domain movement that connection maps to;
  4. when a movement had service opportunity;
  5. lane queue/state at that time;
  6. where privileged exact intent resides;
  7. what canonical non-privileged state existed;
  8. how the run terminated (drained/completed/timeout/failure).
- **Supporting reasoning or source:** This establishes a deliberate boundary: **M1a captures evidence; M1b interprets evidence.** It minimizes schema backtracking when metric semantics are defined.
- **Confidence:** high
- **Resolved by:** `ST-D08` and the M1a artifact schema

---

## KH-024 — Defer documentation section-content hashing from the traffic-state critical path

- **Type:** decision
- **Statement:** Defer the proposed PD-D06 Layer-2 / section-content hashing work rather than including it in M1a or M1b.
- **Supporting reasoning or source:** It is documentation/tooling integrity work and is not required to validate traffic state, movement semantics, metrics, or the RL environment. Revisit when research/document synchronization becomes a demonstrated maintenance problem.
- **Confidence:** high
- **Resolved by:** the M1a specification's out-of-scope section

---

## KH-025 — macOS GUI is not a development prerequisite; current macOS SUMO GUI path depends on XQuartz

- **Type:** correction
- **Statement:** On macOS, current SUMO documentation explicitly requires XQuartz for `sumo-gui` and/or `netedit`. On macOS Tahoe 26, XQuartz has known rendering/refresh compatibility issues. CADENCE M0/M1 should remain fully capable of progressing headlessly; GUI availability must not be an acceptance dependency.
- **Supporting reasoning or source:** SUMO installation docs require XQuartz for `sumo-gui`/`netedit`. The earlier issue #438 reading is stale: it closed 2026-05-18. Issue #497, filed against macOS 26.5.2, closed 2026-08-10 after resolution in XQuartz 2.8.7_beta2. Current project guidance is recorded under `PD-Q02` in `docs/DIRECTION.md`.
- **Confidence:** high
- **Resolved by:** `PD-Q02`

---

## KH-026 — If a CADENCE viewer is built later, it should consume CADENCE trace/state/event data, not become coupled to raw SUMO FCD XML

- **Type:** decision
- **Statement:** Treat visualization as an optional consumer of the simulation/event pipeline. A future cross-platform viewer may replay vehicle/TLS/queue/spillback data, but the long-term architecture should prefer CADENCE-owned trace/state/event formats over direct dependence on `fcd.xml`.
- **Supporting reasoning or source:** Headless SUMO is sufficient for simulator validation. A viewer is useful later for M7/demo/debugging, but coupling it directly to SUMO FCD would bypass the canonical architecture and create another SUMO-specific interface. Conversation decision after investigating XQuartz/Tahoe.
- **Confidence:** medium-high
- **Suggested destination file in `research/`:** `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` or a future visualization/design note

---

# Unresolved Questions to Carry Forward

These are intentionally not resolved in this handoff:

1. **Exact service-exposure model for turn-ratio evidence.** The invariant “no service ≠ no demand” is accepted, but whether v1 uses a boolean served/not-served gate, effective-green duration, discharge opportunity, or another exposure-weighted estimator remains open.
2. **Final semantic name/formula for the observed turn-ratio estimator.** It should not imply latent arrival intent if it is based on discharged/served movements.
3. **Final movement-queue estimator under shared lanes.** Proportional splitting from turn-ratio estimates is a candidate, but FIFO-aware/lane-structured alternatives remain possible.
4. **What exact artifacts belong in privileged `ground_truth/`.** The boundary principle is decided; individual files such as `tripinfo.parquet` should be classified based on what information they expose in the implemented schema rather than by filename alone.

---

# Checklist — Research Files That Should Be Updated

- [ ] `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`
  - define `ConnectionId` / `ControlledLinkId` vs `MovementId`;
  - split `CanonicalTrafficState` and `SimulationGroundTruth`;
  - document type/import/artifact leakage boundaries;
  - clarify parity vs sensor realism;
  - add artifact-access and future viewer boundary notes.

- [ ] M1b specification
  - separate movement-definition vs movement-queue semantics;
  - prohibit scenario-demand turn-ratio leakage;
  - document service-observed estimator semantics;
  - add the closed-loop starvation correction and prior-support invariant;
  - document saturation-limited discharge bias;
  - add reported link-vs-movement evidence once reproduced.

- [ ] `CADENCE_SUMO_SIMULATION_RESEARCH.md`
  - clarify TLS signal index vs lane-to-lane connection semantics;
  - add `s0_turning/v1` fixture purpose and validation evidence after repository reproduction;
  - record `(incoming_lane, outgoing_lane)` / `ConnectionId` traversal identity;
  - add `_approach_pairs` prerequisite/validation requirements;
  - document self-contained immutable scenario artifact decision;
  - update macOS GUI/XQuartz/Tahoe constraint.

- [ ] `CADENCE_RL_TSC_RESEARCH.md`
  - clarify that canonical simulator state is a parity layer, not necessarily sensor-realistic;
  - reinforce privileged-ground-truth exclusion from training datasets.

- [x] M1a specification and `docs/DIRECTION.md`
  - record v1 RL-first sequencing;
  - record M1a/M1b implementation-research gate;
  - record PD-D06 Layer-2 content hashing as deferred/non-critical.

- [ ] Consider creating `CADENCE_SCENARIO_FIXTURES.md`
  - centralize `s0_single_intersection/v1`, `s0_turning/v1`, intended purpose, deterministic demand patterns, expected invariants, and reproducibility/hash rules.

---

**Handoff rule for Codex research agent:** Treat this file as a temporary delta ledger. When an item is incorporated into its suggested `research/` destination and verified, remove or mark it migrated here rather than allowing two competing sources of truth.
