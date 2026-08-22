# CADENCE — Max-Pressure / Backpressure Control Research

**Formal Project Title:** Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks  
**Project Codename:** CADENCE  
**Document Type:** Focused Research Notebook  
**Status:** Initial Research Scaffold — Detailed Research Pending

---

## 1. Purpose

This document is dedicated to the study of **Max-Pressure / Backpressure traffic signal control** as a network-aware classical control baseline for CADENCE.

The objective is not to assume that Max-Pressure is superior to Reinforcement Learning, but to understand:

- what problem Max-Pressure actually solves,
- what traffic information it requires,
- why it is considered network-aware,
- what theoretical guarantees or stability properties are associated with it,
- where it breaks down in realistic road networks,
- how spillback and finite downstream storage affect it,
- what variants improve its practical behavior,
- and what research value remains for RL if Max-Pressure already performs strongly.

---

## 2. Why This Topic Matters to CADENCE

Previous CADENCE research established that:

- fixed-time control is too weak as the only baseline,
- actuated control already provides strong local adaptation,
- local responsiveness is not the same as network awareness,
- oversaturated traffic requires queue management and spillback prevention,
- downstream conditions matter when deciding whether to release traffic.

Max-Pressure is therefore a key next topic because it directly addresses:

```text
upstream demand
+
downstream congestion
+
network-level queue interaction
```

without requiring neural networks or RL training.

---

## 3. Core Research Questions

The detailed research should answer:

1. What is **pressure** in traffic control?
2. What is the mathematical difference between **backpressure** and **Max-Pressure**?
3. How are upstream and downstream queues represented?
4. How is movement pressure computed?
5. How is phase pressure computed?
6. How does the controller select a signal phase?
7. What traffic observations are required?
8. Why is Max-Pressure associated with throughput/stability properties?
9. What assumptions are required for those theoretical guarantees?
10. Does standard Max-Pressure naturally prevent spillback?
11. What happens when downstream links have finite storage?
12. How does link length affect queue-based pressure?
13. How does turning ratio uncertainty affect pressure estimation?
14. What happens under heterogeneous lanes and multi-lane movements?
15. How does Max-Pressure behave under light traffic?
16. How does it compare with actuated control?
17. How does it compare with MPC / optimization?
18. What important practical variants exist?
19. How should Max-Pressure be implemented in SUMO?
20. What exactly would RL need to improve beyond Max-Pressure?

---

## 4. Planned Research Structure

### Part I — Foundations
- Queue differential
- Backpressure intuition
- Movement pressure
- Phase pressure
- Network conservation

### Part II — Standard Max-Pressure Algorithm
- Observation
- Calculation
- Phase selection
- Decision interval
- Signal constraints

### Part III — Theory
- Throughput optimality
- Stability intuition
- Assumptions
- What the guarantees do and do not mean

### Part IV — Practical Traffic Engineering Issues
- Finite link storage
- Spillback
- Queue measurement
- Lane groups
- Turning movements
- Unequal link lengths
- Lost time / switching cost
- Phase transition constraints

### Part V — Important Variants
- Capacity-aware pressure
- Position-weighted pressure
- Spillback-aware pressure
- Travel-time / delay variants
- Hybrid pressure control

### Part VI — Comparison
- Fixed-time
- Actuated
- Coordinated actuated
- Max-Pressure
- MPC
- RL

### Part VII — SUMO Implementation
- Required TraCI measurements
- Queue definitions
- Downstream state
- Phase representation
- Safety layer
- Controller interval
- Benchmark reproducibility

### Part VIII — CADENCE Implications
- Baseline role
- Observation implications
- Reward implications
- Hybrid opportunities
- Research contribution boundary

---

## 5. Preliminary Concept Map

```text
Incoming Queue
      │
      ▼
Movement Demand
      │
      │ compare with
      ▼
Downstream Queue / Capacity
      │
      ▼
Movement Pressure
      │
      ▼
Aggregate by Compatible Phase
      │
      ▼
Phase Pressure
      │
      ▼
Select Highest-Pressure Phase
      │
      ▼
Safety / Signal Constraint Layer
      │
      ▼
SUMO Traffic Signal
```

This diagram is only a research scaffold. Exact definitions will be added after literature review.

---

## 6. Comparison Questions

Every comparison with Max-Pressure should use the same dimensions:

| Dimension | Question |
|---|---|
| Observation | What traffic state does the controller require? |
| Local/Network | Does it explicitly use neighboring/downstream state? |
| Training | Is learning required? |
| Model | Does it require prediction or a traffic model? |
| Computation | How expensive is each decision? |
| Safety | How are legal signal transitions enforced? |
| Spillback | Does it account for finite downstream storage? |
| Explainability | Can a decision be explained from traffic state? |
| Robustness | How sensitive is it to measurement error? |
| Scalability | How does it behave as network size grows? |
| Generalization | Does it require retraining for a new network? |
| Performance | Under which traffic regimes does it perform well/poorly? |

---

## 7. Initial Working Hypotheses

These are hypotheses, not conclusions.

### MP-H01

> Max-Pressure may provide a strong network-aware baseline without RL training.

### MP-H02

> Standard queue-differential pressure may not fully capture finite downstream storage and physical spillback.

### MP-H03

> Practical Max-Pressure performance may depend strongly on queue definition, link length, turning ratios, and phase constraints.

### MP-H04

> A meaningful CADENCE RL contribution may require improving behavior beyond standard Max-Pressure under realistic network constraints rather than merely outperforming fixed or actuated control.

### MP-H05

> Hybrid designs may be more scientifically defensible than pure RL if Max-Pressure provides a strong stability-oriented backbone.

---

## 8. Decision Register

No Max-Pressure-specific design decision is adopted yet.

Future decisions will use identifiers:

```text
MP-D01
MP-D02
MP-D03
...
```

This file should distinguish clearly between:

- established literature findings,
- CADENCE hypotheses,
- design candidates,
- adopted decisions.

---

## 9. Research Method

For each research session:

```text
Concept
→ intuitive explanation
→ mathematical definition
→ traffic-engineering meaning
→ assumptions
→ known limitations
→ CADENCE relevance
→ implementation implication
```

Primary sources should prioritize:

- original Max-Pressure / backpressure research papers,
- peer-reviewed transportation journals,
- authoritative traffic control literature,
- recent review papers,
- SUMO documentation for implementation details.

---

## 10. Immediate Next Research Session

# Max-Pressure Fundamentals

The first detailed research session should cover:

1. Backpressure intuition
2. Queue differential
3. Movement pressure
4. Phase pressure
5. A small 2-intersection numerical example
6. Why downstream queue changes the decision
7. The basic phase-selection algorithm
8. What information the controller must observe
9. How this differs from actuated control
10. What remains unknown before implementation

---

> **Research principle:**  
> Do not treat Max-Pressure as “another algorithm to beat.” First understand which traffic problem it solves and under which assumptions its advantages hold.

---

# Part IX — Research Result: Max-Pressure / Backpressure Fundamentals

## Backpressure Intuition

Max-Pressure considers both upstream demand and downstream congestion.

```text
large upstream queue + low downstream queue
→ strong pressure to serve

large upstream queue + high downstream queue
→ weaker pressure to serve
```

This differs from simply serving the largest incoming queue.

## Queue Differential

A basic intuition is:

```text
pressure ≈ upstream queue - downstream queue
```

Example:

```text
upstream = 20
downstream = 5
queue differential = 15
```

## Movement-Oriented Queues

Original Max-Pressure works with movement-oriented queues such as:

```text
A → B : 10 vehicles
A → C : 25 vehicles
A → D : 5 vehicles
```

rather than only total incoming-link queues.

## Turning Structure

If traffic entering downstream link `m` later turns toward multiple links, downstream congestion is weighted by turning ratios.

## Movement and Stage Pressure

Conceptually:

```text
movement pressure
=
upstream demand
-
expected downstream congestion
```

A legal signal stage combines compatible movements:

```text
stage pressure
=
sum of movement-pressure contributions
```

The controller chooses the legal stage with the largest pressure.

## Local Information with Network-Level Effect

An intersection may only need adjacent incoming/outgoing queue states, yet downstream congestion can still alter upstream decisions.

### MP-D07

> Distinguish local-information control from locally optimized control. Max-Pressure may use local adjacent measurements while encoding downstream network effects.

## Stability / Throughput Interpretation

Max-Pressure's theoretical throughput-optimality is a queue-stability statement under model assumptions.

It does not mean:

- minimum travel time,
- minimum waiting time,
- no congestion,
- best empirical completed-trip throughput in every simulation.

### MP-D05

> Do not interpret theoretical Max-Pressure throughput-optimality as guaranteed minimum delay, waiting time, or best finite-simulation throughput.

## Point-Queue Limitation

Original theoretical Max-Pressure uses abstract queues rather than finite physical road storage.

Therefore:

```text
downstream queue awareness
≠
full physical spillback awareness
```

### MP-D02

> Standard downstream queue awareness must not be described as full physical spillback awareness without explicitly modeling finite link storage.

## Baseline Role

### MP-D01

> Treat Max-Pressure as a serious candidate network-aware classical baseline for CADENCE rather than an optional heuristic comparison.

## Shared Signal Safety Layer

### MP-D03

> Max-Pressure and learned controllers should use the same legal signal-transition/safety layer wherever possible.

---

# Part X — Research Result: Original Max-Pressure Mathematics

## Core Notation

For movement `l → m`:

- `x(l,m)` — queued vehicles intending to move from `l` to `m`
- `r(m,p)` — downstream turning ratio from `m` toward `p`
- `c(l,m)` — saturation/service rate of movement `l → m`
- `S(l,m)` — whether movement `l → m` is active in the candidate legal stage

## Original Movement Weight

```text
w(l,m)
=
x(l,m)
-
Σ r(m,p) x(m,p)
```

Interpretation:

```text
movement weight
=
upstream movement queue
-
expected downstream movement queue
```

## Turning-Ratio Example

Suppose:

```text
x(A,B) = 20
B → C = 75%
B → D = 25%
x(B,C) = 12
x(B,D) = 4
```

Then:

```text
expected downstream queue
= 0.75×12 + 0.25×4
= 10

w(A,B) = 20 - 10 = 10
```

## Saturation-Rate Weighting

Movement contribution:

```text
c(l,m) × w(l,m)
```

This combines queue imbalance with service capability.

## Stage Pressure

For candidate legal stage `S`:

```text
γ(S)
=
Σ c(l,m) w(l,m) S(l,m)
```

The controller selects:

```text
S*
=
argmax γ(S)
```

## Numerical Example

```text
Phase A pressure = 32.7
Phase B pressure = 13.5

→ choose Phase A
```

A movement with the largest raw incoming queue may still lose if its downstream queue is also very large.

## Isolated-Intersection Special Case

If outgoing links effectively leave the network:

```text
downstream queue = 0
```

then:

```text
w(l,m) = x(l,m)
```

and Max-Pressure approaches a queue × service-capability controller.

## Parameter Requirements

Original Max-Pressure does not need average external demand forecasts, but it still depends on:

- turning ratios,
- saturation/service rates,
- legal signal stages.

## Adaptive Max-Pressure

If turning ratios or service rates are unknown, estimated values may be used and updated from measurements.

## Lyapunov / Stability Intuition

A common queue-energy function is:

```text
V(X) = Σ x(l,m)^2
```

Example:

```text
[10,10] → 200
[20,0]  → 400
```

Theoretical Max-Pressure controls the expected drift of this queue measure under feasible demand.

Stable means queues remain bounded in time-average expectation, not that queues become zero.

## Decentralization

The pressure objective can be decomposed by intersection, allowing local controllers to make decisions from adjacent queues while still producing network-level behavior.

## Two-Intersection Example

```text
A 🚦 ─── Link AB ─── 🚦 B ─── C
```

Initially:

```text
queue before A = 30
queue on AB = 5
pressure ≈ 25
```

If downstream congestion grows:

```text
AB queue = 28
pressure ≈ 2
```

so A becomes less likely to release more traffic toward B.

## Finite Storage Problem

Theoretical `x(l,m)` is not the same as physical available storage.

A 100 m road may physically fill long before an abstract queue model becomes problematic.

## Link-Length Problem

```text
50 m road, 10 queued vehicles  → nearly full
500 m road, 10 queued vehicles → relatively empty
```

Raw queue count treats both as `10`, motivating normalized/capacity-aware variants.

## Shared-Lane Problem

A shared lane may serve multiple movements:

```text
← ↑
```

Measured lane queue may be 10 vehicles while original Max-Pressure requires movement-specific queues.

### MP-D04

> Any implementation labeled “Original Max-Pressure” must explicitly document how `x(l,m)`, `r(m,p)`, `c(l,m)`, and legal signal stages are represented.

### MP-D06

> Substituting lane/edge totals for movement-oriented queues must be treated as a modified formulation rather than silently assumed equivalent.

---

# Part XI — Updated Hypothesis Status

| ID | Hypothesis | Current Status |
|---|---|---|
| MP-H01 | Max-Pressure may provide a strong network-aware baseline without RL training. | Strongly supported; retain for empirical validation. |
| MP-H02 | Standard queue-differential pressure may not fully represent finite storage/spillback. | Strongly supported. |
| MP-H03 | Practical performance may depend strongly on queue definition, link length, turn ratios, and phase constraints. | Increasingly supported. |
| MP-H04 | Meaningful RL contribution may require improvement beyond standard Max-Pressure under realistic constraints. | Open. |
| MP-H05 | Hybrid designs may be more defensible than pure RL if Max-Pressure provides a strong backbone. | Open. |

# Part XII — Updated Decision Register

| ID | Decision Candidate |
|---|---|
| MP-D01 | Treat Max-Pressure as a serious candidate network-aware classical baseline. |
| MP-D02 | Do not equate standard downstream queue awareness with full physical spillback awareness. |
| MP-D03 | Use the same legal signal-transition/safety layer for Max-Pressure and learned controllers where possible. |
| MP-D04 | Explicitly document `x(l,m)`, `r(m,p)`, `c(l,m)`, and legal stages for Original Max-Pressure. |
| MP-D05 | Do not misuse theoretical throughput-optimality as a guarantee of minimum delay/waiting or best finite-simulation throughput. |
| MP-D06 | Treat lane/edge-aggregate substitutions for movement queues as modified Max-Pressure formulations. |
| MP-D07 | Distinguish local-information control from locally optimized control. |

# Part XIII — Next Research Direction

## Finite-Capacity / Spillback-Aware Max-Pressure

Next questions:

1. How do finite link-storage constraints change the original assumptions?
2. What happens when downstream links are physically full?
3. How should queue normalization and link length affect pressure?
4. Which variants explicitly model downstream capacity?
5. How should spillback be represented?
6. How do shared lanes alter pressure calculation?
7. Should CADENCE use vehicle count, queue length, occupancy, or available storage?
8. How should switching losses and minimum green be handled?
9. Which practical Max-Pressure variant is the fairest SUMO baseline?
10. Where might RL still add measurable value?

---

# Part XIV — Research Result: Finite-Capacity / Spillback-Aware Max-Pressure

## Finite Physical Storage

Original Max-Pressure theory uses abstract queues that do not automatically enforce the physical storage limit of a road segment.

A real link has finite storage determined by factors such as:

- lane length,
- vehicle length,
- minimum jam gap,
- number of lanes,
- vehicle mix.

Therefore CADENCE must distinguish:

```text
Flow Capacity
→ vehicles per unit time

Storage Capacity
→ vehicles / physical road space
```

### Decision Candidate MP-D08

> CADENCE must distinguish traffic flow capacity from physical link storage capacity.

## Why Raw Queue Count Is Not Enough

Two links can have the same queue count but very different physical congestion.

Example:

```text
Link A
50 m
8 queued vehicles
~89% of storage used

Link B
500 m
8 queued vehicles
~10% of storage used
```

A raw queue-count formulation sees `8 vs 8`, while the physical network states are very different.

## Downstream Congestion vs Downstream Fullness

These are not equivalent.

```text
storage capacity = 20 vehicles
current queue    = 15
remaining storage = 5
```

The link is congested but may still receive traffic.

If current storage reaches capacity, new inflow can create:

- junction blocking,
- upstream spillback,
- secondary congestion.

## Available Storage

A useful conceptual quantity is:

```text
Available Storage
=
Storage Capacity
-
Current Storage
```

A normalized form is:

```text
Available Storage Ratio
=
1 - Current Storage / Storage Capacity
```

Interpretation:

```text
~1.0 → mostly empty
~0.0 → physically full
```

This is relevant to CADENCE, but is not automatically the Original Max-Pressure state definition.

## Normalized Queue

Another possible representation is:

```text
q_norm = q / q_max
```

Changing the pressure definition means the Original Max-Pressure stability result must not automatically be assumed to apply.

### Decision Candidate MP-D10

> Theoretical guarantees from Original Max-Pressure must not be attributed automatically to modified pressure formulations unless supported by the corresponding theory or literature.

## Occupancy as Physical Congestion State

Occupancy can represent downstream fullness in normalized form.

However, an occupancy-based pressure controller is not mathematically identical to Original Max-Pressure and must be described as modified/capacity-aware.

## Travel-Time-Based Max-Pressure

Later Max-Pressure research has explored travel-time-based pressure rather than relying only on raw queue count.

Potential advantages:

- captures spatial congestion better,
- reflects severe congestion,
- may be measurable using travel-time sensing.

Potential limitations:

- delayed observations,
- sparse/noisy measurements,
- different sensor assumptions.

## Spillback-Aware Green Duration

Finite storage creates an additional constraint on useful green time.

A network-aware controller may need to reason about:

```text
remaining storage
+
expected inflow
+
simultaneous downstream outflow
```

rather than only assigning a pressure score.

## Dynamic Storage Balance

Downstream storage evolves as:

```text
Storage(t+1)
=
Storage(t)
+
Inflow
-
Outflow
```

This helps explain why predictive/model-based methods such as MPC become relevant.

## Shockwave Concept

A traffic shockwave is the moving boundary between traffic states, such as free-flow traffic and a stopped queue.

Shockwave-based estimation can help predict when a queue will reach an upstream intersection.

CADENCE does not currently need to implement a shockwave estimator because SUMO provides microscopic state directly.

## Observation Fidelity

Controller comparisons must distinguish simulator-perfect information from sensor-realistic information.

### O0 — Omniscient Simulator State
- exact vehicle positions,
- exact routes/turn intentions,
- precise movement queues.

### O1 — Lane-Level Virtual Detection
- vehicle count,
- halting count,
- occupancy,
- virtual detector measurements.

### O2 — Estimated Traffic State
- estimated queues,
- estimated turn ratios,
- estimated travel times.

### O3 — Real Sensor-Like Observation
Observation constrained by a defined real deployment sensor model.

### Decision Candidate MP-D09

> Controller comparisons should explicitly document observation fidelity; controllers should not receive materially different levels of simulator omniscience without justification.

## Shared Lanes and FIFO Blocking

A lane may support multiple movements:

```text
↑ + →
```

A blocked vehicle at the front of the lane can prevent following vehicles from using otherwise free downstream movements.

Thus independent movement queues can diverge from physical lane-level FIFO/blocking behavior.

## Nominal vs Effective Saturation Flow

Original Max-Pressure uses a movement service/saturation parameter such as `c(l,m)`.

Actual discharge can be reduced by:

- downstream blocking,
- turning conflicts,
- shared-lane obstruction,
- vehicle heterogeneity,
- lane changes,
- heavy vehicles.

Therefore CADENCE should distinguish nominal saturation flow from effective discharge rate under current conditions.

## Cyclic vs Acyclic Max-Pressure

### Acyclic Max-Pressure
Selects whichever legal stage currently has the highest pressure.

Potential advantages:
- high responsiveness.

Potential drawbacks:
- unpredictable phase order,
- fairness concerns,
- excessive switching.

### Cyclic Max-Pressure
Follows a predefined phase order but adapts service/timing according to pressure.

Potential advantages:
- predictable,
- easier fairness/service guarantees.

Potential drawback:
- may delay urgent movements or serve unnecessary phases.

## Multi-Layer Network Protection

Max-Pressure can also be combined with higher-level strategies such as perimeter control.

This suggests multiple network-awareness scales:

```text
Level 1 — Downstream-Aware
Level 2 — Neighbor-Aware
Level 3 — Region-Aware
Level 4 — Global Network-Aware
```

## Pressure-State Families

Potential practical pressure families include:

### A. Raw Queue
```text
q_up - q_down
```

### B. Normalized Queue
```text
q_up / capacity_up
-
q_down / capacity_down
```

### C. Available-Storage-Aware
```text
upstream demand × downstream available-storage factor
```

### D. Travel-Time-Based
Pressure based on upstream/downstream travel-time conditions.

### E. Delay-Based
Pressure based on movement delay rather than queue count.

No formulation is selected yet.

## Practical Baseline Scope

A strong but manageable baseline ladder could be:

```text
1. Tuned Fixed-Time
2. SUMO Native Actuated
3. Clearly Documented Original / Queue-Based Max-Pressure
4. One Justified Practical Capacity-Aware Max-Pressure Variant
5. CADENCE Proposed Controller
```

### Decision Candidate MP-D12

> CADENCE should benchmark one well-defined Original/queue-based Max-Pressure implementation and one justified practical capacity-aware variant rather than attempting to reproduce every Max-Pressure variant.

## Practical Capacity-Aware Variant Shortlist

### Candidate A — Normalized / Capacity-Aware Queue MP
Advantages:
- simple to implement in SUMO,
- close to queue-based semantics,
- directly reflects finite storage.

### Candidate B — Travel-Time MP
Advantages:
- strong practical motivation,
- naturally reflects severe congestion,
- real-world measurement story.

Limitations:
- delayed/noisy state,
- more complex observation semantics.

### Candidate C — Lane-Structured Enhanced Queue MP
Advantages:
- addresses shared lanes and service-rate effects.

Limitations:
- more complex,
- higher implementation effort,
- newer formulation.

No candidate is selected yet.

## Physical Spillback Baseline Requirement

### Decision Candidate MP-D11

> A practical network-aware baseline for CADENCE should include at least one state representation that reflects finite downstream storage or physical congestion severity.

# Part XV — Updated Hypothesis Status

| ID | Hypothesis | Current Status |
|---|---|---|
| MP-H01 | Max-Pressure may provide a strong network-aware baseline without RL training. | Strongly supported; empirical validation still required. |
| MP-H02 | Standard queue-differential pressure may not fully represent finite storage/spillback. | Strongly supported / effectively confirmed as a limitation of the original model. |
| MP-H03 | Practical performance may depend strongly on queue definition, link length, turn ratios, and phase constraints. | Strongly supported. |
| MP-H04 | Meaningful RL contribution may require improvement beyond standard Max-Pressure under realistic constraints. | Open. |
| MP-H05 | Hybrid designs may be more defensible than pure RL if Max-Pressure provides a strong backbone. | Increasing evidence, but still open. |

# Part XVI — Extended Decision Register

| ID | Decision Candidate |
|---|---|
| MP-D01 | Treat Max-Pressure as a serious candidate network-aware classical baseline. |
| MP-D02 | Do not equate standard downstream queue awareness with full physical spillback awareness. |
| MP-D03 | Use the same legal signal-transition/safety layer for Max-Pressure and learned controllers where possible. |
| MP-D04 | Explicitly document `x(l,m)`, `r(m,p)`, `c(l,m)`, and legal stages for Original Max-Pressure. |
| MP-D05 | Do not misuse theoretical throughput-optimality as a guarantee of minimum delay/waiting or best finite-simulation throughput. |
| MP-D06 | Treat lane/edge-aggregate substitutions for movement queues as modified Max-Pressure formulations. |
| MP-D07 | Distinguish local-information control from locally optimized control. |
| MP-D08 | Distinguish flow capacity from physical storage capacity. |
| MP-D09 | Explicitly document observation fidelity and avoid unfair simulator-omniscience differences between controllers. |
| MP-D10 | Do not transfer Original Max-Pressure theoretical guarantees automatically to modified pressure formulations. |
| MP-D11 | Include at least one practical state representation that reflects finite downstream storage or congestion severity. |
| MP-D12 | Limit baseline scope to one well-defined Original/queue-based MP and one justified practical capacity-aware variant. |

# Part XVII — Research Checkpoint Summary

The Max-Pressure research has now established three layers:

```text
Original Theory
    ↓
movement queue differential
turn ratios
service rates
stability / throughput-optimality

Practical Mapping
    ↓
movement queue semantics
shared lanes
signal constraints
measurement fidelity

Physical Network Reality
    ↓
finite storage
link length
spillback
junction blocking
effective discharge
```

The central CADENCE distinction is:

> **Queue balancing and physical congestion propagation are related but not identical problems.**

Original Max-Pressure primarily provides a queue-stability framework.

CADENCE's broader vision emphasizes:

- finite downstream capacity,
- spillback,
- junction blocking,
- congestion propagation,
- real-world road geometry.

# Part XVIII — Next Research Direction

The Max-Pressure foundation is now mature enough to pause detailed variant selection.

The next research track should examine:

# Optimization / Model Predictive Control (MPC)

Key questions:

1. How does optimization-based traffic signal control formulate the network problem?
2. What is Model Predictive Control?
3. What traffic model does MPC require?
4. How does prediction change decisions compared with reactive Max-Pressure?
5. How are finite storage, spillback, and signal constraints represented?
6. What computational/scalability trade-offs exist?
7. Which MPC/optimization approaches are realistic baselines for CADENCE?
8. Where does RL potentially provide value beyond explicit optimization?
