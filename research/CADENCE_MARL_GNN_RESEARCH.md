# CADENCE — MARL / Graph-Based Traffic Signal Control Research

**Project Codename:** CADENCE  
**Document Type:** Focused Research Notebook  
**Status:** Pre-Implementation Landscape Checkpoint  
**Checkpoint Date:** 2026-08-22

---

# 1. Executive Conclusion

Multi-Agent Reinforcement Learning (MARL) and Graph Neural Networks (GNNs) are highly relevant to network traffic signal control, but they should **not** be required for CADENCE v1.

They address genuine problems:

- distributed intersections,
- partial observability,
- network coordination,
- topology-aware representation,
- parameter sharing,
- transfer across heterogeneous networks.

They also introduce major new difficulties:

- non-stationary multi-agent learning,
- credit assignment,
- communication design,
- scalability,
- topology heterogeneity,
- reproducibility,
- sim-to-real communication assumptions.

CADENCE should design its platform so MARL/GNN can plug in later, while initially proving the simulation core and simpler controller families.

---

# 2. Why Traffic Networks Suggest Multiple Agents

A natural decomposition is:

```text
Intersection A → Agent A
Intersection B → Agent B
Intersection C → Agent C
```

Benefits:

- local action space remains small,
- decentralized execution is realistic,
- failures/complexity can be localized,
- network topology maps naturally to neighboring agents.

However, independent local agents do not automatically coordinate.

---

# 3. Independent Multi-Agent Learning

Simplest approach:

```text
Agent A learns independently
Agent B learns independently
Agent C learns independently
```

Advantages:

- simple,
- scalable implementation,
- local observations/actions.

Problem:

> From each agent's perspective, the environment changes because neighboring agents are also learning.

This is the **non-stationarity problem**.

A transition distribution experienced early in training may differ because neighbor policies later change.

---

# 4. Partial Observability

An intersection rarely observes the full network.

Agent A may see:

```text
local incoming queues
local outgoing occupancy
current phase
```

while congestion farther away still affects future outcomes.

Thus multi-intersection TSC is often naturally modeled as a partially observable or Dec-POMDP-style problem.

Solutions include:

- neighbor observations,
- communication,
- recurrent memory,
- graph message passing,
- centralized training.

---

# 5. Credit Assignment

Suppose network travel time improves.

Which signal caused the improvement?

```text
Agent A?
Agent B?
Agent C?
their coordination?
```

A purely global reward gives cooperation information but weak individual credit.

A purely local reward improves credit clarity but can produce selfish local behavior.

MARL research therefore uses:

- local + neighborhood rewards,
- counterfactual baselines,
- value decomposition,
- centralized critics,
- shaped network objectives.

Credit assignment is a core complexity, not an implementation detail.

---

# 6. Centralized Control

One policy observes the whole network and chooses all actions.

```text
Global State
    ↓
Central Policy
    ↓
[A action, B action, C action, ...]
```

Advantages:

- explicit global coordination.

Problems:

- state/action size grows rapidly,
- poor scalability,
- topology-specific policy dimensions,
- centralized runtime dependency.

This is usually unattractive for large heterogeneous networks.

---

# 7. Decentralized Control

Each agent uses local observation:

```text
o_i → π_i → a_i
```

Advantages:

- scalable runtime,
- local failure isolation,
- realistic distributed operation.

Problems:

- partial observability,
- weak coordination,
- potential selfish policies.

---

# 8. CTDE

**Centralized Training, Decentralized Execution (CTDE)** is a major MARL paradigm.

Training may use:

- global state,
- joint actions,
- network reward,
- centralized critic.

Execution uses:

- local observation,
- limited neighbor messages,
- local action.

```text
TRAINING:
global information allowed

EXECUTION:
local / bounded information
```

This addresses some non-stationarity and credit-assignment issues while preserving decentralized deployment.

---

# 9. Value Decomposition

Methods such as VDN/QMIX-inspired approaches learn how individual agent values combine into a joint network value.

Conceptually:

```text
Q_A
Q_B
Q_C
 ↓
mixing / joint value
 ↓
Q_total
```

Purpose:

- improve cooperative credit assignment,
- retain decentralized local action selection.

It adds substantial training machinery and is not necessary for the first CADENCE controller.

---

# 10. Communication-Based MARL

Agents may explicitly share information such as:

- queue summaries,
- occupancy,
- phase state,
- learned embeddings,
- predicted arrivals.

Communication raises design questions:

- which neighbors?
- how often?
- message size?
- communication delay?
- packet loss?
- learned vs fixed messages?

A simulated zero-latency global communication channel can create unrealistic advantages.

CADENCE should make communication assumptions part of observation fidelity and experiment metadata.

---

# 11. Why Graphs Fit Traffic Networks

Road networks are naturally graphs:

```text
intersection = node
road/connectivity = edge
```

Node features can include:

- queue,
- occupancy,
- phase,
- waiting,
- local demand.

Edges can represent:

- physical road connection,
- direction,
- distance,
- travel time,
- traffic influence.

GNNs exploit this structure instead of flattening the whole network into one fixed vector.

---

# 12. Message Passing

A basic GNN repeatedly aggregates neighbor information:

```text
Node A state
   +
messages from connected nodes
   ↓
updated embedding
```

After multiple layers, a node can represent wider network context.

Advantages:

- parameter sharing,
- topology-aware representation,
- variable graph sizes,
- relational inductive bias.

Limitations:

- receptive field can still be limited,
- deeper message passing can blur information,
- computation/communication grows,
- transfer is not automatic.

---

# 13. Graph Attention

CoLight introduced graph-attention-style communication for traffic-signal cooperation.

Instead of treating every neighbor equally, attention can learn:

```text
neighbor B matters strongly now
neighbor C matters less now
```

This is attractive for dynamic congestion propagation.

However, learned attention is not automatically interpretable as causal traffic importance.

---

# 14. GNN and Generalization

Graph-centric state representations have shown improved transfer to unseen demand scenarios compared with fixed vector representations in some studies.

Recent large-scale work also uses graph structures and action masking to handle heterogeneous intersections/topologies.

The literature nevertheless continues to identify OOD generalization as unresolved.

Therefore:

> GNN is a useful inductive bias, not a guarantee of generalization.

---

# 15. Topology Heterogeneity

Real-world intersections differ in:

- lane count,
- number of phases,
- turning permissions,
- geometry,
- neighboring degree.

A fixed neural input/output dimension can become brittle.

Potential solutions:

- graph state,
- movement-level encoding,
- shared embeddings,
- phase/action masking,
- parameter sharing,
- variable-size set/graph models.

This is highly relevant to future CADENCE real-world network scaling.

---

# 16. Action Masking

If different intersections have different legal phases, a shared policy can output a generic action set with illegal actions masked.

This allows parameter sharing while preserving intersection-specific legality.

CADENCE already needs a signal safety layer, so action masks should originate from the same canonical signal-plan metadata.

---

# 17. Parameter Sharing

Rather than one neural network per intersection:

```text
π_A, π_B, π_C ...
```

agents can share parameters:

```text
π_shared(o_i, intersection_metadata)
```

Advantages:

- less training data per policy,
- reduced memory,
- potentially better transfer.

Risk:

- intersections with very different behavior may require specialization.

---

# 18. Hierarchical / Regional Control

Recent research increasingly explores region-based or hierarchical multi-agent structures.

Concept:

```text
local intersection agents
        ↓
region coordinator
        ↓
network objective
```

This mirrors classical ideas such as perimeter/network layers and distributed MPC.

CADENCE architecture should not force “one agent per intersection” as the only future decomposition.

---

# 19. MARL Evaluation Risks

MARL can look strong if:

- communication is perfect and free,
- global training state is omniscient,
- topology used in test is identical,
- only one traffic pattern is evaluated,
- baseline controllers lack equivalent neighbor information.

Therefore CADENCE must report:

- training information scope,
- execution information scope,
- communication graph,
- latency assumptions,
- parameter sharing,
- reward scope.

---

# 20. MARL vs Distributed MPC / Max-Pressure

### Max-Pressure
Distributed local computation using traffic-theory pressure.

### Distributed MPC
Local/regional optimizers communicate predicted states/models.

### MARL
Local policies coordinate through learned value/policy structure.

They solve overlapping coordination problems with different assumptions.

Therefore MARL novelty cannot simply be:

> “multiple intersections communicate.”

Classical control already coordinates networks.

---

# 21. Recommended CADENCE MARL Scope

Before implementation:

### Understand
- independent agents,
- CTDE,
- credit assignment,
- graph message passing,
- parameter sharing,
- topology/action masking.

### Do Not Implement Yet
- complex value decomposition,
- hierarchical graph transformer,
- learned communication protocol,
- city-scale MARL.

These should be triggered by measured failure of simpler corridor/network controllers.

---

# 22. Future MARL Entry Point

A sensible future progression:

```text
Single-agent RL validated
        ↓
Independent/shared-policy multi-intersection RL
        ↓
neighbor observation
        ↓
simple CTDE / centralized critic
        ↓
GNN message passing if topology/generalization demands it
```

This allows ablation of each source of complexity.

---

# 23. MARL/GNN Decision Register

### MG-D01
> MARL/GNN is a future controller family/representation layer, not a dependency of CADENCE simulation core.

### MG-D02
> Training-time global information and execution-time local information must be documented separately.

### MG-D03
> Communication topology, frequency, and latency assumptions are part of the experimental specification.

### MG-D04
> GNNs should be introduced only if topology heterogeneity, transfer, or neighbor coordination creates a demonstrated need.

### MG-D05
> The common signal safety/action-mask source must remain outside the learned policy.

### MG-D06
> Parameter sharing should be preferred before one bespoke neural policy per intersection when intersections have compatible control semantics.

### MG-D07
> MARL evaluation must include non-identical/unseen demand and should eventually include topology-generalization tests before claiming scalability.

---

# 24. Research Checkpoint

MARL/GNN knowledge is sufficient for pre-implementation architecture.

The architecture must support:

- multiple controller instances,
- shared policy backends,
- neighborhood queries,
- optional communication,
- graph/topology metadata,
- centralized training utilities,

without requiring any of them for ordinary fixed/actuated/MP/MPC controllers.

---

# 25. Key References

1. Zhang, X. et al. (2026). *Reinforcement learning for traffic signal control in large-scale transportation networks: a systematic literature review*. Artificial Intelligence Review. DOI: 10.1007/s10462-026-11676-6.
2. Xiao, F. et al. (2025). *Advances in reinforcement learning for traffic signal control: a review of recent progress*. DOI: 10.1093/iti/liaf009.
3. Wei, H. et al. (2019). *CoLight: Learning Network-level Cooperation for Traffic Signal Control*. CIKM. DOI: 10.1145/3357384.3357902.
4. Yoon et al. (2021/2022). *Transferable traffic signal control: Reinforcement learning with graph centric state representation*. Transportation Research Part C.
5. Wang et al. (2024). *A large-scale traffic signal control algorithm based on multi-layer graph deep reinforcement learning*. Transportation Research Part C. DOI: 10.1016/j.trc.2024.104582.
6. Song, X. et al. (2024). *Cooperative traffic signal control through a counterfactual multi-agent deep actor critic approach*. Transportation Research Part C 160:104528.
