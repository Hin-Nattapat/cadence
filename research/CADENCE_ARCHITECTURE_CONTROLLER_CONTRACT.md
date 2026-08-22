# CADENCE — Architecture Principles and Controller Contract

**Project Codename:** CADENCE  
**Document Type:** Pre-Implementation Architecture Specification  
**Status:** Architecture Baseline for Development  
**Checkpoint Date:** 2026-08-22

---

# 1. Architectural Positioning

CADENCE should be built as:

> **A traffic-control experimentation platform with a validated SUMO-based simulation core and pluggable controller implementations.**

It should **not** be built as:

> An RL codebase wrapped around SUMO.

This allows the project to evolve toward:

- Fixed-Time,
- Actuated,
- Max-Pressure,
- capacity-aware pressure control,
- MPC,
- RL,
- MARL,
- hybrid control,
- future algorithms.

---

# 2. Primary Architecture Principles

## AP-01 — Environment First

> **Do not optimize an environment we do not trust.**

Network, demand, driving behavior, routing, signal plans, metrics, and failure detection must be validated before algorithm claims.

## AP-02 — Controller Agnostic

The simulation core must have no dependency on RL-specific concepts such as:

- neural networks,
- replay buffers,
- PPO,
- DQN,
- reward optimizers.

## AP-03 — Domain API over SUMO API

> **The simulator knows SUMO; controllers know traffic-control concepts.**

Controllers should not directly call `traci.lane.*` or manipulate raw SUMO traffic-light strings.

## AP-04 — Common Safety Layer

Every external adaptive controller uses the same legal signal-transition layer wherever possible.

## AP-05 — Objective/Evaluation Separation

Controller reward/cost/objective is private to the controller.

Experiment KPIs are calculated independently.

## AP-06 — Reproducibility by Construction

Scenario, seed, network, demand, controller config, simulator config, and software versions must be explicit experiment metadata.

---

# 3. High-Level Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    EXPERIMENT RUNNER                    │
│ scenario / seeds / controller matrix / repetitions      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   SIMULATION CORE                       │
│ SUMO lifecycle | time | TraCI | events | raw state      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              CANONICAL TRAFFIC STATE                    │
│ lanes | movements | links | intersections | network     │
└──────────────┬────────────────────────────┬─────────────┘
               │                            │
               ▼                            ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│ OBSERVATION / MODEL      │   │ METRICS / EVENTS         │
│ ADAPTERS                 │   │ independent evaluation   │
└──────────────┬───────────┘   └──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│                  CONTROLLER API                         │
│ Fixed | Actuated | MP | MPC | RL | MARL | Hybrid       │
└───────────────────────────┬─────────────────────────────┘
                            │ ControllerAction
                            ▼
┌─────────────────────────────────────────────────────────┐
│            SIGNAL SAFETY / CONSTRAINT LAYER             │
│ legal phase | min/max | yellow | clearance | masks      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
                          SUMO
```

---

# 4. Simulation Core Responsibilities

The simulation core owns:

- starting/stopping SUMO,
- simulation time,
- TraCI connection,
- raw state retrieval,
- scenario lifecycle,
- teleport/event collection,
- vehicle insertion/completion events,
- traffic-light physical state,
- deterministic seed wiring.

It does **not** decide traffic policy.

---

# 5. Scenario Definition

A scenario should be immutable/versioned input describing:

```text
network
traffic demand
routes
vehicle types/behavior
traffic-light definitions
simulation settings
warm-up
evaluation horizon
failure/teleport policy
country/driving side
```

Suggested identity:

```text
scenario_id
scenario_version
network_hash
demand_hash
```

---

# 6. Canonical Traffic State

Controllers should consume canonical domain state rather than direct simulator data.

## LaneState

Candidate fields:

```text
lane_id
length_m
vehicle_count
halting_count
mean_speed
occupancy
queue_length_m
storage_capacity_estimate
available_storage_ratio
```

## MovementState

```text
movement_id
from_lane/link
to_lane/link
queue_count
turn_ratio
service/saturation estimate
downstream occupancy/storage
```

## IntersectionState

```text
intersection_id
current_phase
elapsed_phase_time
legal_phases
incoming movements
outgoing links
blocked movements
```

## NetworkState

```text
time
active vehicles
completed trips
pending/insertion backlog
teleports
network progress
```

Not every controller receives every field.

---

# 7. Observation Adapters

The canonical state is richer than any one controller observation.

Adapters declare:

```text
Canonical State
     ↓
Controller-specific Observation
```

Examples:

### ActuatedAdapter
Detector-like lane presence/gaps.

### OriginalMaxPressureAdapter
Movement queues, turn ratios, service rates.

### CapacityAwarePressureAdapter
Queue + downstream storage/occupancy.

### MPCAdapter
Link accumulation + predicted-demand inputs.

### RLAdapter
Feature tensor/vector.

### SensorRealisticAdapter
Only configured virtual detector information.

---

# 8. Observation Fidelity Metadata

Every adapter declares:

```text
fidelity_level
data_sources
exact_or_estimated
neighbor_scope
route/turn-intention access
```

This supports fair cross-method experiments.

---

# 9. Controller Contract

A conceptual interface:

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

The exact programming language/signature can change during implementation.

The semantic contract should remain stable.

---

# 10. ControllerContext

Initialization metadata may include:

```text
controlled intersection IDs
signal plan metadata
legal actions/phases
network topology view
decision interval
controller configuration
random seed
```

MPC may additionally own an internal prediction model.

RL may additionally own policy/training runtime.

These remain controller-internal.

---

# 11. ControllerObservation

Should be a typed/versioned domain object or controller-specific encoded representation with metadata.

Important:

> The core should not assume every controller consumes a flat numeric tensor.

MP may use structured movements.

MPC may use graph/link state.

RL may use vector/graph tensors.

---

# 12. ControllerAction

Use domain semantics, not algorithm-native integer meaning.

Possible variants:

```text
KeepPhase
RequestPhase(phase_id)
RequestNextPhase
ExtendPhase(duration)
SetGreenSplit(...)
NoOp
```

An RL action index must be translated into one of these domain actions before reaching SUMO.

---

# 13. Why Raw Lamp State Is Forbidden

Do not expose:

```text
"GGrrG..."
```

as the ordinary controller API.

Reasons:

- safety,
- SUMO coupling,
- difficult cross-controller comparison,
- phase semantics become network-file-specific.

Raw state manipulation should remain an internal signal-layer capability.

---

# 14. Signal Safety / Constraint Layer

Responsibilities:

- validate requested action,
- enforce legal phase set,
- apply yellow,
- apply all-red/clearance,
- enforce minimum green,
- optionally enforce maximum green,
- generate intermediate transitions,
- reject/log invalid actions.

The controller asks:

```text
"I want Phase B"
```

The layer decides the legal transition sequence.

---

# 15. Action Masks

For RL/shared policies:

```text
legal_action_mask
```

must originate from the same signal-plan/safety metadata.

This supports heterogeneous intersections without teaching the model illegal phase combinations.

---

# 16. Internal vs External Controllers

CADENCE may support two categories:

### SUMO-Native Controller
Example: native actuated program.

The controller may be configured in SUMO rather than called every decision.

### External Controller Plugin
Examples:

- Max-Pressure,
- MPC,
- RL.

Experiment abstraction should still expose a common controller identity/configuration and KPI pipeline.

---

# 17. Metrics Engine

The metrics engine consumes simulation state/events independently of controller code.

It should produce:

### Trip
- travel time,
- waiting,
- time loss,
- depart delay,
- completion.

### Queue
- counts,
- meters,
- P95/max,
- residual/cycle failure.

### Network
- throughput,
- completion rate,
- unfinished,
- pending insertion,
- network progress.

### Failure
- teleport reason,
- spillback,
- junction blocking,
- gridlock indicators.

### Computational
- controller latency,
- solver/inference timeout.

---

# 18. Derived Metric Registry

Each CADENCE-derived metric must declare:

```text
name
version
definition
units
input fields
aggregation
thresholds
```

Examples:

```text
spillback_event_v1
junction_blocking_v1
cycle_failure_v1
completion_rate_v1
```

This prevents metric semantics changing silently between experiments.

---

# 19. Event Stream

Useful domain events:

```text
VehicleDeparted
VehicleArrived
VehicleTeleport
PhaseRequested
PhaseChanged
SpillbackDetected
JunctionBlocked
ControllerTimeout
SolverInfeasible
EpisodeStarted
EpisodeEnded
```

Events support:

- diagnostics,
- metrics,
- replay/debugging,
- controller attribution.

---

# 20. Experiment Runner

The runner should define a matrix such as:

```text
Scenario × Controller × Seed × Traffic Regime
```

and execute identical evaluation scenarios.

Example:

```text
scenario: corridor_peak_v2
controllers:
  - fixed_tuned_v1
  - sumo_actuated_v1
  - max_pressure_original_v1
  - mpc_storage_v1
  - ppo_v1
seeds: [1,2,3,4,5]
```

---

# 21. Training and Evaluation Separation

Training pipelines should be outside the fundamental simulation API.

```text
Simulation Core
     ↓
Environment Adapter
     ↓
RL Trainer
```

Evaluation later loads a frozen controller/policy through the same controller contract.

This avoids evaluation code depending on training internals.

---

# 22. RL Training Adapter

Possible Gymnasium/PettingZoo-compatible adapter:

```text
Canonical Traffic State
      ↓
RL observation
      ↓
Gym/PettingZoo step
      ↓
ControllerAction
```

CADENCE core should not itself become a Gym environment internally.

Gym is an adapter surface.

---

# 23. MARL Support

Future support should include:

- multiple controller instances,
- shared policy object,
- neighbor topology,
- optional message channel,
- centralized training state provider,
- graph observation builder.

None of these should be mandatory for simple controllers.

---

# 24. MPC Internal Model Boundary

MPC plugin owns:

```text
prediction model
horizon
solver
objective
constraints
demand forecast
```

SUMO does not expose future truth to MPC.

This is necessary for valid model-mismatch experiments.

---

# 25. Timeout/Fallback Contract

Every controller may declare a decision deadline.

If exceeded:

```text
ControllerTimeout
```

then a configured safe fallback executes.

Possible fallback:

- keep current legal phase,
- fallback actuated program,
- previous feasible MPC action.

Fallback behavior must be deterministic and logged.

---

# 26. Controller Diagnostics

Diagnostic object may include:

```text
decision latency
selected action
action score / pressure
predicted cost
RL value/logprob
solver status
fallback used
observation fidelity
```

Diagnostics are for analysis and explainability, not experiment KPI calculation.

---

# 27. Reproducibility Manifest

Each run should persist:

```text
CADENCE version / commit
SUMO version
scenario ID/hash
controller name/version
controller config
seed
simulation settings
observation adapter/version
metric registry/version
start/end time
```

Optional later:

- Python package lock,
- machine/GPU metadata.

---

# 28. Controller Versioning

Controller identity should be explicit:

```text
max_pressure_original:v1
max_pressure_capacity:v1
mpc_storage:v1
rl_ppo:v1
```

Changing observation or action semantics requires a version change.

---

# 29. Failure Attribution

Before blaming a controller, failures should be classified:

```text
NETWORK
DEMAND
ROUTING
VEHICLE
SIGNAL
CONTROLLER
INFRASTRUCTURE / TOOLING
```

Controller diagnostics + simulator events should make this classification possible.

---

# 30. Recommended Repository Shape

Conceptual only:

```text
cadence/
├── simulation/
│   ├── sumo/
│   ├── state/
│   ├── events/
│   └── scenario/
├── traffic/
│   ├── metrics/
│   ├── movements/
│   └── validation/
├── control/
│   ├── contracts/
│   ├── safety/
│   ├── fixed/
│   ├── max_pressure/
│   ├── mpc/
│   └── rl/
├── adapters/
│   ├── gym/
│   ├── pettingzoo/
│   └── observations/
├── experiments/
└── research/
```

Implementation details may change after coding-tool design review.

---

# 31. Initial Development Milestones

## M0 — Simulation Harness
- start/stop deterministic SUMO,
- canonical scenario,
- raw event/state capture.

## M1 — State + Metrics
- canonical lane/movement/intersection state,
- KPI/event pipeline.

## M2 — Signal Contract
- controller interface,
- safety/transition layer,
- fixed external test controller.

## M3 — Classical Baselines
- tuned fixed,
- SUMO actuated,
- Original Max-Pressure.

## M4 — Network Physical Baseline
- spillback metric,
- capacity-aware pressure.

## M5 — Predictive Baseline
- finite-storage MPC.

## M6 — RL Adapter
- Gym/PettingZoo adapter,
- DQN/PPO.

## M7 — Corridor/Network Experiments
- shared scenario/evaluation matrix.

Only after M7 should MARL/GNN become an implementation priority.

---

# 32. Architecture Decision Register

### ARCH-D01
> The simulation core is controller-agnostic.

### ARCH-D02
> Controllers access CADENCE traffic-domain interfaces rather than TraCI directly.

### ARCH-D03
> Canonical traffic state is separated from controller observation.

### ARCH-D04
> Signal safety/transitions are enforced outside adaptive controller algorithms.

### ARCH-D05
> Metrics and experiment KPIs are controller-independent.

### ARCH-D06
> RL frameworks are adapters, not the internal shape of CADENCE.

### ARCH-D07
> MPC prediction models remain private controller models and never receive future SUMO truth.

### ARCH-D08
> Observation fidelity and controller information scope are versioned experiment metadata.

### ARCH-D09
> Timeouts and fallback actions are part of the controller contract.

### ARCH-D10
> Training and evaluation are separate pipelines sharing the same frozen-controller interface.

### ARCH-D11
> MARL/GNN support is extensible but optional.

### ARCH-D12
> The repository and APIs should optimize for replacing controllers without modifying simulation semantics.

---

# 33. Final Pre-Implementation Principle

The long-term asset in CADENCE should be:

```text
validated traffic world
+
stable traffic-control contract
+
reproducible experiment system
```

not a particular neural network.

If future research shows:

```text
MPC > RL
```

or:

```text
Max-Pressure + RL > pure RL
```

or a new algorithm appears, CADENCE should allow that controller to be plugged in without rewriting the simulation foundation.

---

# 34. Research-to-Development Gate

Pre-implementation broad research is considered complete when these documents are accepted as the baseline:

- SUMO research
- Traffic Engineering research
- Max-Pressure research
- Optimization/MPC research
- RL-TSC research
- MARL/GNN landscape
- Cross-method synthesis
- Architecture/controller contract

After this gate:

> New research should be driven by a concrete experiment, implementation issue, or observed controller failure.

This prevents endless literature expansion from blocking development.
