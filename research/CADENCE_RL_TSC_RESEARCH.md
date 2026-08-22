# CADENCE — Reinforcement Learning for Traffic Signal Control Research

**Project Codename:** CADENCE  
**Document Type:** Focused Research Notebook  
**Status:** Pre-Implementation Research Checkpoint  
**Checkpoint Date:** 2026-08-22  
**Scope:** RL formulation, state/action/reward design, algorithm families, benchmark practice, generalization, sim-to-real, and CADENCE implications.

---

# 1. Executive Conclusion

Reinforcement Learning is a legitimate candidate controller family for CADENCE, but it should not define the architecture.

The literature shows that RL-TSC can learn strong adaptive policies and can incorporate complex network state, graph representations, multi-objective rewards, and coordination. At the same time, current reviews continue to identify unresolved issues in:

- baseline fairness,
- generalization,
- scalability,
- sim-to-real transfer,
- reward specification,
- training cost,
- interpretability,
- observation realism,
- reproducibility.

Therefore CADENCE should treat RL as:

> **One pluggable controller family competing against competent traffic-engineering, Max-Pressure, and predictive-control baselines.**

The initial CADENCE RL work should prioritize a scientifically clean MDP and evaluation protocol over inventing a novel neural architecture.

---

# 2. RL Formulation for Traffic Signal Control

Traffic signal control is commonly formulated as a Markov Decision Process (MDP):

```text
Observation / State
        ↓
RL Agent
        ↓
Action
        ↓
Traffic Environment
        ↓
Reward
        ↓
next state
```

For multiple intersections, the formulation often becomes a multi-agent or partially observable problem.

The critical design elements are:

1. observation/state,
2. action,
3. reward,
4. decision interval,
5. transition/safety semantics,
6. termination/reset semantics.

A neural-network choice cannot compensate for a badly specified MDP.

---

# 3. Observation Design

Common RL-TSC observations include:

- current phase,
- elapsed/minimum-green state,
- incoming lane vehicle count,
- lane density,
- queue/halting count,
- waiting-related state,
- outgoing/downstream occupancy,
- pressure-like quantities,
- neighboring intersection information.

SUMO-RL's default observation illustrates a common practical design:

```text
phase one-hot
minimum-green flag
incoming lane densities
incoming lane queues
```

However, CADENCE should not inherit this blindly.

## CADENCE Observation Principle

Observation should be derived from a canonical traffic state through an explicit adapter:

```text
SUMO Raw State
      ↓
Canonical Traffic State
      ↓
Observation Adapter
      ├─ RL Observation
      ├─ Max-Pressure Observation
      ├─ MPC State
      └─ Sensor-Realistic Observation
```

This prevents algorithm-specific SUMO queries and supports fair comparison.

---

# 4. Observation Fidelity

CADENCE should preserve the previously proposed observation-fidelity concept:

### O0 — Omniscient Simulator State
Exact vehicle positions, routes, turning intentions, movement queues.

### O1 — Lane-Level Virtual Detection
Lane count, queue, halting, occupancy, detector-like measurements.

### O2 — Estimated Traffic State
Estimated queues, turning ratios, travel times.

### O3 — Real Sensor-Like State
Observation constrained by a specified deployment sensing model.

RL must not receive substantially richer information than classical baselines without explicit justification.

---

# 5. Downstream State

A central CADENCE research direction is network congestion propagation.

Therefore an RL observation intended to claim network awareness should include some representation of downstream or neighboring conditions, for example:

```text
incoming queue
downstream occupancy
available storage
neighbor state
current phase
elapsed phase
```

Merely learning from local incoming queues is adaptive local control, not necessarily network-aware control.

---

# 6. Action-Space Families

Common TSC RL action formulations include:

### A. Select Green Phase

```text
action = target legal green phase
```

This is common in RL environments and is straightforward for discrete algorithms.

### B. Keep / Switch

```text
0 = keep
1 = request switch / next legal phase
```

Smaller action space and strong traffic-engineering semantics.

### C. Phase Duration / Extension

```text
extend current green by Δt
```

or choose a duration.

### D. Timing-Plan Parameters

Choose:

- split,
- cycle,
- offset.

This is closer to continuous/network timing optimization.

## CADENCE Direction

The controller should **not** directly output raw bulb strings.

Preferred architecture:

```text
RL Policy
   ↓
ControllerAction
   ↓
Signal Safety / Constraint Layer
   ↓
Legal SUMO TLS transition
```

---

# 7. Safety-Layer Requirement

RL should not be expected to discover basic signal safety through reward.

The environment should enforce:

- legal phases,
- conflict prevention,
- minimum green,
- maximum green where configured,
- yellow,
- all-red/clearance where required,
- valid phase transitions.

This keeps the comparison with Max-Pressure and MPC fair because all adaptive controllers can use the same domain-level safety contract.

---

# 8. Decision Interval

RL action frequency is part of the control problem.

Too frequent:

- unrealistic switching pressure,
- unstable learning,
- excessive lost time,
- unnecessary action dimensionality.

Too infrequent:

- weak adaptation,
- delayed response to congestion.

The decision interval must be experiment metadata and should be separated from SUMO simulation step size.

---

# 9. Reward Design

Common reward families include:

- negative waiting time,
- change in waiting time,
- negative queue length,
- delay,
- speed,
- throughput,
- pressure,
- weighted multi-objective combinations.

SUMO-RL uses change in cumulative waiting time as a default and supports custom rewards.

Research such as PressLight explicitly connected RL reward/state design to Max-Pressure ideas rather than using purely heuristic reward engineering.

## CADENCE Reward Principle

Reward must remain distinct from:

```text
Observation
Evaluation KPI
```

A reward that produces good learning does not become the sole research metric.

---

# 10. Reward Risks

### Reward Hacking / Proxy Failure

Examples:

- low average waiting because difficult vehicles never enter,
- high throughput while starving a minor approach,
- low local queue while pushing congestion downstream,
- excessive phase persistence to avoid switch penalty.

Therefore reward design must be validated against the independent evaluation suite.

---

# 11. Candidate Reward Direction

CADENCE should **not lock a final reward before baseline implementation**.

A reasonable initial research baseline may use a simple transportation-grounded signal such as:

```text
change in total time-loss / waiting
```

or:

```text
pressure-related network signal
```

with explicit penalties only where justified.

The final proposed-controller reward should be selected after initial fixed/actuated/MP/MPC benchmarks expose actual failure modes.

---

# 12. DQN Family

Deep Q-Networks are natural for discrete phase-selection actions.

Strengths:

- conceptually simple,
- common in TSC literature,
- experience replay improves data reuse,
- strong connection to FRAP/PressLight-style value-based methods.

Limitations:

- discrete actions only,
- replay data can become problematic in non-stationary multi-agent settings,
- Q-learning variants require careful stabilization,
- may overfit a fixed topology/state encoding.

## CADENCE Role

DQN is a useful **reference RL baseline**, particularly for isolated/small discrete-action experiments.

It should not automatically become the final CADENCE RL architecture.

---

# 13. PPO Family

Proximal Policy Optimization directly optimizes a policy using clipped policy updates.

Strengths:

- stable general-purpose baseline,
- supports discrete or continuous policies,
- straightforward extension to parameter sharing / multi-agent workflows,
- widely implemented and well understood.

Limitations:

- on-policy and comparatively sample hungry,
- training cost can be substantial with microscopic simulation,
- no inherent traffic-engineering structure.

## CADENCE Role

PPO is a strong candidate for the **primary generic RL baseline** because it is relatively architecture-neutral and supports future action-space extensions.

This is a baseline recommendation, not a claim that PPO is superior to all TSC-specific RL methods.

---

# 14. Actor-Critic / A2C / SAC

Actor-critic methods learn both policy and value estimates.

### A2C/A3C
Historically common and simple actor-critic references.

### SAC
Particularly attractive for continuous action spaces because of entropy-regularized exploration.

If CADENCE later optimizes continuous quantities such as green extension or split, SAC-like methods become more relevant.

For initial discrete legal-phase control, adding SAC is not necessary.

---

# 15. Traffic-Specific RL Models

## FRAP

FRAP models **phase competition** and introduces symmetry-aware structure to improve convergence and generalization across traffic patterns/road structures.

Main CADENCE lesson:

> Neural architecture can encode traffic-domain invariances instead of learning every symmetry from scratch.

## PressLight

PressLight connects RL state/reward design to Max-Pressure.

Main CADENCE lesson:

> RL and transportation theory do not need to be competing camps; domain theory can structure RL.

## CoLight

CoLight uses graph attention for learned coordination between intersections.

Main CADENCE lesson:

> Graph-based communication is a natural mechanism for network-level RL, but it introduces a substantially larger research/implementation scope.

## MetaLight

MetaLight uses meta-learning to adapt faster to new traffic scenarios.

Main CADENCE lesson:

> Retraining and generalization are recognized weaknesses of fixed-scenario RL policies.

---

# 16. Generalization

A major weakness in RL-TSC research is that a policy can perform strongly on:

```text
same topology
same demand family
same simulator assumptions
```

while failing on:

- unseen traffic demand,
- reversed flows,
- different road geometry,
- different signal phasing,
- different vehicle behavior,
- incidents,
- unseen network topology.

Recent reviews continue to identify generalization as a central open problem.

## CADENCE Generalization Tests

At minimum:

1. unseen random seeds,
2. unseen demand magnitude,
3. unseen turning ratios,
4. unseen temporal demand pattern,
5. parameter perturbation in vehicle behavior.

Later:

6. unseen intersection/corridor,
7. topology transfer.

---

# 17. Sim-to-Real Gap

Most RL-TSC evaluation remains simulator-based.

Sim-to-real risks include:

- inaccurate driving behavior,
- imperfect detector observations,
- unmodeled incidents,
- communication delay,
- pedestrian/multimodal behavior,
- sensor noise,
- unusual lane use,
- topology/configuration errors.

CADENCE's simulator-first validation is therefore not ancillary work. It is central to any credible RL result.

---

# 18. Training/Test Leakage

Training and evaluation demand must be separated.

Bad evaluation:

```text
train on demand file A
test on demand file A
report best episode
```

Preferred:

```text
training scenarios
validation scenarios
held-out evaluation scenarios
```

with controlled seeds and unseen demand conditions.

---

# 19. Multiple Seeds

RL results are stochastic.

CADENCE should report:

- multiple training seeds,
- multiple simulation/evaluation seeds,
- mean and distribution/uncertainty,
- not just the best policy run.

Baseline controllers should use the same evaluation scenario set.

---

# 20. Benchmark Fairness

The literature increasingly recognizes the need for strong baselines.

CADENCE should avoid:

```text
RL vs arbitrary fixed-time
```

as the main claim.

Required baseline ladder should include competent representatives from:

- tuned fixed-time,
- actuated,
- Max-Pressure,
- predictive optimization/MPC,
- RL.

LibSignal is relevant precedent: it was explicitly developed for unified, cross-simulator comparison of TSC methods with consistent metrics.

---

# 21. Simulator Dependence

RL performance can depend on simulator behavior.

Therefore CADENCE should treat:

- SUMO version/configuration,
- vehicle model,
- routing,
- network preprocessing,
- action interval,
- teleports,
- detector semantics,

as experiment dependencies.

The controller must not depend on undocumented SUMO quirks.

---

# 22. Evaluation Suite

RL should be evaluated with the same external KPI suite as all other controllers.

### Efficiency
- travel time,
- time loss,
- waiting,
- completed throughput.

### Tail / Fairness
- P95 travel/wait,
- maximum waiting,
- per-approach performance,
- starvation indicators.

### Congestion
- queue length,
- residual queue / cycle failure,
- spillback,
- downstream blocking.

### Failure
- teleports by reason,
- unfinished trips,
- insertion/depart delay.

### Computational
- inference latency,
- training cost,
- model size where useful.

---

# 23. RL-Specific Evaluation

In addition to traffic KPIs:

- training steps,
- wall-clock training cost,
- convergence stability,
- seed variance,
- sample efficiency,
- generalization gap,
- inference latency,
- retraining requirement.

---

# 24. Initial RL Baseline Recommendation

For CADENCE v1:

### Reference RL
**DQN** on discrete legal-phase actions.

Purpose:
- connect with established TSC literature,
- transparent value-based baseline.

### Primary Generic RL
**PPO** using the same canonical observation and legal action contract.

Purpose:
- robust general-purpose policy baseline,
- easier future extension.

### Do Not Implement Initially
- large bespoke Transformer,
- GNN-MARL,
- meta-RL,
- model-based RL,
- LLM real-time controller.

These belong after the platform and scientific baselines work.

---

# 25. Proposed RL Development Sequence

```text
Single real/synthetic validated intersection
        ↓
DQN / PPO baseline
        ↓
real intersection
        ↓
corridor with parameter sharing / simple coordination
        ↓
only then consider MARL/GNN
```

This keeps algorithm complexity below environment complexity.

---

# 26. RL Decision Register

### RL-D01
> RL is a pluggable controller family, not the architectural center of CADENCE.

### RL-D02
> RL actions must pass through the common legal signal safety/constraint layer.

### RL-D03
> RL observation fidelity must be explicit and comparable to non-learning baselines.

### RL-D04
> Reward is a training signal and must remain separate from experiment KPIs.

### RL-D05
> Initial RL evaluation must use held-out traffic scenarios and multiple seeds.

### RL-D06
> Competent fixed, actuated, Max-Pressure, and MPC baselines must precede strong claims about RL superiority.

### RL-D07
> Use DQN as a discrete-action reference and PPO as the primary generic RL baseline for early CADENCE experiments.

### RL-D08
> Do not implement MARL/GNN until the corridor/network experiments demonstrate a coordination problem that simpler controllers do not adequately solve.

---

# 27. Open Questions Deferred to Implementation

- exact observation feature vector,
- exact reward formula,
- decision interval,
- neural network size,
- hyperparameters,
- replay/training schedule,
- whether downstream occupancy or available-storage ratio is preferable,
- whether the eventual proposed controller should be pure RL or hybrid.

These should be decided empirically within the validated platform.

---

# 28. Research Checkpoint

The RL pre-implementation research is sufficient to proceed to architecture design.

The key conclusion is:

> **CADENCE should invest first in environment correctness, controller contracts, baseline fairness, and generalization methodology. Novel RL architecture should come later, if evidence shows it is needed.**

---

# 29. Key References

1. Zhang, X. et al. (2026). *Reinforcement learning for traffic signal control in large-scale transportation networks: a systematic literature review*. Artificial Intelligence Review. DOI: 10.1007/s10462-026-11676-6.
2. Xiao, F. et al. (2025). *Advances in reinforcement learning for traffic signal control: a review of recent progress*. Intelligent Transportation Infrastructure. DOI: 10.1093/iti/liaf009.
3. Michailidis, P. et al. (2025). *Traffic Signal Control via Reinforcement Learning: A Review on Applications and Innovations*. Infrastructures 10(5):114. DOI: 10.3390/infrastructures10050114.
4. Wei, H. et al. (2019). *PressLight: Learning Max Pressure Control to Coordinate Traffic Signals in Arterial Network*. KDD. DOI: 10.1145/3292500.3330949.
5. Zheng, G. et al. / Xiong, Y. et al. (2019). *Learning Phase Competition for Traffic Signal Control (FRAP)*. arXiv:1905.04722 / conference publication.
6. Wei, H. et al. (2019). *CoLight: Learning Network-level Cooperation for Traffic Signal Control*. CIKM. DOI: 10.1145/3357384.3357902.
7. Zang, X. et al. (2020). *MetaLight: Value-Based Meta-Reinforcement Learning for Traffic Signal Control*. AAAI. DOI: 10.1609/aaai.v34i01.5467.
8. Mei, H. et al. (2022). *LibSignal: An Open Library for Traffic Signal Control*. arXiv:2211.10649.
9. SUMO-RL project/documentation: https://github.com/LucasAlegre/sumo-rl
