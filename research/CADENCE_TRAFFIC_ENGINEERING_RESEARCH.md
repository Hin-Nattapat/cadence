# CADENCE — Traffic Engineering Research

**Formal Project Title:** Network-Aware Adaptive Traffic Signal Control Using Reinforcement Learning on Real-World Urban Road Networks  
**Project Codename:** CADENCE  
**Document Type:** Focused Research Notebook  
**Status:** Active Research Checkpoint  
**Scope:** Traffic engineering fundamentals, classical signal timing, and actuated traffic signal control

---

## Purpose

This document contains the detailed traffic-engineering research that supports CADENCE controller design and experiment methodology.

It is intentionally separated from the master traffic-control research plan.

### Current completed research tracks

1. Traffic Engineering Fundamentals
2. Classical Signal Control & Actuated Control

### Research principle

> **A controller should not be credited for learning behavior that established traffic engineering already provides explicitly.**

---

# Part I — Traffic Engineering Fundamentals

## Demand, Flow, and Capacity

**Demand** is the amount of traffic that wants to pass. **Flow** is the amount that actually passes. **Capacity** is the maximum traffic service rate available under current conditions.

For a signalized movement:

```text
capacity ≈ saturation flow × effective green / cycle length
```

If demand exceeds capacity, queues accumulate.

## Saturation Flow

**Saturation flow** is approximately the maximum stable discharge rate of a continuously queued traffic stream while effective green is available.

Example:

```text
2-second discharge headway
→ 3600 / 2
→ ~1800 veh/hour/lane
```

Parameters such as `tau`, `minGap`, acceleration, vehicle length, turning behavior, and lane geometry can change simulated saturation flow.

**Decision Candidate TC-D02**

> Before controller evaluation, CADENCE should validate key saturation-flow and queue-discharge behavior in the SUMO scenario.

## Startup and Clearance Lost Time

**Startup lost time** is the inefficient period immediately after green starts while drivers react and accelerate.

**Clearance lost time** is ineffective time associated with yellow/all-red transitions.

```text
Total Lost Time
=
Startup Lost Time
+
Clearance Lost Time
```

## Effective Green

**Effective green** is the green-equivalent time during which traffic receives effective discharge. Displayed green and effective green are not always identical.

## Switching Has a Capacity Cost

Frequent phase switching creates repeated startup, yellow, and clearance losses. Excessive switching can reduce intersection capacity even when nominal green allocation looks similar.

This supports explicit minimum green, legal transition rules, and bounded decision frequency.

## Degree of Saturation / v/c

```text
v/c = demand / capacity
```

```text
v/c < 1  → undersaturated
v/c ≈ 1  → near saturation
v/c > 1  → oversaturated
```

## Residual Queue and Cycle Failure

A **residual queue** remains after green/cycle ends.

A **cycle failure** occurs when a queued movement receives green but the queue does not fully clear before green ends.

Potential future metric:

```text
cycle_failure_rate
```

## Undersaturated vs Oversaturated Operation

### Undersaturated
- minimize delay,
- reduce stops,
- improve progression,
- reduce travel time.

### Oversaturated
- manage queues,
- prevent spillback,
- protect downstream bottlenecks,
- preserve useful throughput,
- avoid secondary congestion.

**Decision Candidate TC-D03**

> Oversaturated evaluation must explicitly consider queue management, spillback, and secondary congestion rather than delay alone.

## Primary and Secondary Congestion

**Primary congestion** occurs at the actual bottleneck.

**Secondary congestion** propagates from that bottleneck into other parts of the network.

A strong CADENCE contribution may be preventing unavoidable local congestion from becoming avoidable network-wide congestion.

## Cycle Length and Green Split

**Cycle length** is the total time required for a signal sequence to repeat.

**Green split** is the share of cycle time allocated to each phase/movement.

Longer cycles can reduce transition-loss fraction but may also increase waiting, queues, turn-bay overflow, and spillback.

## Critical Movement

A **critical movement** is the movement/lane group placing the strongest capacity requirement on a phase.

## Webster-Type Timing

A classical isolated-intersection timing method uses traffic demand, critical flow ratios, and lost time to estimate an efficient cycle length.

A familiar form is:

```text
C0 = (1.5L + 5) / (1 - Y)
```

The important intuition is:

```text
higher demand → more green required
higher lost time → frequent switching becomes more expensive
```

**Decision Candidate TC-D04**

> Fixed-time baselines should be reasonably tuned using established traffic-engineering principles instead of arbitrary phase durations.

## Platoons, Offset, and Progression

A **platoon** is a group of vehicles traveling together, often released by an upstream green.

**Offset** is the timing difference between nearby signal cycles. Good offsets can create a **green wave**.

## Progression vs Queue Management

Under moderate traffic, progression can improve travel time and reduce stops.

Under oversaturation, queue management, spillback prevention, and network protection may be more important than maintaining progression.

## Traffic Regimes for CADENCE

```text
Regime A — Undersaturated
v/c clearly < 1

Regime B — Near Saturation
v/c ≈ 1

Regime C — Oversaturated
v/c > 1

Regime D — Network Spillback
downstream bottlenecks create secondary congestion
```

**Decision Candidate TC-D01**

> Controller evaluation must cover undersaturated, near-saturated, and oversaturated conditions rather than a single traffic volume.

## Reward-Design Implication

Potential priorities differ by regime:

```text
Low traffic:
- travel time
- stops

Near capacity:
- balanced service
- queue control

Oversaturated:
- useful throughput
- spillback prevention
- network protection
```

This does not yet imply a dynamic reward function.

## Traffic Engineering Decision Register

| ID | Decision Candidate |
|---|---|
| TC-D01 | Evaluate controllers across undersaturated, near-saturated, and oversaturated regimes. |
| TC-D02 | Validate scenario saturation flow and queue discharge before controller evaluation. |
| TC-D03 | Oversaturated evaluation must include spillback, queue management, and secondary congestion. |
| TC-D04 | Fixed-time baseline should be reasonably tuned using established traffic-engineering principles. |

## Research Result Summary

```text
UNDER CAPACITY
→ optimize efficiency

NEAR CAPACITY
→ allocate scarce service effectively

OVER CAPACITY
→ manage unavoidable queues

NETWORK OVERLOAD
→ prevent local congestion from propagating
```

> **When demand approaches or exceeds capacity, adaptive signal control should manage queue propagation and protect network throughput, not simply minimize local delay.**

---

# Part II — Classical Signal Control & Actuated Control

## Classical Signal Control Is Broader Than Fixed-Time

Classical traffic signal control includes more than pre-timed operation.

```text
Classical Traffic Signal Control
│
├── Pre-timed / Fixed-Time
├── Semi-Actuated
├── Fully-Actuated
└── Coordinated-Actuated
```

The important distinction is whether the controller reacts to real-time detector demand and whether it coordinates with neighboring signals.

## Pre-Timed / Fixed-Time Control

**Pre-timed** or **fixed-time** control follows a predefined signal timing plan. Typical fixed parameters include cycle length, phase sequence, green duration, yellow/clearance duration, and offset.

A real system may use different **Time-of-Day plans** such as AM Peak, Off Peak, PM Peak, and Night, so fixed-time does not necessarily mean one timing plan all day. A credible fixed-time baseline should not be intentionally weak.

## Actuation and Call

**Actuation** means a detector detects vehicle or pedestrian demand and sends a service request to the controller. The internal request is commonly called a **call**.

```text
Vehicle arrives
      ↓
Detector activates
      ↓
Call registered
      ↓
Controller considers relevant phase
```

A call does not necessarily mean an immediate signal change because timing and safety constraints still apply.

## Semi-Actuated Control

**Semi-actuated control** typically places detectors on selected/minor approaches while the major street remains the default service state.

```text
Main road = GREEN by default
Side-road vehicle arrives
        ↓
Detector call
        ↓
Serve side road
        ↓
Return to main road
```

Strengths include avoiding wasted green on empty side roads and supporting coordinated arterial progression. Its main limitation is that it still responds primarily to local demand.

## Fully-Actuated Control

**Fully-actuated control** uses detectors on all major traffic movements. It can respond to demand from multiple directions and alter phase duration cycle-by-cycle. Typical behavior includes variable green duration, gap-out, max-out, phase skipping, and detector-based service. This is a much stronger baseline than fixed-time control.

## Minimum Green

**Minimum green** is the minimum time a phase must remain green after activation. It helps queued vehicles start moving, avoids rapid switching, and ensures useful service once a phase begins.

## Passage Time / Vehicle Extension

**Passage time** (also called vehicle extension/gap time in related terminology) allows green to be extended when additional vehicles are detected. The configured time must be consistent with detector placement so detected vehicles have enough time to reach and clear the intersection.

## Gap and Gap-Out

A **gap** is the time interval between successive detector actuations.

**Gap-out** occurs when no new vehicle is detected within the configured gap threshold.

```text
GREEN
 ↓
vehicles detected
 ↓
extend
 ↓
no vehicle for long enough
 ↓
GAP-OUT
 ↓
terminate phase
```

## Maximum Green and Max-Out

**Maximum green** limits how long a phase may continue when competing demand exists.

**Max-out** means the phase terminates because it reaches its maximum green duration even though demand continues.

```text
Gap-Out → demand disappeared
Max-Out → demand remains, but service limit reached
```

## Recall

**Recall** is a controller setting that creates or maintains a phase call even without a new detector actuation. Common conceptual forms include minimum recall, maximum recall, soft recall, and pedestrian recall.

**Minimum recall** ensures at least minimum service. **Maximum recall** can make a phase behave as continuously demanding maximum service. **Soft recall** provides a more flexible default service condition.

## Phase Skipping

An actuated controller may skip a phase when no demand exists for it. SUMO actuated traffic-light logic can support detector-aware dynamic phase selection when configured appropriately.

## Detector Placement

Detector location is part of controller behavior, not merely simulator instrumentation. A farther detector observes traffic earlier, but passage-time settings must match the travel time to the stop line. Poor detector placement/configuration can make an actuated controller appear artificially weak or strong.

### Decision Candidate TC-D07

> Detector placement and detector-related timing parameters must be treated as part of actuated-controller configuration and experiment metadata.

## Local Responsiveness vs Network Awareness

An actuated controller can react intelligently to local demand, but this does not necessarily mean it understands downstream saturation, neighboring blockage, or network spillback.

```text
Adaptive to local demand ≠ Network-aware
```

### Decision Candidate TC-D08

> A controller should not be called network-aware merely because it adapts to local detector demand.

## Coordinated Actuated Control

Actuated operation can be combined with network coordination. Signals may preserve common cycle relationships, offsets, and coordinated phases while non-coordinated movements still respond to detector demand.

## Early Return to Green

If a side-road phase uses less than its available service time, it may terminate early and unused time can be returned to the coordinated/main-street phase. This is known as **early return to green**.

## Force-Off

In coordinated operation, a non-coordinated phase may be forced to terminate at a defined time so the signal remains synchronized with the background coordination plan. This forced termination point is a **force-off**.

## Actuated Control as a State Machine

```text
              ┌─────────────┐
              │ MIN GREEN   │
              └──────┬──────┘
                     ↓
              ┌─────────────┐
   vehicle →  │ EXTENSION   │
   detected   │             │
              └──────┬──────┘
                     │
             ┌───────┴─────────┐
             │                 │
          GAP-OUT           MAX-OUT
             │                 │
             └───────┬─────────┘
                     ↓
                  YELLOW
                     ↓
               NEXT PHASE
```

Coordinated systems additionally introduce cycle, offset, force-off, recall, and early-return behavior. Therefore an RL `keep/switch` policy is competing against mature traffic-control engineering, not trivial logic.

## SUMO Native Actuated Control

SUMO provides native actuated traffic-light logic (`type="actuated"`) with parameters and behaviors such as `minDur`, `maxDur`, `max-gap`, detector-placement/gap configuration, passing-time concepts, generated detector logic, coordinated actuated operation, earliest/latest phase-ending controls, dynamic phase selection, and customizable switching conditions.

SUMO documents its built-in actuated scheme as a gap-based control approach common in Germany. Therefore:

```text
SUMO Native Actuated ≠ Universal Real-World Actuated Ground Truth
```

CADENCE should describe it precisely as a reproducible **SUMO native gap-based actuated baseline**.

## Default vs Tuned Actuated Baseline

A future benchmark may distinguish:

- **Native SUMO Actuated** — reproducible and simple.
- **Tuned Actuated** — parameters such as minGreen, maxGreen, max-gap, detector placement, and phase sequence are reasonably tuned for the scenario.

### Decision Candidate TC-D05

> CADENCE should include SUMO's native gap-based actuated controller as a reproducible classical baseline.

### Decision Candidate TC-D06

> Actuated-controller parameters should be documented and reasonably tuned rather than relying blindly on defaults.

## What Actuated Control Already Solves

Without RL, actuated traffic control already provides local sensing, demand-driven service, variable green duration, phase skipping, bounded phase duration, starvation protection, early phase termination, coordination support, and predictable safety logic.

Therefore RL must demonstrate value beyond merely adapting signal timing. Candidate value areas remain downstream awareness, network-level coordination, nonlinear/global objectives, complex multi-intersection interaction, and difficult oversaturated operation.

## Updated Classical Baseline Ladder

```text
Tuned Fixed-Time
       ↓
SUMO Native Gap-Based Actuated
       ↓
Tuned Actuated
       ↓
Coordinated Classical Control
       ↓
Max-Pressure / Network-Aware Classical
       ↓
MPC / Optimization
       ↓
RL / Hybrid
```

Not every level must eventually be implemented, but baseline selection should be based on scientific relevance rather than convenience.

## Classical / Actuated Decision Register

| ID | Decision Candidate |
|---|---|
| TC-D05 | Include SUMO native gap-based actuated control as a reproducible classical baseline. |
| TC-D06 | Document and reasonably tune actuated-controller parameters rather than relying blindly on defaults. |
| TC-D07 | Treat detector placement and detector timing as part of controller configuration/experiment metadata. |
| TC-D08 | Distinguish local demand responsiveness from true network awareness. |

## Research Result Summary

The main lesson is:

> **Actuated control is already a sophisticated adaptive local controller.**

It can dynamically sense demand, extend/terminate phases, skip empty phases, protect competing approaches, and coordinate with corridor timing without neural networks, training, or reward functions.

The remaining research question is more specific:

> **What additional value can a network-aware controller provide beyond mature local/actuated traffic control?**

This makes **Max-Pressure / backpressure control** the next logical research topic.

---

# Part III — Current Boundary and Next Research

The detailed traffic-engineering track currently ends at classical and actuated control.

The next network-aware control track is maintained separately in:

`CADENCE_MAX_PRESSURE_RESEARCH.md`

The master roadmap and cross-method landscape remain in:

`CADENCE_TRAFFIC_CONTROL_RESEARCH_PLAN.md`

## Current Traffic-Engineering Decision Register

- `TC-D01` — Evaluate controllers across undersaturated, near-saturated, and oversaturated regimes.
- `TC-D02` — Validate scenario saturation flow and queue discharge before controller evaluation.
- `TC-D03` — Oversaturated evaluation must include spillback, queue management, and secondary congestion.
- `TC-D04` — Fixed-time baseline should be reasonably tuned using established traffic-engineering principles.
- `TC-D05` — Include SUMO native gap-based actuated control as a reproducible classical baseline.
- `TC-D06` — Document and reasonably tune actuated-controller parameters rather than relying blindly on defaults.
- `TC-D07` — Treat detector placement and detector timing as part of controller configuration/experiment metadata.
- `TC-D08` — Distinguish local demand responsiveness from true network awareness.

