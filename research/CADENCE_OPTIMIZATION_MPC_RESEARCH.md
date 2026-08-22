# CADENCE — Optimization / Model Predictive Control Research

**Formal Project Title:** Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks  
**Project Codename:** CADENCE  
**Document Type:** Focused Research Notebook  
**Status:** Active Research Checkpoint

---

# Part I — Optimization Fundamentals

## Optimization-Based Traffic Signal Control

Optimization-based control formulates traffic signal control as:

```text
choose control variables
→ optimize an objective
→ obey traffic/signal constraints
```

A generic formulation is:

```text
minimize J(x,u)

subject to:
- traffic dynamics
- signal constraints
- safety constraints
- capacity constraints
```

Where:

- `x` = traffic state,
- `u` = control decision,
- `J` = objective/cost function.

## Objective Function

Possible traffic-control objectives include:

- total queue,
- delay,
- stops,
- travel time,
- spillback penalties,
- phase-switch penalties,
- network-level congestion measures.

Optimization and RL both depend heavily on objective specification, but they use it differently.

```text
Optimization:
objective → solver searches for actions online

RL:
reward → policy is learned through training
```

## Decision Variables

Possible traffic-signal decision variables include:

- cycle length,
- green split,
- offset,
- phase selection,
- phase duration.

Discrete phase decisions often make optimization more difficult than continuous timing adjustments.

## Constraints

Optimization methods can represent constraints explicitly.

Examples:

```text
minimum green
maximum green
legal phase transitions
conflicting movements
physical link storage
cycle-time constraints
```

This is one of the major conceptual strengths of MPC.

---

# Part II — Model Predictive Control Fundamentals

## What Is MPC?

**Model Predictive Control (MPC)** repeatedly:

1. observes the current traffic state,
2. predicts future traffic using an internal model,
3. optimizes a sequence of future controls,
4. executes only the first action,
5. observes the new state,
6. re-optimizes.

```text
Current State
     ↓
Traffic Model
     ↓
Predict Future
     ↓
Optimize Future Actions
     ↓
Execute First Action
     ↓
Observe Again
     ↓
Repeat
```

This is called **receding-horizon control**.

## Prediction Horizon

The **prediction horizon** is how far into the future MPC considers.

Examples:

```text
next 60 seconds
next 5 cycles
next 10 control steps
```

A longer horizon can capture delayed downstream effects but increases:

- computational cost,
- model uncertainty,
- optimization complexity.

Longer is not automatically better.

## Why Execute Only the First Action?

Future predictions may become inaccurate as traffic changes.

Therefore MPC does not normally commit permanently to its entire predicted plan.

Example:

```text
planned:
now      → Phase A
+10 sec  → Phase B
+20 sec  → Phase C

execute:
Phase A only

then observe and re-optimize
```

---

# Part III — Traffic Model Inside MPC

## Traffic-State Dynamics

A generic model can be written as:

```text
x(t+1) = f(x(t), u(t), d(t))
```

where:

- `x(t)` = current traffic state,
- `u(t)` = signal action,
- `d(t)` = external traffic demand.

Possible state representations include:

- queue lengths,
- link vehicle accumulation,
- density,
- occupancy.

## SUMO Is Not Necessarily the MPC Model

CADENCE should distinguish:

```text
SUMO
=
experiment environment / detailed simulator
```

from:

```text
MPC traffic model
=
controller's internal prediction model
```

A simplified prediction model can be evaluated against richer SUMO dynamics.

### Decision Candidate MPC-D01

> CADENCE should treat SUMO as the experiment environment and an MPC traffic model as an internal controller model; the two must not be assumed equivalent.

---

# Part IV — Store-and-Forward Model

## Concept

A road link is represented as a traffic-storage unit.

```text
        inflow
          ↓
    ┌───────────┐
    │ vehicles  │
    │    x_i    │
    └───────────┘
          ↓
        outflow
```

State update:

```text
x_i(t+1)
=
x_i(t)
+
inflow
-
outflow
```

This abstraction is simpler than microscopic vehicle simulation and is useful for real-time network optimization.

## Connection to Max-Pressure Research

This model resembles the physical storage balance already identified in the Max-Pressure track:

```text
Storage(t+1)
=
Storage(t)
+
Inflow
-
Outflow
```

---

# Part V — TUC and Network Feedback Control

## Traffic-Responsive Urban Control (TUC)

TUC is an established network traffic-control approach based on simplified network models and control-theoretic feedback.

Important lesson:

> Network-wide adaptive signal control existed well before modern Deep RL.

Classical TUC-style control is generally designed for:

- speed,
- scalability,
- network-level congestion control.

MPC variants extend this idea by explicitly optimizing over a prediction horizon and handling constraints.

---

# Part VI — Finite Storage and Spillback

MPC can explicitly represent constraints such as:

```text
0 ≤ x_i ≤ X_i_max
```

where:

- `x_i` = current vehicles/storage,
- `X_i_max` = physical storage capacity.

This makes MPC conceptually attractive for:

- downstream-capacity protection,
- spillback control,
- signal constraints,
- finite urban links.

### Decision Candidate MPC-D02

> MPC should be evaluated partly for its ability to represent traffic and signal constraints explicitly, particularly finite storage and legal control bounds.

---

# Part VII — Reactive Max-Pressure vs Predictive MPC

## Max-Pressure

```text
observe current queues
↓
calculate pressure
↓
react
```

Question:

> Is downstream congested now?

## MPC

```text
observe current state
↓
predict future state
↓
evaluate future consequences
↓
act
```

Question:

> If I release traffic now, will downstream congestion become critical later?

This anticipatory behavior is one of MPC's main conceptual advantages over purely reactive Max-Pressure.

---

# Part VIII — Model Mismatch

Prediction introduces a new failure mode:

```text
internal traffic model
≠
actual traffic behavior
```

Examples:

- demand forecast error,
- inaccurate saturation flow,
- incorrect turning ratios,
- simplified queue dynamics.

### Decision Candidate MPC-D03

> Any MPC benchmark should document its prediction model and evaluate sensitivity to model mismatch or demand uncertainty.

---

# Part IX — Centralized and Distributed MPC

## Centralized MPC

A central optimizer controls several intersections simultaneously.

```text
        CENTRAL MPC
       /    |     \
      A     B      C
```

Advantages:

- explicit coordination,
- global objective.

Limitations:

- optimization size grows rapidly,
- communication and computation requirements increase.

## Distributed MPC

Several local MPC controllers coordinate with neighboring controllers.

```text
MPC A ↔ MPC B ↔ MPC C
```

This resembles MARL structurally, but the mechanism differs:

```text
Distributed MPC
→ explicit model + optimization

MARL
→ learned policies
```

---

# Part X — Optimization Families

## LP — Linear Programming

Linear objective and linear constraints.

## QP — Quadratic Programming

Allows quadratic objectives, such as queue-square penalties.

## MILP — Mixed-Integer Linear Programming

Includes both continuous and integer/binary decisions.

Useful for:

- green/red decisions,
- discrete phase selection.

## MIQP — Mixed-Integer Quadratic Programming

Combines integer decisions with quadratic objectives.

---

# Part XI — Combinatorial Complexity

Discrete phase selection can create rapidly growing combinations.

Example:

```text
4 possible phases per intersection
× many intersections
× multiple prediction steps
```

Real-time MPC often requires:

- simplified models,
- restricted action spaces,
- decomposition,
- approximate optimization.

---

# Part XII — Objective Specification

MPC behavior depends strongly on the chosen objective.

Examples:

```text
minimize total queue
```

versus:

```text
minimize travel time
```

versus:

```text
queue
+
spillback penalty
+
switching penalty
```

A controller can only optimize what its objective asks it to optimize.

---

# Part XIII — Explainability

MPC can often provide explicit reasoning:

```text
Candidate A
predicted cost = 150

Candidate B
predicted cost = 92

→ choose B
```

This may be operationally valuable for traffic-control systems.

---

# Part XIV — Signal and Route Co-Optimization

Optimization-based traffic management can potentially control more than signal timing.

Possible future CADENCE control plugins may include:

```text
signal controller
routing controller
perimeter controller
```

This supports CADENCE as a modular traffic-control experimentation platform rather than an RL-only project.

---

# Part XV — Max-Pressure vs MPC

| Property | Max-Pressure | MPC |
|---|---|---|
| Uses current traffic state | Yes | Yes |
| Downstream-aware | Yes | Yes |
| Predicts future traffic | Not inherently | Yes |
| Explicit traffic model | Limited | Required |
| Explicit constraints | Limited / architecture-enforced | Strong |
| RL training required | No | No |
| Online optimization cost | Low | Higher |
| Model mismatch risk | Lower | Higher |
| Explainability | High | High |
| Scalability | Strong | Depends on formulation |

MPC is another serious non-learning competitor to RL.

---

# Part XVI — MPC vs Reinforcement Learning

## MPC Philosophy

```text
I know approximately how traffic evolves
↓
predict
↓
optimize every decision
```

## RL Philosophy

```text
interact with simulator/environment
↓
learn policy
↓
execute learned decisions
```

Typical cost distribution:

```text
MPC:
higher runtime optimization cost

RL:
higher training cost,
usually low inference cost
```

The boundary becomes less clear with hybrid approaches such as:

- Model-Based RL,
- RL-assisted MPC,
- learned traffic models,
- learned optimizer surrogates.

---

# Part XVII — Decision Register

| ID | Decision Candidate |
|---|---|
| MPC-D01 | Keep SUMO experiment dynamics separate from the internal MPC prediction model. |
| MPC-D02 | Evaluate MPC partly for explicit handling of finite storage and signal constraints. |
| MPC-D03 | Document prediction models and evaluate model-mismatch/demand uncertainty. |
| MPC-D04 | Do not benchmark an intentionally weak/toy MPC merely to favor RL. |

---

# Part XVIII — Initial Hypotheses

### MPC-H01

> Predictive control may outperform reactive Max-Pressure when congestion can be anticipated before downstream storage is exhausted.

### MPC-H02

> MPC's strongest advantages may appear near finite-storage, travel-delay, and coordinated multi-intersection constraints.

### MPC-H03

> Model mismatch and computational cost may erase part of MPC's theoretical advantage in realistic networks.

### MPC-H04

> A modular CADENCE controller API can support MPC cleanly if the prediction model remains internal to the controller plugin.

---

# Part XIX — Next Research Direction

The next MPC research topic should be:

# Traffic Models for MPC

Focus:

1. Store-and-Forward model
2. Cell Transmission Model (CTM)
3. Queue/link-based models
4. finite storage representation
5. spillback propagation
6. prediction fidelity vs computational cost
7. suitability for CADENCE/SUMO benchmarking

After this, the MPC track should cover:

- robust/stochastic MPC,
- practical baseline selection,
- computational feasibility,
- comparison with Max-Pressure and RL.

---

# Part XX — Research Result: Traffic Models for MPC

## Why the Internal Traffic Model Matters

MPC does not optimize directly against reality. It optimizes against an internal prediction model.

Therefore:

```text
MPC quality
=
optimization quality
×
prediction-model quality
```

A sophisticated optimizer using a poor traffic model may make worse decisions than a simpler reactive controller.

For CADENCE this creates a strict architectural separation:

```text
SUMO
=
detailed experiment environment

MPC prediction model
=
controller-internal approximation
```

This separation allows controlled model-mismatch experiments.

---

## Store-and-Forward Model

The **Store-and-Forward (S&F)** model treats each link approximately as a traffic-storage reservoir.

A basic conservation equation is:

```text
x_i(k+1)
=
x_i(k)
+
inflow_i(k)
-
outflow_i(k)
```

where:

- `x_i` = number of vehicles stored on link `i`,
- inflow = traffic entering the link,
- outflow = traffic leaving the link.

The model is attractive because it is:

- compact,
- network-oriented,
- computationally efficient,
- naturally expressed in state-space form,
- suitable for linear/quadratic feedback and optimization.

The TUC family is a major example of network control built around Store-and-Forward traffic modeling.

### Main abstraction

A link is treated largely as one aggregated storage state.

Therefore the basic S&F model does not explicitly represent the physical position of the queue inside the link.

---

## Strengths of Store-and-Forward

### 1. Computational simplicity

The model can remain sufficiently compact for large networks.

### 2. Natural network conservation

Traffic propagation can be represented through link inflow/outflow relationships.

### 3. Compatibility with control theory

Linear or approximately linear dynamics allow methods such as:

- LQR,
- QP,
- MPC,
- decentralized feedback control.

### 4. Strong history in urban signal control

TUC and later decentralized/store-and-forward control research demonstrate that this model family remains highly relevant to congested urban networks.

---

## Limitations of Basic Store-and-Forward

The basic abstraction may not represent:

- queue position within a long road segment,
- detailed shockwave propagation,
- spatial progression of congestion,
- transient stop-and-go patterns,
- explicit finite-storage blocking unless additional constraints/model extensions are added.

Thus:

```text
link accumulation
```

and:

```text
physical queue propagation
```

are not identical.

This distinction is similar to the limitation already identified in Original Max-Pressure.

---

## Cell Transmission Model (CTM)

The **Cell Transmission Model (CTM)** was introduced by Daganzo as a discrete macroscopic representation consistent with kinematic-wave traffic-flow theory.

Instead of representing an entire link as one storage state, the road is divided into multiple cells.

Example:

```text
Road segment

┌──────┬──────┬──────┬──────┐
│ C1   │ C2   │ C3   │ C4   │
└──────┴──────┴──────┴──────┘
```

Traffic moves from one cell to the next subject to:

- how much traffic the upstream cell can send,
- how much traffic the downstream cell can receive.

This allows congestion to move spatially through the road.

---

## CTM Sending and Receiving Intuition

For two adjacent cells:

```text
Cell i
   ↓
Cell i+1
```

actual transfer is limited by approximately:

```text
min(
  upstream sending capability,
  downstream receiving capability
)
```

If the downstream cell becomes full:

```text
receiving capability ↓
```

and upstream discharge is restricted.

This mechanism naturally represents backward-propagating congestion.

---

## Why CTM Represents Spillback Better

Suppose downstream congestion begins near an intersection.

With several cells:

```text
C1 → C2 → C3 → C4[FULL]
```

over subsequent time steps:

```text
C3 fills
↓
C2 fills
↓
C1 fills
```

The congestion boundary moves upstream.

This reproduces queue formation, propagation, and dissipation more explicitly than a single-link aggregate storage variable.

Daganzo's original CTM work specifically emphasizes the model's ability to reproduce evolving queues and density discontinuities/shockwaves using simple difference equations.

---

## CTM and Finite Storage

Each cell has a maximum occupancy/density.

Therefore the model directly supports the idea that:

```text
downstream full
→ receiving flow constrained
→ upstream cannot discharge freely
```

This makes CTM conceptually attractive for CADENCE because physical spillback is a central research concern.

---

## CTM Network Extension

CTM has also been generalized to networks containing:

- merges,
- diverges,
- known turning proportions,
- multiple commodities/routes.

This means CTM is not limited to one highway segment.

However, intersection signal representation still requires careful mapping between:

- cell flows,
- turning movements,
- signal phases,
- service constraints.

---

## Store-and-Forward vs CTM

| Property | Store-and-Forward | CTM |
|---|---|---|
| Spatial resolution | Link-level | Multi-cell |
| Computational complexity | Lower | Higher |
| Queue propagation | Aggregate | Explicit spatial propagation |
| Shockwave behavior | Limited/basic | Natural strength |
| Finite receiving capacity | Can be constrained/extended | Fundamental to model |
| Spillback representation | Requires care/extensions | Stronger |
| Large-network tractability | Strong | More demanding |
| Controller modeling simplicity | High | Medium |
| Suitability for prediction | Strong for aggregate control | Strong for physical propagation |
| Model calibration burden | Lower | Higher |

---

## Which Model Is Better for CADENCE?

There is no universally superior model.

The choice depends on what the MPC baseline is expected to prove.

### Store-and-Forward is attractive if:

- the goal is a scalable network-control baseline,
- aggregate link congestion is sufficient,
- computational feasibility matters strongly,
- MPC controls green splits at network level.

### CTM is attractive if:

- physical queue propagation is central,
- spillback timing must be predicted explicitly,
- link length and internal spatial state matter,
- computational cost remains manageable for the scenario size.

### Current CADENCE direction

CADENCE should **not select CTM merely because it is more detailed**.

The baseline should use the simplest internal traffic model that represents the phenomenon being evaluated credibly.

This is consistent with the broader CADENCE principle:

> Complexity must earn its place.

---

## Queue/Link-Based Hybrid Models

Between simple S&F and full CTM there are intermediate models that add:

- link storage bounds,
- travel-time delays,
- downstream supply restrictions,
- queue spillback constraints,

without discretizing every road into many cells.

These models may provide a good practical compromise for real-time MPC.

Therefore the final MPC baseline should not be chosen solely from a binary:

```text
S&F vs CTM
```

but from:

```text
required physical fidelity
vs
online computational cost
```

---

## MPC Traffic-Model Fidelity Proposal

A provisional internal-model fidelity ladder:

### M0 — Simple Link Accumulation

```text
x_next = x + inflow - outflow
```

No explicit spatial spillback.

### M1 — Storage-Constrained Link Model

Adds:

- finite storage,
- downstream receiving constraints.

### M2 — Travel-Time / Delayed Link Model

Adds:

- non-zero propagation/travel delays,
- improved temporal traffic movement.

### M3 — Cell Transmission Model

Adds:

- spatial cells,
- shockwave/queue propagation,
- explicit sending/receiving dynamics.

### M4 — Higher-Fidelity / Specialized Model

Only if justified for later research.

This ladder is a research framework, not yet an adopted standard.

---

## Decision Candidate MPC-D05 — Model Fidelity Must Match the Claim

> CADENCE should choose an MPC prediction model based on the traffic phenomenon being evaluated, not on maximum theoretical model detail.

## Decision Candidate MPC-D06 — Spillback Claim Requires Spillback-Capable Model

> An MPC controller should not be described as predictive spillback control unless its internal model can represent finite receiving/storage constraints and backward congestion effects at the required fidelity.

## Decision Candidate MPC-D07 — Start with Tractable Model

> The first MPC baseline should prefer a tractable link-based/store-and-forward-style model with explicit finite-storage constraints unless experiments show that spatial CTM detail is necessary.

This is currently a design candidate rather than a final architecture decision.

---

# Part XXI — Research Result: Robust / Stochastic / Practical MPC

## Why Deterministic MPC Is Not Enough

A deterministic MPC may assume:

```text
predicted demand
=
future demand
```

and:

```text
turn ratio estimate
=
future turn ratio
```

Real traffic violates this constantly.

Uncertainty may come from:

- external demand variation,
- turning-ratio variation,
- detector noise,
- incidents,
- parking/side-street flows,
- inaccurate saturation rates,
- model simplification.

Therefore a practical MPC must be evaluated under imperfect predictions.

---

## Nominal MPC

**Nominal MPC** optimizes using one assumed future model/trajectory.

Conceptually:

```text
forecast = expected future
↓
optimize against this forecast
```

Advantages:

- simpler,
- cheaper computationally.

Risk:

- brittle if actual traffic deviates significantly.

---

## Robust MPC

**Robust MPC** asks:

> What action remains acceptable even if uncertain quantities vary within a defined uncertainty set?

Conceptually:

```text
demand ∈ [low, high]
turn ratio ∈ uncertainty range
```

and the controller searches for an action that performs safely under unfavorable cases.

A common formulation is minimax-like:

```text
choose control
that minimizes
worst-case cost
```

### Advantages

- explicit protection against model/demand error,
- useful near physical constraints,
- potentially safer for spillback prevention.

### Trade-off

Robust control can become conservative.

Example:

```text
worst case predicts heavy arrivals
→ controller withholds traffic
```

even when actual demand remains light.

---

## Stochastic MPC

**Stochastic MPC** models uncertain quantities probabilistically.

Example:

```text
future demand
~ probability distribution
```

Rather than optimize only the worst case, it can optimize:

- expected performance,
- risk-sensitive objectives,
- chance constraints.

A **chance constraint** may look conceptually like:

```text
P(queue <= storage capacity) ≥ 0.95
```

meaning:

> Keep the probability of overflow below the allowed risk level.

Research on stochastic urban signal MPC has explicitly used uncertain demand/disturbances and chance constraints to reduce spillback risk.

---

## Robust vs Stochastic MPC

| Property | Robust MPC | Stochastic MPC |
|---|---|---|
| Uncertainty model | Bounded/set-based | Probabilistic |
| Typical philosophy | Protect against worst/uncertain cases | Optimize expected/risk-aware behavior |
| Conservativeness | Can be high | Usually tunable by risk |
| Data requirement | Bounds may be sufficient | Distribution/variance information useful |
| Computation | Higher than nominal | Often higher |
| Interpretation | Strong safety envelope | Probability-aware risk |

Neither is automatically superior.

---

## Model Mismatch Test

CADENCE should not evaluate MPC only with a perfect prediction model.

Suggested experiment dimensions:

```text
Nominal model
↓
mild mismatch
↓
moderate mismatch
↓
severe mismatch
```

Potential mismatch sources:

- ± demand error,
- turning-ratio error,
- saturation-flow error,
- link-storage estimate error,
- delayed/noisy traffic-state estimates.

This can reveal whether predictive gains survive realistic uncertainty.

---

## Prediction Horizon Sensitivity

A practical MPC benchmark should test more than one horizon when feasible.

Too short:

```text
low computation
but weak anticipation
```

Too long:

```text
better theoretical foresight
but higher computation
and larger forecast error
```

The selected horizon should therefore be justified empirically rather than arbitrarily.

---

## Computation as an Evaluation Metric

For real-time control, controller quality includes whether a decision arrives before its deadline.

CADENCE should record:

```text
controller decision latency
```

and potentially:

```text
solver timeout / failure count
```

for MPC.

A controller that finds a mathematically better action after the real-time deadline is operationally unusable.

---

## Scalability

MPC complexity can increase with:

- number of intersections,
- number of phases,
- horizon length,
- model resolution,
- number of scenarios/uncertainty samples,
- integer/discrete variables.

Therefore scalability experiments should distinguish:

```text
1 intersection
corridor
small urban network
```

rather than extrapolate from one scenario.

---

## Centralized vs Distributed Practicality

### Centralized MPC

Potentially stronger global coordination, but:

- larger optimization problem,
- higher communication dependency,
- single computational bottleneck.

### Distributed / Hierarchical MPC

Splits the network into subproblems.

Potential benefits:

- improved real-time feasibility,
- local computation,
- scalability.

Potential costs:

- coordination complexity,
- approximation/decomposition error,
- additional communication logic.

Recent robust/hierarchical MPC research continues to use decomposition specifically to improve urban-network real-time performance.

---

## Solver Failure Must Be Defined

A practical MPC controller needs fallback behavior when:

- the solver times out,
- no feasible solution is found,
- observations are missing,
- the prediction model becomes invalid.

Possible fallback:

```text
previous feasible control
```

or:

```text
safe actuated/fixed fallback
```

The fallback mechanism must be part of the controller specification.

---

## Practical MPC Baseline Scope

CADENCE does not need every MPC family.

A realistic research baseline could be:

### Baseline MPC-A — Deterministic Finite-Storage MPC

- simple link/store-and-forward-style model,
- explicit storage constraints,
- continuous green split or restricted action representation,
- short receding horizon.

Then optionally:

### Robustness Extension

Evaluate the same baseline under traffic-model mismatch.

A separate full stochastic/robust MPC implementation is not mandatory for the first CADENCE version unless predictive-control robustness becomes part of the research contribution.

This prevents MPC research from becoming its own thesis.

---

## Decision Candidate MPC-D08 — Evaluate Runtime Feasibility

> MPC evaluation should report decision/solver latency and controller deadline failures in addition to traffic-performance metrics.

## Decision Candidate MPC-D09 — Imperfect Prediction Evaluation

> MPC should be evaluated under controlled model/demand mismatch rather than only under perfect prediction assumptions.

## Decision Candidate MPC-D10 — Require Safe Fallback

> Any practical MPC controller should define deterministic fallback behavior for infeasible, missing-state, or solver-timeout conditions.

## Decision Candidate MPC-D11 — Scope MPC to One Competent Baseline

> CADENCE should implement one competent, finite-storage-aware MPC baseline rather than reproducing the full robust/stochastic MPC literature unless MPC itself becomes part of the proposed contribution.

---

# Part XXII — Updated MPC Comparison

## Max-Pressure vs MPC

```text
Max-Pressure
→ reactive feedback
→ model-light
→ low online cost
→ strong queue-stability theory in specific formulations

MPC
→ predictive feedback
→ explicit internal model
→ explicit constraints
→ higher online cost
→ vulnerable to model mismatch
```

The key research contrast is now:

> **Reactive network stability vs predictive constraint-aware control.**

---

## Implication for RL Research

The MPC track narrows the question RL must answer.

RL should not be presented merely as:

- adaptive,
- network-aware,
- able to optimize complex objectives,
- able to prevent spillback.

Classical/non-learning methods already provide many of these capabilities.

Potential RL-specific value must eventually be investigated around areas such as:

- learning complex nonlinear policies without solving large online optimization problems,
- adapting to model mismatch without explicit traffic-model identification,
- fast inference after training,
- policy transfer/generalization,
- hybrid learning + classical control.

These remain hypotheses until the RL literature review is complete.

---

# Part XXIII — Updated MPC Decision Register

| ID | Decision Candidate |
|---|---|
| MPC-D01 | Keep SUMO experiment dynamics separate from the internal MPC prediction model. |
| MPC-D02 | Evaluate MPC partly for explicit handling of finite storage and signal constraints. |
| MPC-D03 | Document prediction models and evaluate model-mismatch/demand uncertainty. |
| MPC-D04 | Do not benchmark an intentionally weak/toy MPC merely to favor RL. |
| MPC-D05 | Match MPC model fidelity to the traffic phenomenon/research claim. |
| MPC-D06 | Require spillback-capable internal modeling before claiming predictive spillback control. |
| MPC-D07 | Prefer a tractable finite-storage link model for the first MPC baseline unless CTM detail is empirically necessary. |
| MPC-D08 | Report solver/controller decision latency and deadline failures. |
| MPC-D09 | Evaluate MPC under controlled prediction/model mismatch. |
| MPC-D10 | Define safe fallback behavior for infeasible/timeout/missing-state conditions. |
| MPC-D11 | Scope the initial project to one competent finite-storage-aware MPC baseline. |

---

# Part XXIV — Current MPC Hypothesis Status

| ID | Hypothesis | Current Status |
|---|---|---|
| MPC-H01 | Predictive control may outperform reactive Max-Pressure when congestion can be anticipated. | Plausible / supported conceptually; empirical validation required. |
| MPC-H02 | MPC advantages may be strongest near finite-storage and coordinated-network constraints. | Supported as a strong research hypothesis. |
| MPC-H03 | Model mismatch and computation may erase predictive advantage. | Strongly supported as a practical concern. |
| MPC-H04 | Modular CADENCE controller API can contain prediction models inside controller plugins. | Strong architecture candidate. |

---

# Part XXV — MPC Research Checkpoint

The MPC pre-implementation research is now sufficient at the **foundation / baseline-selection level**.

CADENCE currently understands:

```text
Optimization fundamentals
        ↓
MPC / receding horizon
        ↓
Store-and-Forward
        ↓
CTM / physical propagation
        ↓
finite storage / spillback
        ↓
model mismatch
        ↓
robust / stochastic MPC
        ↓
runtime / scalability constraints
```

Detailed MPC algorithm selection should be deferred until after the RL and cross-method comparison tracks.

This prevents premature implementation decisions.

---

# Part XXVI — Source Notes

Primary references used for this checkpoint include:

1. Daganzo, C. F. (1994), *The Cell Transmission Model: A Dynamic Representation of Highway Traffic Consistent with the Hydrodynamic Theory*, Transportation Research Part B.
   - https://www.sciencedirect.com/science/article/pii/0191261594900027
   - https://its.berkeley.edu/node/4777

2. Daganzo, C. (1994), *The Cell Transmission Model: Network Traffic*.
   - https://escholarship.org/uc/item/9pz309w7

3. Diakaki, C., Papageorgiou, M., Aboudolas, K. (2002), *A multivariable regulator approach to traffic-responsive network-wide signal control*, Control Engineering Practice.
   - https://www.sciencedirect.com/science/article/pii/S0967066101001216

4. Stochastic Model Predictive Control for Urban Traffic Networks (2017), Applied Sciences.
   - https://www.mdpi.com/2076-3417/7/6/588

5. Robust real-time control for urban road traffic networks (2014), IEEE Transactions on Intelligent Transportation Systems.
   - https://research.chalmers.se/en/publication/189805

6. HD-RMPC: Hierarchical Distributed and Robust Model Predictive Control Framework for Urban Traffic Signal Timing (2022).
   - https://onlinelibrary.wiley.com/doi/10.1155/2022/8131897

7. Distributed Stochastic Model Predictive Control for an Urban Traffic Network (2022).
   - https://arxiv.org/abs/2201.07949

---

# Part XXVII — Next Research Track

The next critical pre-implementation track is:

# Reinforcement Learning for Traffic Signal Control

The detailed chat explanation can be skipped.

Research should be written directly into a dedicated document covering:

1. RL traffic-signal-control literature landscape
2. single-agent vs multi-intersection RL
3. observation/state representations
4. action spaces
5. reward design
6. DQN / PPO / actor-critic families
7. training/evaluation methodology
8. common benchmark weaknesses
9. generalization and simulator overfitting
10. comparison with Actuated, Max-Pressure, and MPC
