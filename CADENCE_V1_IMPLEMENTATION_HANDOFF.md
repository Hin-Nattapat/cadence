# CADENCE v1 — Implementation Handoff

**Project Codename:** CADENCE  
**Formal Title:** Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks  
**Document Type:** Development Handoff / Implementation Plan  
**Status:** Ready for Development Planning  
**Checkpoint Date:** 2026-08-22

---

# 1. Purpose

This document is the handoff from research/design into implementation.

CADENCE v1 will deliberately implement **Reinforcement Learning first** as a modern rebuild/revisit of the original university thesis project.

However:

> **The codebase must remain controller-agnostic.**

Future controller families such as Max-Pressure, MPC, hybrid control, MARL, or other methods must be able to plug into the same validated simulation foundation.

---

# 2. v1 Product / Research Goal

CADENCE v1 should prove that the project can:

1. construct and validate a trustworthy SUMO traffic environment,
2. expose traffic state through a stable domain model,
3. control legal signal decisions through a reusable controller contract,
4. train and evaluate RL controllers reproducibly,
5. run scientifically fair experiments,
6. support later non-RL controllers without changing simulation semantics.

The v1 goal is **not** to solve city-scale traffic optimization.

---

# 3. Non-Goals for v1

Do not block v1 on:

- city-scale MARL,
- Graph Neural Networks,
- Model-Based RL,
- LLM-based real-time control,
- advanced routing + signal co-optimization,
- full stochastic MPC,
- perimeter control,
- full Thailand traffic calibration,
- every Max-Pressure variant,
- production traffic-signal deployment.

These remain future research/engineering tracks.

---

# 4. Core Architecture

```text
┌───────────────────────────────────────────────────────┐
│                  EXPERIMENT RUNNER                    │
│ scenario × controller × seed × traffic regime        │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│                 SUMO SIMULATION CORE                  │
│ lifecycle | TraCI | time | events | raw state        │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│               CANONICAL TRAFFIC STATE                │
│ lane | movement | intersection | network             │
└───────────────┬───────────────────┬───────────────────┘
                │                   │
                ▼                   ▼
┌────────────────────────┐  ┌───────────────────────────┐
│ OBSERVATION ADAPTERS   │  │ METRICS / EVENT PIPELINE │
│ RL first in v1         │  │ controller-independent    │
└───────────────┬────────┘  └───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────┐
│                 CONTROLLER CONTRACT                   │
│ RL now | MP/MPC/Hybrid later                         │
└─────────────────────────┬─────────────────────────────┘
                          │ ControllerAction
                          ▼
┌───────────────────────────────────────────────────────┐
│            SIGNAL SAFETY / CONSTRAINT LAYER           │
│ phase legality | min green | yellow | clearance      │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
                         SUMO
```

---

# 5. Architectural Principles

## AP-01 — Environment First

> Do not optimize an environment we do not trust.

Network, demand, routing, vehicle behavior, signal logic, telemetry, and failure handling must be validated before performance claims.

## AP-02 — Controller Agnostic

Simulation code must not depend on:

- PPO,
- DQN,
- replay buffers,
- PyTorch policy objects,
- RL reward logic.

RL is one adapter/controller family.

## AP-03 — No Direct TraCI in Controllers

Controllers should consume CADENCE traffic-domain objects.

They should not directly call:

```text
traci.lane.*
traci.edge.*
traci.trafficlight.*
```

except through dedicated simulator infrastructure.

## AP-04 — Common Signal Safety Layer

Controllers request traffic-control actions.

The environment owns legal transitions.

## AP-05 — Evaluation Is Independent

RL reward is not the experiment KPI pipeline.

## AP-06 — Reproducibility

Every experiment must be reproducible from explicit metadata.

---

# 6. Proposed Repository Structure

Conceptual starting point:

```text
cadence/
├── simulation/
│   ├── sumo/
│   │   ├── client
│   │   ├── lifecycle
│   │   └── raw_state
│   ├── scenario/
│   ├── events/
│   └── validation/
│
├── traffic/
│   ├── state/
│   ├── movements/
│   ├── metrics/
│   └── topology/
│
├── control/
│   ├── contracts/
│   ├── safety/
│   ├── actions/
│   └── rl/
│
├── adapters/
│   └── gym/
│
├── experiments/
│   ├── runner/
│   ├── configs/
│   └── reports/
│
├── scenarios/
├── tests/
└── research/
```

Exact folder names may change during implementation planning.

The boundaries should not.

---

# 7. Core Domain Objects

## LaneState

Candidate fields:

```text
lane_id
length_m
vehicle_count
halting_count
mean_speed_mps
occupancy
queue_length_m
storage_capacity_estimate
available_storage_ratio
```

## MovementState

Candidate fields:

```text
movement_id
from_lane/link
to_lane/link
queue_count
turn_ratio
service/saturation estimate
downstream occupancy
downstream available storage
```

Not all fields must be implemented in M1.

## IntersectionState

```text
intersection_id
current_phase_id
phase_elapsed_s
legal_phase_ids
incoming lanes/movements
outgoing lanes/links
```

## NetworkState

```text
simulation_time
active_vehicle_count
arrived_vehicle_count
pending/insertion count
teleports
```

---

# 8. Controller Contract

The semantic contract should resemble:

```python
class TrafficController:
    def initialize(self, context) -> None:
        ...

    def reset(self, episode_context) -> None:
        ...

    def decide(self, observation) -> ControllerAction:
        ...

    def on_transition(self, transition) -> None:
        ...

    def diagnostics(self) -> ControllerDiagnostics:
        ...

    def close(self) -> None:
        ...
```

The implementation language/signatures may evolve.

The semantics should remain stable.

---

# 9. Controller Actions

Prefer domain actions such as:

```text
KeepPhase
RequestPhase(phase_id)
RequestNextPhase
ExtendPhase(seconds)
NoOp
```

For v1 RL, the simplest action space should probably be:

```text
Select / request a legal green phase
```

or:

```text
Keep / Switch
```

The exact action design is an implementation-stage decision and should be validated on the first scenario.

---

# 10. Signal Safety Layer

Must own:

- legal phase validation,
- conflicting movement prevention,
- minimum green,
- yellow transitions,
- optional all-red/clearance,
- intermediate transition state,
- invalid-action logging.

RL must not learn these safety constraints through reward.

---

# 11. RL Environment Boundary

Preferred architecture:

```text
CADENCE Simulation Core
        ↓
Canonical Traffic State
        ↓
RL Observation Adapter
        ↓
Gymnasium-style Environment
        ↓
RL Algorithm
```

Gymnasium is an adapter, not the internal architecture.

Future MARL may use PettingZoo or another adapter.

---

# 12. RL Observation v1

Do not over-design before the first validated environment.

Initial candidate:

```text
current phase
phase elapsed / minimum-green state
incoming lane density/count
incoming queue/halting
downstream occupancy or available-storage signal
```

All features must have:

- clear units,
- normalization definition,
- data source,
- observation fidelity declaration.

---

# 13. RL Reward v1

Do not finalize reward before state/metric validation.

Candidate starting rewards:

```text
Δ total waiting
```

or:

```text
Δ time loss
```

Potential later addition:

```text
spillback penalty
switch penalty
fairness/starvation component
```

The reward must remain separate from experiment KPIs.

---

# 14. RL Algorithms for v1

## DQN

Use as:

> discrete-action reference RL baseline.

Useful for connecting with established traffic-signal RL literature.

## PPO

Use as:

> primary generic RL baseline.

Reasons:

- stable general baseline,
- supports discrete actions,
- easy future extension,
- not highly traffic-specific.

### v1 Implementation Priority

Recommended:

```text
PPO first
DQN second/reference
```

if implementation effort must be minimized.

Both should share the same environment contract.

---

# 15. Scenario Progression

## Scenario S0 — Deterministic Synthetic Intersection

Purpose:

- integration testing,
- action/safety validation,
- metric verification.

Not for final research claims.

## Scenario S1 — Controlled Single Intersection

Purpose:

- RL training sanity,
- fixed vs RL comparison,
- behavior diagnostics.

## Scenario S2 — Real-World Single Intersection

OSM/SUMO validated network.

Purpose:

- first meaningful v1 RL result.

## Scenario S3 — Small Corridor

Approximately 3–5 traffic signals.

Purpose:

- downstream capacity,
- spillback,
- simple network awareness.

MARL is not required initially.

A centralized/shared RL formulation may be sufficient for first experiments.

---

# 16. Traffic Regimes

At minimum define:

```text
A — undersaturated
B — near saturation
C — oversaturated
D — spillback stress
```

These should be parameterized scenario variants rather than separate ad-hoc projects.

---

# 17. Metrics for v1

## Required

- travel time,
- time loss,
- waiting time,
- throughput / arrived trips,
- completion rate,
- unfinished trips,
- queue count,
- queue length in meters,
- teleport count and reason.

## Strongly Recommended

- P95 travel time,
- P95 waiting,
- max waiting,
- per-approach metrics,
- depart/insertion delay,
- spillback event count/duration.

---

# 18. Reproducibility Manifest

Each experiment run should persist:

```text
CADENCE git commit
SUMO version
scenario ID/version
network hash
demand hash
controller name/version
controller config
observation adapter version
reward version
metric definitions version
seed
simulation time step
decision interval
vehicle behavior config
```

---

# 19. Test Strategy

Testing should be treated as a primary engineering concern.

## Unit Tests

Examples:

- storage-capacity calculations,
- queue normalization,
- action validation,
- phase-transition generation,
- metric aggregation.

## Contract Tests

Every external controller must pass:

```text
initialize
reset
valid decide result
timeout behavior
close
```

## SUMO Integration Tests

Examples:

### Network Smoke Test
Simulation starts and progresses.

### Queue Discharge Test
Known queue under green discharges within expected bounds.

### Downstream Storage Test
Finite downstream link can reach congestion/spillback.

### Signal Transition Test
Requested phase produces valid yellow/clearance sequence.

### Reproducibility Test
Same seed/config produces matching expected outputs.

---

# 20. Development Milestones

# M0 — Simulation Harness

Deliverables:

- deterministic SUMO launch/shutdown,
- TraCI wrapper,
- scenario config loader,
- raw state/event capture,
- software/version logging.

Acceptance:

- run the same scenario repeatedly,
- no controller intelligence required,
- deterministic behavior within documented SUMO constraints.

---

# M1 — Canonical State + Metrics

Deliverables:

- LaneState,
- IntersectionState,
- basic NetworkState,
- trip/queue metrics,
- teleport capture.

Acceptance:

- metrics verified against known/simple scenarios,
- no controller-specific state logic in simulation layer.

---

# M2 — Signal Safety + Controller Contract

Deliverables:

- TrafficController interface,
- ControllerAction types,
- signal legality metadata,
- safety/transition executor,
- dummy/manual controller.

Acceptance:

- external code can request signal changes without calling TraCI directly,
- illegal requests cannot produce unsafe signal states.

---

# M3 — RL Adapter

Deliverables:

- Gymnasium environment adapter,
- observation builder v1,
- action mapping,
- reward v1,
- episode/reset semantics.

Acceptance:

- random agent can run complete episodes,
- environment passes Gymnasium compatibility checks where applicable,
- no RL-library dependency in simulation core.

---

# M4 — PPO / DQN Baselines

Deliverables:

- PPO training pipeline,
- evaluation pipeline,
- checkpoint save/load,
- optional DQN reference implementation.

Acceptance:

- frozen policy evaluates through common controller/evaluation contract,
- training and evaluation scenario sets are separate,
- multiple seeds supported.

---

# M5 — Single-Intersection Experiments

Compare:

```text
Fixed-Time
vs
RL
```

Optional early:

```text
SUMO Actuated
```

Purpose:

- verify that RL actually learns a meaningful policy,
- diagnose reward/action/state problems.

No major superiority claim yet.

---

# M6 — Real-World Intersection

Deliverables:

- OSM-derived validated intersection,
- explicit lane connections,
- legal TLS definition,
- controlled demand variants.

Compare at least:

- tuned fixed,
- actuated,
- RL.

---

# M7 — Corridor / Network-Aware v1

3–5 signals.

Focus:

- downstream occupancy/storage,
- spillback,
- network metrics.

This is the first point where the original CADENCE network-aware thesis becomes fully visible.

---

# 21. Baselines Deferred but Architecturally Supported

Not required before first RL v1:

- Original Max-Pressure,
- capacity-aware Max-Pressure,
- MPC.

However:

> Their future implementation must not require simulation-core redesign.

After v1 RL is operational, these become the preferred comparative baseline expansion.

---

# 22. Outstanding Decisions Before Coding

Only a small set of decisions should be resolved before or during M0–M3.

## Must Decide Early

### DEV-Q01 — Primary implementation language / package structure

Likely Python because:

- SUMO/TraCI ecosystem,
- Gymnasium,
- RL libraries.

Still document final toolchain.

### DEV-Q02 — SUMO version pin

Pin a known stable version and record it.

### DEV-Q03 — RL library

Candidate:

- Stable-Baselines3 for PPO/DQN,
- custom PyTorch only if necessary.

Prefer established library for v1 to avoid conflating RL implementation bugs with research.

### DEV-Q04 — Config format

Candidate:

- YAML,
- TOML,
- typed Python config.

Choose one reproducible/configurable approach.

### DEV-Q05 — Canonical state versioning strategy

Simple version identifiers are enough initially.

---

# 23. Decisions That Can Wait Until M3/M5

Do not block M0 on:

- final reward,
- final neural architecture,
- hyperparameters,
- final observation normalization,
- exact decision interval,
- DQN vs PPO superiority,
- MARL,
- GNN.

These should be experiment-driven.

---

# 24. Research Still Needed?

## Broad Research

**No.**

The broad pre-implementation landscape is sufficiently complete.

Do not continue open-ended literature review before development.

## Targeted Research Still Expected

Research should now be triggered by concrete development/experiment questions.

Examples:

### During M0–M1
- exact SUMO API semantics,
- detector/queue measurement definitions,
- OSM preprocessing issue,
- teleport/failure interpretation.

### During M3
- Gymnasium/SB3 integration details,
- observation normalization practice,
- episode reset semantics.

### During M5
- reward failure,
- RL convergence problem,
- baseline tuning.

### During M7
- corridor coordination,
- whether MARL/GNN is justified,
- whether downstream storage representation is sufficient.

This is **question-driven research**, not another landscape phase.

---

# 25. Recommended Development Process

Because the implementation will be handed to a coding agent/workflow:

1. read this handoff,
2. read `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md`,
3. read SUMO research checkpoint,
4. produce an implementation plan for M0–M2,
5. review boundaries/contracts before coding,
6. implement milestone-by-milestone,
7. require tests and acceptance evidence per milestone,
8. do not jump directly to RL training.

The first coding goal is:

> **A trustworthy simulator + controller boundary, not a neural network.**

---

# 26. Suggested First Development Ticket

## Ticket: CADENCE M0 — Deterministic SUMO Simulation Harness

### Goal

Create the minimum production-quality infrastructure for running a versioned CADENCE SUMO scenario reproducibly.

### Required

- scenario config,
- SUMO process lifecycle,
- TraCI connection wrapper,
- deterministic seed wiring,
- simulation stepping,
- event/raw-state capture,
- clean shutdown,
- version metadata,
- smoke/integration tests.

### Explicitly Excluded

- RL,
- reward,
- neural network,
- Max-Pressure,
- MPC,
- advanced metrics.

### Done When

A test command can:

```text
load scenario
start SUMO
run N seconds
capture state/events
stop cleanly
repeat reproducibly
```

with automated tests.

---

# 27. Development Gate

CADENCE is ready to enter development planning.

The pre-development research gate is passed.

The correct next step is:

```text
M0–M2 implementation plan
        ↓
code
        ↓
validated simulation foundation
        ↓
RL environment
        ↓
PPO/DQN
```

---

# 28. Final Handoff Statement

CADENCE v1 intentionally returns to Reinforcement Learning first.

This choice is a project-direction decision, not an architectural limitation.

The engineering goal is therefore:

> **Build an excellent traffic simulation and experiment platform, then plug RL into it first.**

If future experiments show that Max-Pressure, MPC, a hybrid controller, or a new method is better, the codebase should be ready to accept that result rather than resist it.
