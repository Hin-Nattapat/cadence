# CADENCE — Current Direction

**Document Type:** Living document. Updated as milestones complete.
**Last updated:** 2026-08-22

The reasoning behind everything here is in
`docs/specs/2026-08-22-project-direction.md`. This file is the operational summary.

---

# 1. Status

```
Pre-implementation research        complete
Project direction and conventions  decided  (PD-D01 .. PD-D07)
Implementation                     M0 complete, M1 not started
Current milestone                  M1 — Canonical State + Metrics
```

---

# 2. Milestone Ladder (`PD-D02`)

| | Milestone | Delivers | State |
|---|---|---|---|
| **M0** | Simulation Harness | deterministic SUMO lifecycle, TraCI/libsumo wrapper, scenario loader, seed wiring, event capture | done |
| **M1** | Canonical State + Metrics | lane / movement / intersection / network state, metric registry, teleport capture | current |
| **M2** | Signal Safety + Controller Contract | controller interface, action types, safety and transition executor, action masks, timeout and fallback | |
| **M3** | Validation Controllers | tuned fixed-time, SUMO native actuated — the acceptance test for M2 | |
| **M4** | RL Adapter | Gymnasium adapter, observation builder v1, action mapping, reward v1 | |
| **M5** | PPO (+ DQN reference) | training and evaluation pipelines, checkpointing, multiple seeds | |
| **M6** | Single-Intersection Experiments | fixed vs actuated vs RL on controlled synthetic demand | |
| **M7** | Real-World Intersection | OSM-derived validated intersection. **The demonstration milestone.** | |
| **M8** | Corridor + Max-Pressure | 3-5 signals, downstream storage, spillback metric | |
| **M9** | Network-Aware RL vs Max-Pressure | oversaturation and spillback regimes — the Study 1 claim | |

Architecturally supported but **not scheduled**: MPC, capacity-aware pressure variants,
MARL, GNN, hybrid controllers. They enter when an experiment demands them, not before.

---

# 3. Scenario Progression

| ID | Scenario | Purpose | Milestone |
|---|---|---|---|
| **S0** | Deterministic synthetic intersection | integration testing, action and safety validation, metric verification. **Not for research claims.** | M0-M3 |
| **S1** | Controlled single intersection | RL training sanity, fixed vs RL comparison, behaviour diagnostics | M4-M6 |
| **S2** | Real-world single intersection | OSM-validated network. First meaningful result. | M7 |
| **S3** | Small corridor, 3-5 signals | downstream capacity, spillback, network awareness | M8-M9 |

MARL is not required for S3. A centralised or shared RL formulation is sufficient for the
first corridor experiments.

---

# 4. Traffic Regimes

Parameterised variants of a scenario, not separate projects (`TC-D01`, `TC-D03`).

```
A   undersaturated      v/c clearly below 1
B   near saturation     v/c around 1
C   oversaturated       v/c above 1
D   spillback stress    downstream bottlenecks create secondary congestion
```

Regimes C and D are the research-relevant ones for CADENCE. A controller that only wins in
regime A has not addressed the question the project exists to answer.

---

# 5. Generalisation Scenario Families

Training and evaluation scenarios stay explicitly separated (`RL-D05`). A controller is not
successful merely because it performs well on its training distribution.

```
A   uniform demand                  E   sudden traffic surge
B   north/south dominant            F   temporary downstream congestion
C   east/west dominant              G   randomised demand
D   rush-hour transition            H   driver-behaviour variation
```

---

# 6. Baseline Suite

Ordered by when they enter, not by expected strength.

| Tier | Controller | Milestone | Role |
|---|---|---|---|
| 0 | Fixed-time, reasonably tuned | M3 | deterministic reference; must not be deliberately weak (`TC-D04`) |
| 0 | SUMO native actuated | M3 | how far strong local demand-responsive control goes (`TC-D05`) |
| 1 | PPO | M5 | primary generic RL baseline (`RL-D07`) |
| 1 | DQN | M5 | discrete-action reference connecting to the RL-TSC literature |
| 2 | Max-Pressure, queue-based | M8 | training-free network-aware baseline (`MP-D01`) |
| — | Capacity-aware pressure, MPC, MARL, GNN | unscheduled | supported by the architecture; not on the roadmap |

---

# 7. Open Decisions

| ID | Question | Must be resolved by |
|---|---|---|
| `PD-Q01` | Scenario site and demand data source | before M7 |

`PD-Q01` includes the choice between an established scenario (InTAS, LuST, MoST) and a Thai
site, the demand-realism level (L1 / L2 / L3), and how motorcycle-dense traffic is handled.
Full framing and selection criteria are in the spec, §11.

---

# 8. Non-Goals

Not blockers, not on the current roadmap:

```
city-scale simulation            LLM-controlled traffic signals
MARL implementation              production infrastructure integration
Graph Neural Networks            real-world deployment
full stochastic MPC              perimeter control
routing and signal co-optimisation
premature RL algorithm optimisation
every Max-Pressure variant
```

## Role of LLMs

Large Language Models are **not** the traffic-signal decision engine. Control decisions
belong to methods suited to sequential control: reinforcement learning, classical traffic
control, optimisation, or hybrids.

LLMs support the research workflow — experiment configuration, scenario generation,
orchestration, result analysis, failure diagnosis, documentation. A secondary engineering
layer, never a control requirement.

---

# 9. Where Things Live

```
README.md                             what CADENCE is
CLAUDE.md                             working rules, conventions, test strategy
docs/ORIGIN.md                        why the project exists; lessons from 2020
docs/DIRECTION.md                     this file
docs/specs/                           dated decision records, immutable once accepted
research/INDEX.md                     the research corpus
research/decisions.yaml               every decision identifier
scenarios/<id>/v<N>/                  versioned scenario definitions
studies/<NN>-<slug>/                  experiments and their results
```
