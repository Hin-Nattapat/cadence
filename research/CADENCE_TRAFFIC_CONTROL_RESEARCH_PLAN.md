# CADENCE — Traffic Control Research Plan

**Formal Project Title:** Network-Aware Adaptive Traffic Signal Control
Using Reinforcement Learning on Real-World Urban Road Networks\
**Project Codename:** CADENCE\
**Document Type:** Master Research Plan / Landscape\
**Status:** Active Master Research Plan

## 1. Purpose

This document defines the research landscape CADENCE should study before
finalizing its traffic-control architecture.

The project originated from a Reinforcement Learning
traffic-signal-control project, but the current research direction
should not assume that RL is automatically the best solution.

Traffic signal control has already been studied across:

-   traffic engineering,
-   control theory,
-   operations research,
-   optimization,
-   adaptive traffic control,
-   artificial intelligence,
-   machine learning,
-   Reinforcement Learning.

> **Document role:** This file is the master map for CADENCE traffic-control research.  
> Detailed findings are kept in focused research files rather than accumulated here.

### Focused Research Files

- `CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` — Traffic engineering, classical signal timing, and actuated control.
- `CADENCE_MAX_PRESSURE_RESEARCH.md` — Max-Pressure / Backpressure control.
- Future focused files may cover Optimization/MPC and AI/RL/MARL as those tracks become substantial.


The central question should therefore be:

> **Given the available traffic-control methods, which problems remain
> difficult, and where can CADENCE provide meaningful additional
> value?**

## 2. Core Principle

> **Do not use AI to rediscover a solution that established traffic
> engineering already solves more simply, safely, and explainably.**

A method should earn its complexity.

## 3. Research Landscape

``` text
Traffic Flow Theory
        ↓
Traffic Engineering
        ↓
Classical Signal Timing
        ↓
Actuated Signal Control
        ↓
Adaptive / Network Signal Control
        ↓
Queue-Based / Max-Pressure Control
        ↓
Optimization / MPC
        ↓
AI / Machine Learning
        ↓
Reinforcement Learning
        ↓
Multi-Agent / Graph-Based Control
```

These tracks are not mutually exclusive. Future CADENCE controllers may
be hybrid systems.

# Part I — Traffic Engineering Foundations

## 4. Traffic Flow Theory

Traffic flow theory studies relationships between:

-   flow,
-   speed,
-   density,
-   capacity,
-   queues,
-   congestion.

A common relationship is:

``` text
flow = speed × density
```

CADENCE needs these fundamentals so observations and rewards remain
consistent with real traffic behavior.

## 5. Saturation Flow

**Saturation flow** is approximately the maximum rate at which a
continuously queued traffic stream can pass through an intersection
while it has effective green.

Typical unit:

``` text
vehicles/hour/lane
```

It is affected by headway, acceleration, geometry, turns, vehicle types,
and driver behavior.

## 6. Lost Time

**Lost time** is signal time that does not contribute effectively to
vehicle discharge.

Examples include:

-   startup reaction,
-   queue startup delay,
-   yellow,
-   clearance.

This matters because excessive phase switching can waste significant
capacity.

## 7. Degree of Saturation

A simplified intuition:

``` text
degree of saturation ≈ demand / capacity
```

Interpretation:

``` text
< 1.0 → below capacity
≈ 1.0 → near capacity
> 1.0 → oversaturated
```

CADENCE should evaluate controllers under multiple saturation regimes.

# Part II — Classical Signal Timing

## 8. Fixed-Time Control

Fixed-time control uses predetermined:

-   cycle length,
-   green split,
-   phase sequence,
-   offset.

Strengths: deterministic, explainable, reproducible.\
Weakness: cannot adapt to unexpected traffic changes.

It remains a baseline, but should not be the strongest benchmark.

## 9. Webster-Type Timing

Webster's method is a classical approach for estimating efficient cycle
length and green allocation for an isolated intersection based on demand
and saturation flow.

CADENCE should understand it because beating a poorly chosen fixed plan
is not a strong RL result.

# Part III — Actuated Control

## 10. Vehicle-Actuated Control

Actuated control uses detectors to adapt phase service.

Typical concepts:

-   minimum green,
-   maximum green,
-   presence detection,
-   detector gap,
-   gap-out,
-   phase skipping.

Simplified:

``` text
phase green
   ↓
vehicles still arriving?
   ├─ yes → extend
   └─ no  → change phase
```

Strengths: adaptive, explainable, no training.\
Weaknesses: often local and limited in explicit network coordination.

**Role in CADENCE:** required baseline.

# Part IV — Adaptive Traffic Signal Control

## 11. Adaptive Control Systems

Adaptive traffic signal control continuously adjusts timing according to
measured traffic.

Historic examples include SCOOT and SCATS.

The important lesson is:

> Traffic-responsive signal control existed long before Deep RL.

CADENCE must therefore define its novelty more specifically than
"adaptive traffic lights".

## 12. Local vs Network-Level Adaptation

**Local adaptation:** reacts mainly to local detectors.\
**Network-level adaptation:** coordinates multiple intersections and
surrounding traffic.

CADENCE increasingly focuses on the second category.

# Part V — Max-Pressure / Backpressure

## 13. Max-Pressure Control

Max-Pressure is a queue-based network-control family.

Simple intuition:

``` text
large upstream queue
+
available downstream capacity
→ strong reason to serve movement
```

versus:

``` text
large upstream queue
+
full downstream link
→ releasing traffic may be harmful
```

It is important because it is:

-   adaptive,
-   network-aware,
-   training-free,
-   relatively interpretable.

A dedicated research session should cover its mathematics, assumptions,
stability properties, spillback behavior, and limitations.

# Part VI — Optimization and MPC

## 14. Mathematical Optimization

Traffic signals can be controlled using methods such as:

-   LP,
-   MILP,
-   nonlinear optimization,
-   dynamic programming,
-   metaheuristics.

Decision variables may include:

-   phase timing,
-   green splits,
-   offsets,
-   phase sequence.

Strengths: explicit objectives and constraints.\
Weaknesses: computational/model complexity.

## 15. Model Predictive Control (MPC)

MPC repeatedly:

1.  observes current traffic,
2.  predicts future traffic,
3.  optimizes future actions,
4.  executes the first action,
5.  repeats.

``` text
Current Traffic
      ↓
Predict Future
      ↓
Optimize
      ↓
Execute First Decision
      ↓
Observe Again
```

Strengths: future-aware, constraint-friendly.\
Weaknesses: requires a model and can be computationally expensive.

# Part VII — AI and Machine Learning

## 16. AI Without RL

ML may support traffic control without directly controlling signals.

Examples:

-   traffic-flow prediction,
-   queue prediction,
-   travel-time estimation,
-   incident detection,
-   demand forecasting,
-   learned traffic models.

## 17. Fuzzy / Rule-Based AI

Example:

``` text
IF north_queue is HIGH
AND east_queue is LOW
THEN extend north_green
```

Strengths: interpretable, expert knowledge can be encoded.\
Weakness: rule complexity grows quickly.

# Part VIII — Reinforcement Learning

## 18. Reinforcement Learning

RL learns through interaction:

``` text
Observation
    ↓
Agent
    ↓
Action
    ↓
Environment
    ↓
Reward
    ↓
Policy Update
```

Potential benefits:

-   nonlinear policies,
-   long-term optimization,
-   complex state spaces,
-   network coordination.

Risks:

-   reward-design errors,
-   poor generalization,
-   unsafe actions,
-   training instability,
-   simulator exploitation,
-   weaker interpretability.

## 19. Deep RL

Relevant future algorithm families may include:

-   DQN,
-   PPO,
-   A2C/A3C,
-   SAC,
-   actor-critic variants.

CADENCE should not choose an algorithm until observation, action,
safety, baselines, and evaluation are defined.

# Part IX — Multi-Agent RL

## 20. MARL

Multiple agents may control different intersections.

``` text
Agent A → Intersection A
Agent B → Intersection B
Agent C → Intersection C
```

Potential advantages: natural fit for distributed networks.\
Difficulties: non-stationarity, coordination, credit assignment,
scalability, reproducibility.

This should remain a later-stage direction.

# Part X — Graph-Based Control

## 21. Graph Representation

Road networks naturally form graphs:

``` text
Intersection = node
Road = edge
```

Graph Neural Networks may later support:

-   message passing,
-   shared representation,
-   policy transfer,
-   scalability across topology.

# Part XI — Hybrid Controllers

## 22. Hybrid Control

CADENCE should not assume a pure-RL final architecture.

Possible combinations:

``` text
Max-Pressure + RL timing optimization
```

``` text
Traffic prediction + MPC
```

``` text
RL + hard safety constraints
```

``` text
Classical local control + RL network coordinator
```

Hybrid approaches may improve safety, stability, interpretability, and
sample efficiency.

# Part XII — Comparison Framework

## 23. Questions for Every Method

For each control family, ask:

1.  **What does it observe?**
2.  **What does it control?**
3.  **What does it optimize?**
4.  **Where does it fail?**

## 24. Initial Comparison Matrix

  -------------------------------------------------------------------------------------------------------------------------
  Method           Adaptive   Network-Aware   Downstream-Aware   Training   Explainability Main Limitation
  -------------- ---------- --------------- ------------------ ---------- ---------------- --------------------------------
  Fixed-Time             No              No                 No       None             High Cannot react to traffic changes

  Actuated              Yes   Usually local            Limited       None             High Limited coordination

  Adaptive              Yes             Yes            Depends       None     Medium--High System/model complexity
  Network                                                                                  
  Control                                                                                  

  Max-Pressure          Yes             Yes                Yes       None             High Queue/state assumptions

  Optimization /        Yes             Yes                Yes      Model             High Computational/model complexity
  MPC                                                            required                  

  Rule/Fuzzy AI         Yes        Possible           Possible      No RL     Medium--High Rule scalability

  RL                    Yes        Possible           Possible        Yes            Lower Training/generalization/safety

  MARL                  Yes             Yes           Possible        Yes              Low Coordination/training complexity
  -------------------------------------------------------------------------------------------------------------------------

This matrix is a scaffold and should be refined during detailed
research.

# Part XIII — Implications for CADENCE

## 25. Research Contribution Must Be Earned

A weak result:

``` text
Arbitrary Fixed-Time vs RL
```

A stronger progression:

``` text
Tuned Fixed-Time
      ↓
Actuated
      ↓
Network-Aware Classical
      ↓
Optimization / Max-Pressure
      ↓
RL / Hybrid
```

The stronger the baseline, the stronger the research claim.

## 26. CADENCE May Not End as Pure RL

Possible outcomes:

-   **Pure RL** --- RL clearly provides the best solution.
-   **Hybrid** --- classical control provides stability/safety while RL
    improves selected decisions.
-   **Classical network control** --- methods such as Max-Pressure solve
    the core problem better.
-   **RL as benchmark only** --- useful comparison but not preferred
    engineering solution.

All are scientifically acceptable.

# Part XIV — Research Roadmap

## 27. Proposed Research Order

``` text
1. Traffic Engineering Fundamentals
2. Classical Signal Timing
3. Actuated Control
4. Adaptive Network Control
5. Max-Pressure / Backpressure
6. Optimization / MPC
7. AI / ML Approaches
8. RL Literature
9. MARL / Graph-Based Control
10. CADENCE Controller Architecture
```

This is targeted research, not a full transportation-engineering
curriculum.

# Part XV — Current Research Track

## 28. Max-Pressure / Backpressure Control

Detailed research for this track is maintained in `CADENCE_MAX_PRESSURE_RESEARCH.md`.


Questions:

1.  What is traffic pressure mathematically?
2.  How are upstream/downstream queues represented?
3.  How does Max-Pressure choose phases?
4.  Why does it have network-stability properties?
5.  What assumptions does it make?
6.  Does it naturally prevent spillback?
7.  What happens when downstream links are physically full?
8.  Which Max-Pressure variants matter?
9.  How does it compare with actuated control?
10. What exactly would RL need to improve beyond it?

# Initial Reference Directions

Detailed references will be added during each research session.

Primary categories:

-   transportation engineering literature,
-   FHWA traffic-signal guidance,
-   SUMO traffic-light documentation,
-   adaptive traffic signal control literature,
-   Max-Pressure/backpressure papers,
-   MPC traffic-control literature,
-   recent RL traffic-signal-control surveys and benchmark papers.

------------------------------------------------------------------------

> **CADENCE should compare methods by the traffic problem they solve,
> not by how modern or sophisticated the algorithm appears.**

Complexity should be introduced only when evidence shows that simpler
methods are insufficient.

---
