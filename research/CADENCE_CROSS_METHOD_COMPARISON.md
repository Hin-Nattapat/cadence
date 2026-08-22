# CADENCE — Cross-Method Traffic Control Comparison and Pre-Implementation Decisions

**Project Codename:** CADENCE  
**Document Type:** Decision Synthesis  
**Status:** Pre-Implementation Research Final Checkpoint  
**Checkpoint Date:** 2026-08-22

---

# 1. Purpose

This document synthesizes the completed pre-implementation research across:

- traffic engineering,
- fixed/pre-timed control,
- actuated control,
- Max-Pressure,
- capacity/spillback-aware pressure control,
- optimization/MPC,
- Reinforcement Learning,
- MARL/GNN.

Its purpose is not to choose one universal winner.

Its purpose is to answer:

> **Which controller families must CADENCE support, which baselines are scientifically credible, and what claims can each method legitimately make?**

---

# 2. Central Finding

No reviewed controller family dominates every dimension.

The methods trade off:

- model dependence,
- training cost,
- runtime computation,
- theoretical guarantees,
- prediction,
- adaptation,
- interpretability,
- scalability,
- generalization,
- sensing requirements.

Therefore CADENCE should be a **controller-agnostic experimentation platform**.

---

# 3. Method Landscape

```text
Traffic Engineering
      ↓
Tuned Fixed-Time
      ↓
Actuated
      ↓
Max-Pressure
      ↓
Capacity-Aware Network Control
      ↓
MPC / Optimization
      ↓
RL
      ↓
MARL / GNN / Hybrid
```

This is not a quality ranking. It is a progression of control complexity/capability families.

---

# 4. Cross-Method Comparison

| Dimension | Fixed-Time | Actuated | Max-Pressure | Practical Capacity-Aware MP | MPC | RL | MARL/GNN |
|---|---|---|---|---|---|---|---|
| Real-time adaptive | No/plan-based | Yes | Yes | Yes | Yes | Yes | Yes |
| Downstream aware | No | Usually limited | Yes | Yes | Yes | Possible | Yes |
| Explicit prediction | No | No | No | Usually no | Yes | Learned/implicit | Learned/implicit |
| Training required | No | No | No | No | No | Yes | Yes |
| Explicit traffic model | Low | Low | Queue/service params | Moderate | High | Not required model-free | Not required model-free |
| Explicit constraints | Strong timing rules | Strong | External safety layer | External safety layer | Strong | External safety layer | External safety layer |
| Runtime computation | Very low | Low | Low | Low–medium | Medium–high | Low inference | Low–medium inference |
| Interpretability | Very high | High | High | High/medium | High | Lower | Lower |
| Strong stability theory | No general network theorem | No MP-style theorem | Yes under assumptions | Variant-dependent | Formulation-dependent | No generic guarantee | No generic guarantee |
| Finite-storage modeling | Timing-only | Indirect | Weak in original | Explicitly improved | Can be explicit | Feature/reward dependent | Feature/reward dependent |
| Generalization without retuning | Low | Medium | High algorithmically | Medium–high | Model-dependent | Open challenge | Open challenge |
| Online solver/model mismatch | No | No | No | No | Yes | No online solver | No online solver |
| Network scaling | Simple but limited adaptation | Good local | Strong decentralized | Strong depending variant | Challenging | Policy-dependent | Main research focus |

---

# 5. Traffic-Regime Perspective

## Undersaturated

Strong candidates:

- tuned fixed-time,
- actuated,
- progression/coordinated timing.

RL/MPC complexity may provide limited additional benefit unless demand is highly variable.

## Near Saturation

Important:

- actuated service allocation,
- pressure/network balancing,
- predictive coordination.

This is a useful regime for differentiating algorithms.

## Oversaturated

Objectives change toward:

- queue management,
- network throughput,
- preventing spillback,
- avoiding secondary congestion.

Strong candidates:

- Max-Pressure variants,
- finite-storage-aware MPC,
- network-aware RL.

## Spillback / Network Blocking

The most CADENCE-specific research regime.

Controllers must be tested on whether they:

- recognize downstream storage,
- avoid blocking intersections,
- preserve network progress,
- handle unavoidable bottlenecks.

---

# 6. What Fixed-Time Is For

CADENCE should use a **reasonably tuned** fixed-time baseline.

Purpose:

- deterministic reference,
- verify simulation repeatability,
- establish classical timing performance.

It must not be deliberately weak.

---

# 7. What Actuated Is For

Use SUMO native gap-based actuated control and document:

- min/max green,
- gap,
- detector placement,
- phase logic.

Purpose:

> Establish how far mature local demand-responsive control can go before network-aware methods are needed.

---

# 8. What Max-Pressure Is For

Use a clearly defined queue-based Original/Original-like Max-Pressure implementation.

Purpose:

- strong training-free network-aware baseline,
- expose whether downstream queue balancing already solves the problem.

Important:

- document movement queue semantics,
- turn ratios,
- service rates,
- theoretical boundary.

---

# 9. Practical Capacity-Aware Pressure Baseline

CADENCE should eventually implement **one**, not every variant.

Purpose:

> Prevent RL from receiving credit merely for using finite downstream storage, because pressure methods can also be made capacity-aware.

Exact variant remains an implementation-stage selection.

Preferred engineering characteristics:

- simple,
- reproducible,
- finite-storage aware,
- compatible with real lane/link geometry,
- explicit about theoretical differences from Original MP.

---

# 10. What MPC Is For

Use one competent finite-storage-aware MPC baseline if computational scope permits.

Purpose:

> Test whether explicit prediction + constraints outperform reactive network control.

Initial model should be tractable rather than maximally detailed.

The internal MPC model must remain separate from SUMO ground-truth dynamics.

---

# 11. What RL Is For

RL should be tested for value beyond:

- simple adaptation,
- downstream awareness,
- pressure logic,
- finite-storage awareness,
- predictive optimization.

Potential value:

- nonlinear policy approximation,
- fast runtime inference after training,
- adaptation to complex interactions without online combinatorial solving,
- learned combinations of state features,
- future hybridization.

These are empirical hypotheses, not assumed advantages.

---

# 12. What MARL/GNN Is For

MARL/GNN becomes justified when:

- multiple intersections require learned coordination,
- shared policy/topology heterogeneity matters,
- local observations are insufficient,
- transfer across network layouts is a research target.

It is not required to begin CADENCE implementation.

---

# 13. Recommended CADENCE Baseline Suite

## Tier 0 — Validation Controllers

1. **Fixed-Time**
2. **SUMO Native Actuated**

These validate environment/controller plumbing.

## Tier 1 — Network-Aware Classical

3. **Original / Queue-Based Max-Pressure**
4. **One Capacity-Aware Pressure Variant**

## Tier 2 — Predictive

5. **One Finite-Storage-Aware MPC**

## Tier 3 — Learning

6. **DQN reference**
7. **PPO primary generic RL**

## Tier 4 — Future

8. MARL / GNN / hybrid controllers only after simpler baselines are operational.

---

# 14. Fairness Rule

All controllers should share, where semantically possible:

```text
same network
same demand/routes
same simulation parameters
same signal legality/safety layer
same evaluation metrics
same scenario seeds
same observation-fidelity declaration
```

Differences in information scope must be explicit.

---

# 15. Controller-Specific Information Is Allowed

Fairness does **not** require identical mathematical inputs.

Examples:

- MPC legitimately needs a prediction model.
- Max-Pressure needs turn/service parameters.
- RL may use encoded features.
- Actuated uses detectors/gaps.

Fair comparison requires:

> information assumptions are documented, realistic, and not secretly biased toward one controller.

---

# 16. Evaluation Dimensions

Every controller should be evaluated on:

### Traffic Performance
- mean/P95 travel time,
- mean/P95 time loss,
- waiting,
- throughput/completion,
- queue,
- spillback.

### Fairness/Tail
- max waiting,
- per-approach performance,
- starvation.

### Failure
- teleport reasons,
- unfinished trips,
- insertion backlog,
- gridlock.

### Computational
- decision latency,
- solver timeout,
- inference latency.

### Robustness
- traffic-regime changes,
- parameter mismatch,
- unseen demand.

### Engineering
- configuration complexity,
- explainability,
- training/calibration requirement.

---

# 17. No Single Winner Metric

A method cannot be declared best from:

```text
average waiting time only
```

A strong conclusion requires:

- efficiency,
- tail/fairness,
- congestion propagation,
- failure,
- computational viability.

---

# 18. Research Claims CADENCE Should Avoid

Do not claim:

- RL is better because it beats arbitrary fixed timing.
- downstream queue awareness equals physical spillback awareness.
- Max-Pressure throughput optimality means minimum empirical travel time.
- MPC prediction is perfect.
- GNN guarantees topology generalization.
- SUMO native actuated represents every real-world actuated controller.
- one simulator scenario demonstrates real-world robustness.

---

# 19. Strong Research Questions for CADENCE

Better questions include:

1. When does network awareness become materially better than strong local actuated control?
2. Does finite-storage awareness reduce secondary congestion under oversaturation?
3. Does prediction provide measurable benefit over reactive Max-Pressure?
4. Can RL match or exceed strong classical/predictive baselines while retaining low online latency?
5. How does controller ranking change across traffic regimes?
6. How sensitive are results to observation fidelity and demand/model mismatch?
7. Can a common controller interface preserve scientific comparability across methods?

---

# 20. Architecture Decision

The research strongly supports:

> **CADENCE must not be architecturally tied to Reinforcement Learning.**

The simulator/environment is the long-lived asset.

Controllers are replaceable plugins.

---

# 21. Pre-Implementation Decision Register

### CM-D01
> CADENCE is a controller-agnostic traffic-control experimentation platform.

### CM-D02
> SUMO/environment correctness and reproducibility have higher priority than sophisticated control algorithms.

### CM-D03
> Initial implementation must support Fixed-Time, Actuated, and external plugin controllers before RL-specific code.

### CM-D04
> Controller evaluation must use a shared KPI/event pipeline independent of controller reward/objective.

### CM-D05
> Controller information/observation fidelity must be declared explicitly.

### CM-D06
> The main network research regime must include oversaturation and physical spillback, not only ordinary traffic.

### CM-D07
> Strong claims about RL require comparison with Max-Pressure and a competent predictive/non-learning method where feasible.

### CM-D08
> MARL/GNN is deferred until simpler multi-intersection baselines reveal a demonstrated coordination/generalization need.

### CM-D09
> No final “best controller” is selected before empirical experiments.

---

# 22. Pre-Implementation Research Status

```text
Traffic Engineering          ✅
Classical / Actuated         ✅
SUMO Foundation              ✅
Max-Pressure                 ✅
Optimization / MPC           ✅
RL-TSC                       ✅
MARL / GNN Landscape         ✅
Cross-Method Synthesis       ✅

Architecture / Contract      → next/final artifact
```

At this point, broad literature research should stop blocking implementation.

Future research should be **question-driven by experiments**, not open-ended landscape review.
