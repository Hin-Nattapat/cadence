# CADENCE — Research Corpus Index

**Document Type:** Living index of the research corpus.
**Last updated:** 2026-08-22

This file replaces `CADENCE_RESEARCH_STATUS.md`, which duplicated the same status table.

---

# 1. Purpose of the Corpus

Broad pre-implementation research is **complete**. Its purpose was to answer one question:

> Given the traffic-control methods that already exist, which problems remain difficult,
> and where can CADENCE add something?

Its governing principle:

> **Do not use AI to rediscover a solution that established traffic engineering already
> solves more simply, safely, and explainably.** A method must earn its complexity.

Open-ended literature review no longer blocks development. Further research is triggered by
an implementation decision, an experiment result, a failure mode, a baseline-selection
question, or a new contribution hypothesis — never by "we should read more".

---

# 2. Tracks

| File | Lines | Decisions | Conclusion |
|---|---|---|---|
| `CADENCE_TRAFFIC_CONTROL_RESEARCH_PLAN.md` | 590 | — | The master map of the landscape. Traffic-responsive signal control long predates deep RL, so CADENCE must define its novelty more precisely than "adaptive traffic lights". |
| `CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` | 516 | `TC-D01`–`D08` | When demand approaches or exceeds capacity, adaptive control should manage queue propagation and protect network throughput, not simply minimise local delay. Switching has a real capacity cost. |
| `CADENCE_SUMO_SIMULATION_RESEARCH.md` | 313 | `SIM-D` reserved | The simulation foundation and its definition of done. Import is not validation. Artificial deadlock must be separable from real gridlock. |
| `CADENCE_MAX_PRESSURE_RESEARCH.md` | 1088 | `MP-D01`–`D12`, `MP-H01`–`H05` | A strong, training-free, network-aware baseline with stability results under stated assumptions. Standard queue-differential pressure does **not** equal physical spillback awareness. |
| `CADENCE_OPTIMIZATION_MPC_RESEARCH.md` | 1518 | `MPC-D01`–`D11`, `MPC-H01`–`H04` | Explicit prediction and constraints are powerful, but model mismatch and computation may erase the advantage. The internal model must never receive future simulator truth. |
| `CADENCE_RL_TSC_RESEARCH.md` | 717 | `RL-D01`–`D08` | RL is a legitimate candidate controller family, but must not define the architecture. Prioritise a clean MDP and evaluation protocol over a novel neural architecture. |
| `CADENCE_MARL_GNN_RESEARCH.md` | 571 | — | Addresses real problems, introduces major new ones. Design for later plug-in; do not require it for v1. |
| `CADENCE_CROSS_METHOD_COMPARISON.md` | 472 | `CM-D01`–`D09` | No controller family dominates every dimension. Therefore CADENCE is a controller-agnostic experimentation platform. |
| `CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` | 886 | `ARCH-D01`–`D12` | The canonical architecture and controller contract. **Single source of truth** for domain objects, the controller interface, the safety layer, metrics, and the reproducibility manifest. |

---

# 3. Decision Registry

`research/decisions.yaml` is the authoritative index of every decision identifier: 110
entries, validated against the source documents.

```
PD-D / PD-Q    9   project direction
ARCH-D        12   architecture and contract
AP             6   architecture principles
CM-D           9   cross-method comparison
TC-D          11   traffic engineering and actuated control (TC-D04 superseded)
MP-D / MP-H   17   Max-Pressure
MPC-D / MPC-H 15   optimization and MPC
RL-D           8   reinforcement learning
ST-D          23   M1a canonical state (ST-D03, ST-D07, ST-D20 superseded)
SIM-D          0   simulation foundation (allocated during M0)
```

Code references decisions **by identifier**, never by heading (`PD-D06` layer 0.2).
Changing the meaning of an adopted decision is prohibited: issue a new identifier and mark
the old one superseded.

---

# 4. Open Research Questions

Recorded so they are not rediscovered. Each becomes actionable at a specific milestone.

## Simulation
See `CADENCE_SUMO_SIMULATION_RESEARCH.md` §10 and §11.

## Adaptive control
1. Which traffic observations are necessary for effective adaptive signal control?
2. How much downstream information is required to prevent spillback?
3. Does RL outperform a strong actuated controller under varying demand?
4. Can a learned policy generalise to traffic patterns not seen during training?
5. How should fairness and starvation be incorporated into evaluation?

## Network coordination
1. When does independent intersection control become insufficient?
2. How much neighbouring information is required?
3. Does MARL provide enough benefit to justify its complexity?
4. Can graph-based representations support transfer between topologies?

## Cross-method
1. When does network awareness become materially better than strong local actuated control?
2. Does finite-storage awareness reduce secondary congestion under oversaturation?
3. Does prediction measurably beat reactive Max-Pressure?
4. Can RL match strong classical and predictive baselines while retaining low online latency?
5. How does controller ranking change across traffic regimes?
6. How sensitive are results to observation fidelity and demand or model mismatch?

---

# 5. Expected Targeted Research

Question-driven, by milestone.

| Milestone | Likely questions |
|---|---|
| M0-M1 | exact SUMO API semantics, detector and queue measurement definitions, OSM preprocessing, teleport interpretation |
| M4 | Gymnasium and SB3 integration details, observation normalisation, episode reset semantics |
| M6 | reward failure modes, RL convergence problems, baseline tuning |
| M8-M9 | corridor coordination, whether MARL or GNN is justified, whether downstream storage representation is sufficient |

---

# 6. Known Issues in the Corpus

Recorded rather than silently fixed, because they motivate `PD-D06`.

| Issue | Status |
|---|---|
| `CADENCE_MAX_PRESSURE_RESEARCH.md` contradicts itself: §8 states no Max-Pressure decision is adopted, while a later register records `MP-D01`–`MP-D12`. | Registry treats the later register as authoritative. The source text is left as-is; a `MP` cleanup pass is deferred to M8. |
| Three documents referenced a "SUMO research checkpoint" that did not exist. | Resolved. The content existed in `CADENCE_INITIAL.md` and now lives in `CADENCE_SUMO_SIMULATION_RESEARCH.md`. |
| Several decisions are labelled "Decision Candidate" in their source text. | Treated as `adopted` in the registry, following the cross-method synthesis and the research gate. |

---

# 7. Superseded Originals

`CADENCE_INITIAL.md` and `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` were removed after their
unique content was distributed to `docs/ORIGIN.md`, `docs/DIRECTION.md`, `CLAUDE.md`, and
`CADENCE_SUMO_SIMULATION_RESEARCH.md`. Everything they contained beyond that was already
duplicated in this corpus or superseded by
`docs/specs/2026-08-22-project-direction.md`.

Both files remain retrievable in full from git, in the commit titled
`docs: add baseline research corpus and project direction spec`.
