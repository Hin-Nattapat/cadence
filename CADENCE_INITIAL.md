# CADENCE

## Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks

**Project Codename:** CADENCE\
**Document Type:** Initial Research & Engineering Direction\
**Status:** Initial Draft\
**Primary Domain:** Adaptive Traffic Signal Control, Microscopic Traffic
Simulation, Reinforcement Learning

------------------------------------------------------------------------

## 1. Project Overview

**CADENCE** is the codename for a research and engineering project
investigating adaptive traffic signal control on real-world urban road
networks.

The project revisits an earlier university graduation project,
`Reinforcement_Traffic_Project`, developed approximately five to six
years ago. The original work explored Reinforcement Learning (RL) for
traffic signal control using SUMO and TraCI. Although the project
demonstrated the core concept, limitations in the original simulation
design, traffic-state representation, controller design, and
implementation prevented the system from achieving the intended result.

CADENCE is not intended to be a direct rewrite of that implementation.

Instead, the project will rebuild the research environment from first
principles using current engineering knowledge, modern RL tooling, and a
stronger understanding of microscopic traffic simulation.

The primary research direction is:

> **Network-aware adaptive traffic signal control using realistic
> traffic simulation, real-world road topology, and reinforcement
> learning, with particular attention to downstream congestion,
> spillback, and network-level gridlock.**

------------------------------------------------------------------------

## 2. Naming

### 2.1 Formal Project Title

**Network-Aware Adaptive Traffic Signal Control Using Reinforcement
Learning on Real-World Urban Road Networks**

This title should be used in formal documentation, research discussions,
academic communication, and material presented to academic advisors.

### 2.2 Project Codename

**CADENCE**

CADENCE is intentionally a codename rather than an academic acronym.

The name represents the concept of **rhythm, timing, and coordinated
movement**. In the context of traffic control, the system is not merely
switching traffic lights; it is attempting to regulate the cadence of
vehicle movement across an interconnected road network.

Technical components, variables, modules, and research terminology
should continue to use established traffic-engineering and
machine-learning terminology rather than CADENCE-specific terminology.

------------------------------------------------------------------------

## 3. Background

The original university project investigated Reinforcement Learning for
adaptive traffic signal control.

Its implementation already included several useful foundations:

-   SUMO microscopic traffic simulation,
-   TraCI-based traffic-light control,
-   fixed-time traffic signal baselines,
-   reinforcement-learning-based controllers,
-   multi-intersection synthetic networks,
-   traffic measurements such as waiting time, queue length, flow,
    speed, and density.

However, several limitations became apparent when the system was scaled
beyond simple scenarios.

The most significant observed issue was **deadlock/gridlock behavior in
larger synthetic grid networks**.

The new project therefore begins from the assumption that improving the
RL algorithm alone is insufficient.

Before developing an adaptive controller, the project must establish
that the underlying simulation behaves credibly.

------------------------------------------------------------------------

## 4. Core Research Principle

### Simulator First, Controller Second

The central engineering principle of CADENCE is:

> **Do not optimize an environment that has not yet been validated.**

Reinforcement Learning optimizes behavior against the environment and
reward function it is given.

If the simulation contains unrealistic road topology, incorrect junction
behavior, artificial deadlocks, unrealistic vehicle behavior, or hidden
simulator interventions, an RL agent may learn to exploit those
artifacts rather than learn meaningful traffic-control behavior.

Therefore, the first major milestone of CADENCE is not an RL model.

It is a **validated Simulation Foundation**.

------------------------------------------------------------------------

## 5. Research Objective

The initial objective is to construct a reproducible microscopic traffic
simulation environment capable of representing real-world road networks
and realistic congestion behavior.

Once this environment is validated, the project will investigate
adaptive traffic signal control.

The eventual controller should reason beyond isolated intersection
demand.

A central question is:

> **What will happen to the surrounding road network if this
> intersection releases these vehicles now?**

This introduces the concept of **network-aware traffic control**.

Rather than optimizing only the incoming queue of an intersection,
future controllers should account for downstream road capacity and the
effect of local decisions on neighboring intersections.

------------------------------------------------------------------------

## 6. Proposed System Architecture

``` text
                         Real World
                             │
                  ┌──────────┴──────────┐
                  │                     │
               Map Data            Traffic Data
                  │                     │
                  ↓                     ↓
           Network Builder      Demand / Calibration
                  │                     │
                  └──────────┬──────────┘
                             ↓
                     SUMO Environment
                             │
             ┌───────────────┼───────────────┐
             │               │               │
       Car-Following    Lane-Changing     Junction /
          Behavior         Behavior       TLS Behavior
             │               │               │
             └───────────────┴───────────────┘
                             ↓
                     Validated Traffic
                             │
                  ┌──────────┴──────────┐
                  │                     │
            Baseline Control      Adaptive Control
                  │                     │
          Fixed / Actuated           RL / MARL
                  │                     │
                  └──────────┬──────────┘
                             ↓
                    Evaluation Layer
```

The architecture should maintain clear separation between:

-   network generation,
-   traffic demand,
-   vehicle behavior,
-   signal-control logic,
-   observations,
-   controller actions,
-   signal safety constraints,
-   reward calculation,
-   metrics,
-   experiment configuration,
-   evaluation.

------------------------------------------------------------------------

## 7. Real-World Road Networks

The original project primarily used synthetic grid networks.

CADENCE will move toward **real-world road topology**.

OpenStreetMap (OSM) is the initial candidate source for road-network
data, while SUMO will remain the primary microscopic traffic simulator.

SUMO supports native OSM import through `netconvert` and provides
tooling such as `osmWebWizard.py` for generating simulation scenarios.

A target workflow is:

``` text
Selected Geographic Area
        ↓
Acquire OSM Data
        ↓
Network Conversion
        ↓
Network Preprocessing
        ↓
Junction Validation
        ↓
Traffic-Light Validation
        ↓
Route / Demand Generation
        ↓
Simulation Scenario
```

Importing an OSM network should not be considered sufficient validation.

SUMO documentation explicitly notes that imported networks commonly
require correction or enhancement, including roads, turns, lane counts,
and traffic lights. Network deficiencies can manifest as unrealistic
congestion or vehicle teleportation.

Therefore, **network validation is a first-class component of the
project**.

------------------------------------------------------------------------

## 8. Real-World Network Development Strategy

Real-world topology introduces important complexity absent from regular
synthetic grids:

-   unequal road lengths,
-   unequal lane counts,
-   turning lanes,
-   one-way roads,
-   irregular intersections,
-   offset intersections,
-   asymmetric traffic demand,
-   different road capacities,
-   heterogeneous signal programs.

The project should scale incrementally:

``` text
Synthetic Single Intersection
        ↓
Real-World Single Intersection
        ↓
Real-World Corridor
(approximately 3–5 signals)
        ↓
Small Real-World District
(approximately 10–30 signals)
        ↓
Larger Urban Network
```

The project should **not begin with an entire city**.

Small real-world networks provide sufficient complexity for meaningful
research while remaining observable and debuggable.

------------------------------------------------------------------------

## 9. Deadlock and Gridlock

The original project experienced deadlock behavior when scaling to
larger grid networks.

In CADENCE, two different phenomena must be distinguished.

### 9.1 Artificial Simulation Deadlock

Artificial deadlock may result from defects or inappropriate assumptions
in the simulation environment.

Potential causes include:

-   incorrect lane connections,
-   short intermediate edges,
-   incorrectly separated junctions,
-   invalid or unrealistic traffic-light programs,
-   route-generation errors,
-   unrealistic lane-changing behavior,
-   inappropriate network-conversion settings.

These should be treated as **simulation defects** and corrected before
controller evaluation.

### 9.2 Real Traffic Gridlock

A different situation occurs when congestion propagates through the
network until downstream links no longer have capacity.

For example:

``` text
J1 → J2 → J3
↑         ↓
J6 ← J5 ← J4
```

If every intersection continues releasing vehicles into already
saturated downstream links, queues may propagate upstream until the
network becomes blocked.

This represents a legitimate traffic-control problem.

It should not simply be removed from the simulator.

The controller should eventually detect and respond to the conditions
that lead to this state.

------------------------------------------------------------------------

## 10. Spillback

**Spillback** occurs when congestion on a downstream link grows far
enough upstream to interfere with upstream intersections.

This concept is expected to become important to CADENCE.

A controller that observes only its own incoming queues may make a
locally reasonable but globally harmful decision.

For example:

``` text
Large incoming queue
        ↓
Controller releases vehicles
        ↓
Downstream road is already saturated
        ↓
Vehicles cannot clear the intersection
        ↓
Queue propagates upstream
        ↓
Network performance deteriorates
```

Future observations may therefore include:

``` text
Incoming:
- queue length
- waiting time
- occupancy
- arrival rate

Intersection:
- current signal phase
- elapsed phase time

Downstream:
- occupancy
- queue length
- available capacity
```

This changes the controller's objective from:

> Which direction currently has the most traffic?

toward:

> Which movement can be served without creating harmful downstream
> congestion?

------------------------------------------------------------------------

## 11. Vehicle Behavior

A major Simulation Foundation workstream will be the study and
calibration of SUMO vehicle behavior.

SUMO is a microscopic simulator in which individual vehicle behavior is
affected by multiple behavioral models and parameters.

### 11.1 Car-Following Behavior

Car-following models govern how vehicles respond to leading vehicles.

Relevant concepts include:

-   acceleration,
-   deceleration,
-   desired following gap,
-   minimum gap,
-   reaction behavior,
-   desired speed.

SUMO currently uses the modified **Krauss** model as its default
car-following model and supports alternative models.

The `actionStepLength` parameter can also separate the simulation step
length from the frequency of driver decision-making.

### 11.2 Lane-Changing Behavior

Lane-changing behavior influences:

-   route preparation,
-   strategic lane selection,
-   cooperation,
-   speed-gain lane changes,
-   lane preference,
-   bottleneck formation near junctions.

SUMO currently uses **LC2013** as its default lane-changing model.

These behaviors may have substantial effects on queue formation,
discharge rate, intersection capacity, and spillback.

They therefore cannot be treated as purely cosmetic simulation details.

------------------------------------------------------------------------

## 12. Driver Heterogeneity

Real drivers do not behave identically.

A future version of the environment may model multiple behavioral
profiles, conceptually such as:

``` text
Aggressive
- smaller preferred gap
- stronger acceleration
- more frequent lane changes

Normal
- calibrated baseline behavior

Conservative
- larger preferred gap
- lower acceleration
- less aggressive lane changing
```

These profiles must eventually be based on defensible parameters or
empirical calibration.

The initial Simulation Foundation should begin with controlled SUMO
defaults and introduce heterogeneity only after baseline behavior is
understood.

------------------------------------------------------------------------

## 13. Calibration

Real-world map geometry alone does not create a realistic traffic
simulation.

CADENCE should eventually contain a dedicated calibration process.

Possible calibration targets include:

-   traffic volume,
-   queue length,
-   average travel time,
-   intersection discharge rate,
-   lane utilization,
-   speed distribution,
-   route distribution,
-   congestion propagation.

Potential calibration parameters include:

-   demand volume,
-   route choice,
-   vehicle-type distribution,
-   car-following parameters,
-   lane-changing parameters,
-   signal timing.

Full automatic calibration is not required initially.

The first requirement is that all important assumptions are **explicit,
configurable, measurable, and reproducible**.

------------------------------------------------------------------------

## 14. Simulation Foundation --- Definition of Done

Before significant RL training begins, the simulation layer should
satisfy the following criteria:

-   OSM-derived networks can be generated reproducibly.
-   Road and lane topology can be inspected and validated.
-   Turning connections are correct.
-   Signalized intersections are correctly represented.
-   Traffic-light programs are understandable and controllable.
-   Vehicles generate valid routes.
-   Queues form and discharge plausibly.
-   Lane-changing behavior does not introduce obvious artificial
    bottlenecks.
-   Downstream congestion can produce spillback.
-   Artificial topology-related deadlocks can be identified.
-   Genuine demand-induced gridlock remains possible.
-   SUMO vehicle teleportation behavior is explicitly configured and
    logged.
-   Random seeds can reproduce experiment conditions.
-   Traffic metrics are collected consistently.
-   Fixed-time control produces stable and explainable behavior.

------------------------------------------------------------------------

## 15. Lessons from the Original Project

The original implementation should be preserved as a historical baseline
rather than directly evolved into the new architecture.

### 15.1 Traffic-State Representation

The previous implementation represented state too closely around
controller-selected movements rather than describing the complete
traffic condition.

The new architecture should explicitly separate:

``` text
SUMO Environment State
        ↓
Observation Builder
        ↓
Controller Observation
```

### 15.2 Reinforcement Learning vs Heuristic Logic

The original implementation combined RL decisions with heuristic logic
for selecting movements and calculating signal duration.

In CADENCE, controller responsibilities should be explicit.

``` text
Observation
    ↓
Controller
    ↓
Requested Action
    ↓
Signal Constraint / Safety Layer
    ↓
Executed Signal Transition
```

Heuristic control remains valuable, but it should exist as an explicit
baseline controller rather than being hidden inside RL behavior.

### 15.3 Reward Design

The first reward function should remain interpretable.

A conceptual starting point is:

``` text
reward =
    - α × queue_length
    - β × waiting_time
    - γ × stops
```

Potential later terms include:

-   throughput,
-   spillback penalty,
-   downstream blocking,
-   phase-switch penalty,
-   fairness,
-   maximum waiting time.

Reward complexity should only increase when experiments justify it.

### 15.4 Temporal Metrics

RL observations and rewards should primarily use current measurements or
bounded time windows rather than cumulative averages from the beginning
of an episode.

Examples include:

``` text
queue length now
lane occupancy now
vehicles passed during the last Δt
waiting accumulated during the last Δt
```

### 15.5 Network Coordination

The original project already experimented with multiple intersections,
but neighboring intersection state was not fully represented.

Future network-level control should make downstream and neighboring
state explicit.

------------------------------------------------------------------------

## 16. Traffic Signal Controller

The RL agent should not be responsible for learning fundamental
traffic-signal safety rules through trial and error.

A proposed controller architecture is:

``` text
Traffic Observation
        ↓
Control Policy
        ↓
Requested Action
        ↓
Signal Constraint / Safety Layer
        ↓
Legal Signal Transition
        ↓
SUMO
```

The safety layer may enforce:

-   minimum green duration,
-   yellow transition,
-   all-red clearance where required,
-   incompatible movement prevention,
-   valid phase transitions.

This allows the learning algorithm to focus on **traffic optimization**
rather than signal legality.

------------------------------------------------------------------------

## 17. Initial Observation Space

The exact observation design remains a research question.

A candidate single-intersection observation may include:

### Incoming Lanes

-   queue length,
-   lane occupancy,
-   mean speed,
-   waiting time,
-   arriving vehicle count.

### Intersection State

-   current signal phase,
-   elapsed phase time.

### Outgoing / Downstream Lanes

-   occupancy,
-   queue length,
-   available capacity.

Normalization must account for differences such as lane length and road
capacity.

------------------------------------------------------------------------

## 18. Initial Action Space

The first RL action space should remain intentionally small.

A possible initial action set is:

``` text
KEEP_CURRENT_PHASE
REQUEST_NEXT_PHASE
```

The environment's signal constraint layer would then execute the legal
transition.

Future versions may investigate:

``` text
SELECT_PHASE
EXTEND_GREEN
```

Arbitrary continuous green-time control should not be introduced until
simpler action spaces are well understood.

------------------------------------------------------------------------

## 19. Initial Reward Direction

A candidate conceptual reward is:

``` text
reward =
    - queue_penalty
    - waiting_penalty
    - spillback_penalty
    - unnecessary_switch_penalty
```

Potential positive terms may include throughput or completed trips.

The reward function must be evaluated for unintended incentives and
should remain explainable.

------------------------------------------------------------------------

## 20. Baseline Controllers

RL performance must be compared against meaningful baselines.

### 20.1 Fixed-Time Controller

A deterministic signal program.

This provides the simplest reproducible baseline.

### 20.2 Actuated / Heuristic Controller

A traffic-responsive controller using explicit traffic measurements.

Conceptually:

``` text
if current movement still has demand
and downstream capacity is available
and maximum green has not been reached:
    extend green
else:
    transition to another movement
```

This is an important baseline because a well-designed heuristic
controller may already perform strongly.

### 20.3 Historical Controller

Where practical, the original project's controller may be preserved or
ported as a historical comparison.

The project evolution could then be evaluated as:

``` text
Fixed-Time Control
        ↓
Original Project Controller
        ↓
Modern Single-Agent RL
        ↓
Network-Aware RL
        ↓
Multi-Intersection Coordination
```

------------------------------------------------------------------------

## 21. Evaluation Metrics

No single metric should define controller success.

Candidate metrics include:

-   average waiting time,
-   P95 waiting time,
-   maximum waiting time,
-   average delay,
-   average queue length,
-   maximum queue length,
-   throughput,
-   completed trips,
-   travel time,
-   number of stops,
-   spillback events,
-   teleport events,
-   gridlock events.

This is important because optimizing a network-wide average can hide
severe starvation for a minority of vehicles or approaches.

------------------------------------------------------------------------

## 22. Generalization

A controller should not be considered successful merely because it
performs well on the traffic distribution used during training.

Evaluation should include unseen conditions.

Example scenario families:

``` text
A — Uniform demand

B — North/South dominant demand

C — East/West dominant demand

D — Rush-hour transition

E — Sudden traffic surge

F — Temporary downstream congestion

G — Randomized traffic demand

H — Driver-behavior variation
```

Training and evaluation scenarios should remain explicitly separated.

------------------------------------------------------------------------

## 23. Initial Success Criterion

The first meaningful RL milestone is:

> **An adaptive controller consistently outperforms fixed-time and
> actuated baselines across multiple unseen traffic-demand scenarios
> without increasing pathological network behavior.**

Evaluation should compare multiple metrics rather than relying on a
single reward value.

No fixed percentage improvement should be committed until the simulator
and baseline controllers are validated.

------------------------------------------------------------------------

## 24. Development Roadmap

### Phase 0 --- Simulation Foundation

Research and implement:

-   current SUMO capabilities,
-   OSM acquisition and import,
-   network preprocessing,
-   junction validation,
-   traffic-light validation,
-   routing,
-   traffic-demand generation,
-   vehicle behavior,
-   deadlock diagnosis,
-   gridlock behavior,
-   teleport handling,
-   calibration,
-   metrics,
-   reproducibility.

**Deliverable:** A validated real-world SUMO scenario operating without
RL.

### Phase 1 --- Single-Intersection Control

Implement:

-   controller interface,
-   observation builder,
-   action layer,
-   signal safety/constraint layer,
-   fixed-time baseline,
-   actuated baseline,
-   first RL controller.

**Deliverable:** Controlled baseline-vs-RL experiments on one
intersection.

### Phase 2 --- Real-World Intersection

Implement and validate:

-   OSM-derived real intersection,
-   real topology,
-   realistic traffic demand,
-   vehicle-behavior assumptions.

**Deliverable:** Adaptive control evaluated on real-world topology.

### Phase 3 --- Corridor Coordination

Target approximately 3--5 connected signalized intersections.

Focus on:

-   downstream state,
-   spillback,
-   queue propagation,
-   network-level metrics.

**Deliverable:** A network-aware controller that accounts for downstream
conditions.

### Phase 4 --- Small Urban Network

Target approximately 10--30 signalized intersections.

Research:

-   scalable state representation,
-   controller coordination,
-   Multi-Agent Reinforcement Learning,
-   centralized training / decentralized execution,
-   graph-based representations.

**Deliverable:** Coordinated adaptive control on a small real-world
urban network.

### Phase 5 --- Advanced Research

Potential directions include:

-   Multi-Agent Reinforcement Learning,
-   Graph Neural Networks,
-   traffic-demand prediction,
-   robust RL,
-   offline RL,
-   transfer between road networks,
-   domain randomization,
-   incident response,
-   simulation-to-real calibration.

These should only be introduced when earlier phases demonstrate a clear
need.

------------------------------------------------------------------------

## 25. Role of LLMs and Generative AI

Large Language Models are **not currently intended to be the
traffic-signal decision engine**.

Traffic-control decisions should be handled by methods appropriate for
sequential control, such as:

-   Reinforcement Learning,
-   classical traffic control,
-   optimization,
-   or hybrid control systems.

LLMs may instead support research and engineering workflows such as:

-   experiment configuration,
-   scenario generation,
-   experiment orchestration,
-   result analysis,
-   failure diagnosis,
-   research assistance,
-   documentation.

This is considered a secondary engineering layer rather than a core
control requirement.

------------------------------------------------------------------------

## 26. Initial Research Questions

### Simulation

1.  How reliably can OSM-derived SUMO networks represent real
    intersection topology?
2.  Which imported-network defects most strongly affect congestion
    behavior?
3.  Which SUMO vehicle parameters most strongly influence queue
    formation and spillback?
4.  How should heterogeneous driver behavior be represented?
5.  How can artificial simulation deadlock be distinguished from
    legitimate traffic gridlock?
6.  How should SUMO teleportation be configured and interpreted during
    experiments?

### Adaptive Control

1.  Which traffic observations are necessary for effective adaptive
    signal control?
2.  How much downstream information is required to prevent spillback?
3.  Does RL outperform a strong actuated controller under varying
    demand?
4.  Can the learned policy generalize to traffic patterns not seen
    during training?
5.  How should fairness and starvation be incorporated into evaluation?

### Network Coordination

1.  When does independent intersection control become insufficient?
2.  How much neighboring information is required?
3.  Does Multi-Agent RL provide sufficient benefit to justify its
    complexity?
4.  Can graph-based representations support transfer between different
    network topologies?

------------------------------------------------------------------------

## 27. Immediate Workstream

The immediate project workstream is formally defined as:

# Simulation Foundation

The intended research sequence is:

``` text
SUMO Current Capabilities
        ↓
OSM Import
        ↓
Network Generation
        ↓
Junction / TLS Validation
        ↓
Routing
        ↓
Traffic Demand
        ↓
Vehicle Behavior
        ↓
Deadlock / Gridlock
        ↓
Calibration
        ↓
Metrics
        ↓
Reproducibility
```

RL algorithm selection should occur **after** this foundation has been
investigated and validated.

------------------------------------------------------------------------

## 28. Current Non-Goals

The following are not initial priorities:

-   city-wide simulation,
-   Multi-Agent RL implementation,
-   Graph Neural Networks,
-   LLM-controlled traffic lights,
-   production traffic-infrastructure integration,
-   real-world deployment,
-   premature optimization of RL algorithms.

These remain possible future directions.

------------------------------------------------------------------------

## 29. Project Identity Summary

**Codename:** CADENCE

**Formal Title:**\
**Network-Aware Adaptive Traffic Signal Control Using Reinforcement
Learning on Real-World Urban Road Networks**

**Research Direction:**\
Adaptive traffic signal control on realistic urban road networks, with
emphasis on simulation fidelity, downstream congestion, spillback, and
network-level coordination.

**Working Principle:**

> **Do not optimize an environment we do not trust.**

------------------------------------------------------------------------

## 30. Initial References

1.  Eclipse SUMO --- OpenStreetMap Import\
    https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html

2.  Eclipse SUMO --- Import from OpenStreetMap Tutorial\
    https://sumo.dlr.de/docs/Tutorials/Import_from_OpenStreetMap.html

3.  Eclipse SUMO --- Scenario Guide\
    https://sumo.dlr.de/docs/Tutorials/ScenarioGuide.html

4.  Eclipse SUMO --- Vehicle Types and Routes\
    https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html

5.  Eclipse SUMO --- Car-Following Models\
    https://sumo.dlr.de/docs/Car-Following-Models/index.html

6.  Original University Project\
    https://github.com/Hin-Nattapat/Reinforcement_Traffic_Project
