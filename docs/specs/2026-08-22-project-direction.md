# CADENCE — Project Direction and Engineering Conventions

**Document Type:** Design Specification
**Status:** Accepted
**Date:** 2026-08-22
**Supersedes:** milestone ladders in `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` §20 and
`research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §31; resolves `DEV-Q01`–`DEV-Q05`.

---

> ## Addendum — 2026-08-22, after acceptance
>
> This document repeatedly cites `CADENCE_INITIAL.md` and
> `CADENCE_V1_IMPLEMENTATION_HANDOFF.md`. Both were **removed from the repository** in the
> commit that followed this one, after the restructuring described below. They remain
> retrievable in full from git, in the commit titled
> *"docs: add baseline research corpus and project direction spec"*.
>
> Their content was distributed as follows:
>
> | Content | New home |
> |---|---|
> | origin, background, lessons from the 2020 project | `docs/ORIGIN.md` |
> | OSM import, network strategy, deadlock vs gridlock, spillback, vehicle behaviour, heterogeneity, calibration, definition of done | `research/CADENCE_SUMO_SIMULATION_RESEARCH.md` |
> | scenario progression S0–S3, traffic regimes, generalisation families, non-goals, role of LLMs | `docs/DIRECTION.md` |
> | test strategy | `CLAUDE.md` §7 |
> | research questions, "research still needed" | `research/INDEX.md` |
> | everything else | already duplicated in `research/`, or superseded by this document |
>
> `research/CADENCE_RESEARCH_STATUS.md` was also removed; `research/INDEX.md` replaces it.
>
> Citations below are left unchanged. They are historical references, accurate as of the
> date of this document, and the documentation consistency checker (PD-D06) must support
> that category rather than treating them as broken links.
>
> No decision in this document is altered by this addendum.

---

# 1. Purpose

Pre-implementation research is complete, but two of its output documents disagree on the
order in which controller families should be built, and the project title asserts a method
(Reinforcement Learning) that the research explicitly refuses to commit the architecture to.

This document resolves those conflicts, fixes the engineering conventions, and defines the
gate into implementation planning. It does not revisit any accepted research finding.

---

# 2. Project Goals, Ranked

The ranking below is the tiebreaker for every decision in this document.

| # | Goal | Weight |
|---|---|---|
| 1 | **Personal closure** — finish what the 2020 thesis could not: a working RL controller on a simulator that can be trusted | Primary |
| 2 | **Engineering quality** — an architecture worth being proud of, which is also what makes 3 and 4 cheap | Strong |
| 3 | **Long-lived platform** — other controller families can plug in later; possible open source | Derived from 2 |
| 4 | **Publication** — a result presentable to an academic advisor, and possibly a paper | Weakest, but real |

Goal 1 means the project must reach a working RL controller before enthusiasm runs out.
Goal 2 means it must get there without shortcuts that make the result untrustworthy.
The rest of this document is the reconciliation of those two.

---

# 3. PD-D01 — Two-Layer Identity

CADENCE is separated into a **platform** and the **studies** that run on it. They have
different names, different lifetimes, and different engineering standards.

```
PLATFORM  — CADENCE
            A controller-agnostic platform for network-aware adaptive traffic
            signal control on real-world road networks.
            Lifetime: years. Standard: production-grade.

STUDY 1   — Network-Aware Adaptive Traffic Signal Control Using Reinforcement
            Learning on Real-World Urban Road Networks
            Lifetime: one research question. Standard: reproducible lab notebook.
```

The Study 1 title is the previous formal project title, unchanged. It is re-scoped from
naming the project to naming the first study.

## Rationale

- A result where Max-Pressure outperforms RL is a finding under this framing, not a failure.
  Under the previous framing there was exactly one acceptable outcome.
- "Using Reinforcement Learning" is the part CADENCE shares with the 2020 project.
  "Network-Aware" is the part that is new. The load-bearing word is not the method.
- Adding MPC, Max-Pressure, or MARL later requires no rebranding.
- This is standard practice for research infrastructure (SUMO, CityFlow, RESCO, Gymnasium):
  the platform is never named after an algorithm, because algorithms turn over faster than
  the platform does.

## Consequences

- `README.md` is written as platform documentation with a "Studies" section.
- The GitHub repository description matches the platform framing.
- `CADENCE_INITIAL.md` §2.1 gains a note recording the re-scope.
- Paper titles are decided at M7–M9, not now.

---

# 4. PD-D02 — Milestone Ladder

## The conflict being resolved

| | `ARCHITECTURE_CONTROLLER_CONTRACT.md` §31 | `V1_IMPLEMENTATION_HANDOFF.md` §20 |
|---|---|---|
| M3 | classical baselines incl. Max-Pressure | RL adapter |
| M4 | capacity-aware pressure | PPO / DQN |
| M5 | MPC | single-intersection experiments |
| M6 | RL adapter | real-world intersection |
| Max-Pressure / MPC | before RL | deferred past RL v1 |

## Accepted ladder

```
M0  Simulation Harness
    Deterministic SUMO lifecycle, TraCI/libsumo wrapper, scenario config loader,
    seed wiring, raw state and event capture, version metadata, smoke tests.

M1  Canonical State + Metrics
    LaneState, MovementState, IntersectionState, NetworkState.
    Trip / queue / network / failure metrics. Metric registry. Teleport capture.

M2  Signal Safety + Controller Contract
    TrafficController interface, ControllerAction types, signal legality metadata,
    safety and transition executor, action masks, timeout and fallback contract.

M3  Validation Controllers                       <-- added relative to the handoff ladder
    Tuned fixed-time. SUMO native actuated.
    These are the acceptance test for M2, not a research baseline expansion.

M4  RL Adapter
    Gymnasium adapter, observation builder v1, action mapping, reward v1,
    episode and reset semantics. Random agent completes episodes.

M5  PPO (+ DQN reference)
    Training pipeline, evaluation pipeline, checkpointing, multiple seeds.

M6  Single-Intersection Experiments
    Fixed-time vs actuated vs RL on controlled synthetic demand. Diagnostics.

M7  Real-World Intersection                      <-- goal 1 and goal 4 land here
    OSM-derived validated intersection, explicit lane connections, legal TLS,
    controlled demand variants. This is the demonstration for the advisor.

M8  Corridor + Max-Pressure
    3-5 signals. Downstream storage, spillback metric, queue propagation.
    Max-Pressure enters here.

M9  Network-Aware RL vs Max-Pressure
    Oversaturation and spillback regimes. The Study 1 research claim.

MPC, capacity-aware pressure variants, MARL, GNN: architecturally supported,
not scheduled. They enter only when an experiment demands them.
```

## Rationale for M3 preceding M4

Fixed-time and SUMO actuated cost very little (actuated is native to SUMO), and they buy
what an RL-first ladder lacks: the controller contract gets exercised by controllers that
can be read in full before a neural network is attached to it. A contract defect found at
M3 costs an afternoon. The same defect found at M5 is indistinguishable from a reward bug,
a hyperparameter problem, or an observation normalisation error.

They are also the two baselines an advisor asks about first, obtained as a side effect.

## Rationale for Max-Pressure at M8 rather than M3

At an isolated intersection with unconstrained downstream links, Max-Pressure degenerates
to serving the phase with the largest weighted queue. The downstream term — the reason
Max-Pressure is interesting to this project at all — only carries information when
neighbouring intersections exist. Placing it at M8 puts it where the algorithm is
meaningful, and makes it the direct opponent of network-aware RL at M9, which is the
Study 1 thesis.

This is a scheduling decision, not a weakening of `CM-D07`. No strong claim about RL
superiority is made before M9, where Max-Pressure is present.

## Accepted risk

If Max-Pressure outperforms network-aware RL at M9, this is discovered late. By then goals
1, 2 and 3 are already met, and the result is publishable. This risk is accepted.

---

# 5. PD-D03 — Toolchain

Resolves `DEV-Q01` through `DEV-Q05`.

| Concern | Decision | Rationale |
|---|---|---|
| Language | **Python 3.12** | TraCI, libsumo, Gymnasium, SB3, and the entire RL-TSC literature. 3.13/3.14 outrun the RL ecosystem. |
| Package / env manager | **uv** | Real lockfile, manages the Python version itself, no pyenv or conda layer. |
| SUMO | **`eclipse-sumo`, `libsumo`, `traci`, `sumolib`, all pinned at `1.27.1` via uv** | Verified macOS arm64 wheels (cp39–cp314). SUMO becomes a locked dependency rather than machine state. Resolves `DEV-Q02` more strongly than the handoff anticipated. |
| Simulator binding | **Switchable TraCI / libsumo via config** | libsumo is materially faster in-process but has no GUI and no parallel clients per process. TraCI for inspection, libsumo for training. This is a further reason the wrapper of `ARCH-D02` must be strict. |
| Lint + format | **ruff** | Replaces black, isort, flake8. |
| Type checking | **mypy `--strict`** | See "Why strict" below. |
| Config validation | **Pydantic v2**, `frozen=True`, `extra="forbid"` | A mistyped config key must be an error, not a silent default. |
| Testing | **pytest** + **hypothesis** | Hypothesis encodes physical invariants: a queue cannot exceed its lane, occupancy stays in [0,1]. |
| RL library | **Stable-Baselines3** — PPO primary, DQN reference | `DEV-Q03`, `RL-D07`. An established implementation keeps our own RL bugs out of the research result. |
| Config format | **YAML as artifact, Pydantic as schema** | Nested scenario and controller configs read better in YAML than TOML. A YAML file is data that can be hashed for the reproducibility manifest; a typed Python config is code, and hashing it is meaningless. Resolves `DEV-Q04`. |
| Result storage | **Parquet via Polars**; CSV only for small human-readable summaries | Per-vehicle, per-second output grows quickly. |
| Training curves | **TensorBoard** (ships with SB3) | No external service, no account, no server to maintain. |
| Experiment tracking | **Filesystem + `manifest.json` per run** | Matches the reproducibility manifest of `ARCH` §27. Zero infrastructure. |
| State versioning | **String identifiers**, e.g. `ppo:v1`, `rl_downstream:v1` | Resolves `DEV-Q05`. See PD-D04. |

## Why strict typing, specifically here

Most of this code will be written by an AI agent. Strict typing and schema validation
therefore act mainly on the agent, not on the human maintainer. The usual trade-off —
stricter tooling slows the author down — largely does not apply. What remains is the
benefit: mistakes surface as type errors instead of as unexplained shapes in a results plot.

## Compute

Apple Silicon, no CUDA. Traffic-signal RL policies are small MLPs, where CPU frequently
outperforms MPS, and the bottleneck is SUMO rather than the network. The performance
strategy is libsumo plus parallel environments on CPU, not GPU acceleration.

---

# 6. PD-D04 — Naming Conventions

## R1 — Every physical quantity carries its unit as a suffix

```
length_m        time_s          speed_mps       accel_mps2
queue_count_veh flow_vehph      occupancy_ratio saturation_pct
```

Bare `length`, `speed`, `time`, or `queue` are rejected in review.

The failure mode this prevents is not a crash. It is a `km/h` value used as `m/s`,
producing a plausible-looking number that is wrong, and staying wrong until someone
writes it into a report.

## R2 — Every identifier kind is its own type

```python
LaneId         = NewType("LaneId", str)
EdgeId         = NewType("EdgeId", str)
MovementId     = NewType("MovementId", str)
IntersectionId = NewType("IntersectionId", str)
PhaseId        = NewType("PhaseId", int)
```

In SUMO, `"e1"` is an edge and `"e1_0"` is a lane. Both are `str`. Confusing them is the
most common defect class in SUMO-based code, and mypy can eliminate it for free.

## R3 — Anything with an interpretation carries a version

```
controller_id  = "ppo:v1"
scenario_id    = "corridor_peak:v2"
obs_adapter_id = "rl_downstream:v1"
metric_id      = "spillback_event_v1"
```

Changing observation or action semantics requires a version bump
(`CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §28).
A metric definition is never edited; a `_v2` is added.

## R4 — Temporal scope is explicit

Per `CADENCE_INITIAL.md` §15.4, observations and rewards use current values or bounded
windows, never episode-cumulative averages.

```
halting_count_now          arrived_count_window_60s      waiting_total_episode_s
```

`avg_waiting` is rejected: averaged over which interval?

## R5 — Run and scenario layout

```
scenarios/<scenario_id>/v<N>/
    network.net.xml
    demand.rou.xml
    scenario.yaml

studies/01-network-aware-rl/runs/<UTC timestamp>__<scenario>__<controller>__seed<N>/
    manifest.json           commit, SUMO version, hashes, seed, full resolved config
    config.resolved.yaml
    metrics.parquet
    events.parquet
```

## R6 — No abbreviations outside a short whitelist

Whitelisted: `id`, `tls`, `veh`, `osm`, `rl`, `mp`, `mpc`.
Everything else is spelled out: `configuration` not `cfg`, `max_pressure` not `mp_ctrl`.

---

# 7. PD-D05 — Comment Policy

The default is **no comment**. Each comment must belong to one of four categories or be
deleted. The categories, not a line count, are the rule; the budgets are secondary.

| Category | Content | Budget |
|---|---|---|
| **PROVENANCE** | Where a number, formula, or definition came from | 2 lines |
| **GOTCHA** | Counter-intuitive behaviour, SUMO quirk, "looks wrong but is not" | 2 lines |
| **DECISION** | Why this approach rather than the more obvious one | 2 lines |
| **CONTRACT** | What a module or public interface guarantees | 5 lines, module docstrings and public interfaces only |

**Mandatory:** every numeric constant carries a PROVENANCE comment. No exceptions.

**Forbidden:** `Args:` / `Returns:` blocks (type hints already carry this);
any comment that restates the code in English.

**Longer than the budget:** the explanation belongs in `research/` or `docs/`, and the
comment becomes a reference to a decision ID (see PD-D06).

A line count alone was rejected as the rule: it compresses necessary explanation into
cryptic fragments while permitting a worthless one-line comment on every statement. The
expectation is that roughly 80% of functions in Zone A carry no comment at all, because
`compute_queue_length_m(lane: LaneState) -> float` already says everything.

Zone B (`studies/`) is exempt. A lab notebook may be verbose.

```python
"""Capacity-aware pressure computation for movement-level control.

Extends classical Max-Pressure with finite downstream storage.
Consumes canonical state only, never TraCI (ARCH-D02).
"""

# HCM through-movement default: 1.9 s headway -> ~1895 veh/h/lane.
SATURATION_HEADWAY_S = 1.9

def movement_pressure(m: MovementState) -> float:
    # Classical MP subtracts the raw downstream queue; we gate on remaining storage
    # so a long but empty link is not penalised. -> MP-D01
    if m.downstream_available_storage_ratio < SPILLBACK_GUARD_RATIO:
        return 0.0
    return (m.queue_count_veh - m.downstream_queue_count_veh) * m.turn_ratio
```

Identifiers in code examples throughout this document are illustrative; the authoritative
list is `research/decisions.yaml`.

---

# 8. PD-D06 — Documentation Anti-Rot

Comments and references decay as code and research documents drift apart. A checker that
only verifies that a link resolves will not detect the dangerous case, which is a reference
that still resolves but now points at different content. Four layers address this, ordered
by return on effort.

## Layer 0 — Minimise what can rot (free; rules only)

**0.1 — If a claim can be a test, it must be a test, not a comment.**
A comment rots silently; a test rots loudly.

```python
# Rejected: comment
# Queue length can never exceed lane length.

# Required: property test
@given(...)
def test_queue_never_exceeds_lane_length(...):
    assert result.queue_length_m <= lane.length_m
```

**0.2 — Reference decision IDs, never prose headings.**
The research documents already define 69 stable identifiers across six groups
(`ARCH-D`, `CM-D`, `TC-D`, `MP-D`/`MP-H`, `MPC-D`/`MPC-H`, `RL-D`); see §12. A heading can be renamed;
a decision ID cannot change meaning, because changing one's mind issues a new ID and marks
the old one superseded.

## Layer 1 — Decision registry (`research/decisions.yaml`)

Collects the identifiers already scattered across eight documents into one
machine-readable index.

```yaml
ARCH-D02:
  statement:  "Controllers access CADENCE traffic-domain interfaces, never TraCI directly."
  source:     CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md#arch-d02
  status:     adopted          # proposed | adopted | superseded | retracted
  section_sha: 7b21ee40
  enforced_by: tests/test_architecture.py::test_no_traci_outside_simulation

MPC-D06:
  statement:  "Predictive spillback control requires a spillback-capable internal model."
  source:     CADENCE_OPTIMIZATION_MPC_RESEARCH.md#mpc-d06
  status:     adopted
  section_sha: a3f9c1d2
  used_by:
    - control/mpc/storage_model.py
```

`enforced_by` makes visible which decisions have an automated guard and which rest only on
discipline.

## Layer 2 — Section content hash

The registry stores a hash of the referenced section as it read when the reference was
written. `make check` recomputes and fails on mismatch.

```
FAIL  MPC-D06  content changed since last review
      research/CADENCE_OPTIMIZATION_MPC_RESEARCH.md#mpc-d06
      expected a3f9c1d2  ->  got 9e4b0071
      depended on by: control/mpc/storage_model.py:88

      Resolve by either:
        (a) meaning changed  -> update the code, then update the hash
        (b) wording only     -> cadence docs approve MPC-D06 --reason "..."
```

Hashes are computed over normalised content (whitespace collapsed, markdown formatting
stripped, lowercased) so typographic edits do not fire.

## Layer 3 — Bidirectional validation

Rot travels in both directions, and the second is usually forgotten.

| Direction | Symptom | Guard |
|---|---|---|
| doc changed, code unaware | reference still resolves, meaning moved | Layer 2 |
| code deleted or moved | `used_by` points at nothing | Layer 3 |
| decision superseded | code still implements the retired decision | Layer 3 |

The third row is the most valuable: it forces a change of mind in the research to travel
all the way into the code.

## Required behaviour when the check fails

Updating a hash to silence the checker is prohibited. The referenced section must be re-read
and the outcome stated: if the meaning changed, the code is corrected; if only the wording
changed, the reference is approved with a one-line justification.

Editing an `adopted` decision in a way that changes its meaning is prohibited. Issue a new
ID, mark the previous one `superseded`, and point it at the replacement.

## Honest limitation

No tool can determine whether meaning has changed. This system converts silent rot into
loud rot and forces a human judgement at the moment it fires. False positives on rewording
are the accepted cost.

## Build order

| Layer | When | Effort |
|---|---|---|
| 0 | day one | free, rules only |
| 1 and 3 | M0 | ~150 lines |
| 2 | M1, at the first real prose reference | ~100 lines |

---

# 9. PD-D07 — Zone Boundaries

```
Zone A — PLATFORM CORE          simulation/  traffic/  control/  experiments/
         The measuring instrument. Production standard, and stricter than usual:
         TDD, mypy --strict, unit suffixes, frozen state objects, stable interfaces,
         version bump on any semantic change.
         If the instrument is wrong, every experiment ever run with it is void.

Zone B — STUDIES                studies/<NN>-<slug>/
         The lab notebook. Append-only, not retro-refactored, duplication tolerated,
         configs are immutable artifacts.
         An experiment that has already been run must not change meaning.
         Zone B is formatted and linted, but is not held to `mypy --strict` and does
         not require tests.
```

**The boundary rule: Zone A must not know Zone B exists.** No `import studies.*` in core,
no `if study_name == ...`.

## Enforcement

| Rule | Mechanism |
|---|---|
| no `studies.*` import in Zone A | ruff `TID251` banned-api + `tests/test_architecture.py` |
| no `traci` / `libsumo` import outside `simulation/sumo/` | ruff `TID251` with per-file ignore + architecture test |
| no raw lamp strings (`"GGrrG"`) outside the signal layer | architecture test |
| KPI code never imports reward code (`AP-05`, `ARCH-D05`) | architecture test |
| every emitted metric is registered with name, version, unit, definition | metric registry validator |
| every doc reference resolves, is `adopted`, and matches its hash | doc consistency checker |

Architectural decisions become tests rather than sentences in a document.

---

# 10. Tooling to Build

| Tool | Purpose | Milestone |
|---|---|---|
| `make check` | ruff + mypy + pytest + architecture + registry + docs, in one command | M0 |
| `tests/test_architecture.py` | zone and dependency boundaries as tests | M0 |
| metric registry validator | fails if a metric is emitted without a registry entry | M1 |
| doc consistency checker | Layers 1–3 of PD-D06 | M0 (L1, L3), M1 (L2) |
| `cadence validate-scenario` | junction, TLS, lane connection, and route validation (Phase 0) | M0 |
| `cadence run` | scenario x controller x seed matrix | M1 |
| `cadence verify-run <dir>` | re-executes a past run from its manifest and compares | M1 |
| `cadence docs approve <ID>` | records a reviewed wording change | M0 |
| pre-commit | ruff, mypy, architecture test | M0 |

---

# 11. PD-Q01 — Deferred: Scenario Site and Demand Data

**Deferred by decision. Must be resolved before M7.**

## Framing established

The demand-realism requirement follows from the claim being made, not from the word
"real-world" in the title.

| Claim level | Demand requirement | Cost |
|---|---|---|
| L1 — real topology, controlled demand regimes A–D | synthetic, explicitly declared | low |
| L2 — comparable to published benchmarks | an established scenario | low |
| L3 — reproduces traffic at this specific location | calibration against measurements | high |

None of the four project goals requires L3. Most RL-TSC literature operates at L1 or L2.
The load-bearing phrase in the Study 1 title is *real topology* — unequal link lengths,
unequal lane counts, turning lanes, one-way streets, irregular geometry — which is precisely
what the 2020 synthetic grid lacked.

## Candidate sites

| Option | Strengths | Costs |
|---|---|---|
| Established scenario (InTAS Ingolstadt, LuST Luxembourg, MoST Monaco) | calibrated demand, pre-validated network, literature comparability | no personal meaning, cannot be observed directly, right-hand traffic |
| Thai site | personal meaning and sustained motivation, direct observation and counting, left-hand traffic exercises the platform | OSM quality uncertain (lane counts, turn restrictions, signal tagging), demand must be built, motorcycles |
| Mixed: Thai intersection at M7, established corridor at M8–M9 | meaning where it is cheapest to obtain; rigour where the claim is heaviest; running both networks is itself generalisation evidence (`CADENCE_INITIAL.md` §22) | two networks to maintain |

Verified as available and maintained: `lcodeca/LuSTScenario`, `lcodeca/MoSTScenario`,
`silaslobo/InTAS` (most recently updated).

## Motorcycles — recorded so it is not rediscovered late

Motorcycles are a large share of Thai traffic and filter to the front of the queue at red.
This alters saturation flow, discharge rate, and the meaning of queue length in metres.
SUMO defaults (Krauss, LC2013) do not represent it; the sublane model
(`--lateral-resolution`) partially can, at the cost of calibration and simulation speed.

Three responses, to be chosen at M7: avoid it by site selection; accept and declare it as a
limitation; or make it the subject of Study 2. It must not be mixed into Study 1, where it
would be impossible to separate its effect from the controller's.

## Selection criteria for whenever this is taken up

1. The site must actually congest — without oversaturation the spillback research question
   cannot arise in simulation.
2. The site should be observable in person if a Thai site is chosen.
3. OSM coverage must be inspected before committing: lane counts, turn restrictions,
   `highway=traffic_signals` presence.
4. A corridor needs 3–5 signals on one arterial at workable spacing.
5. Left-hand traffic requires the corresponding SUMO network build settings.

---

# 12. Reconciliation with Existing Documents

## Superseded

| Location | Superseded by |
|---|---|
| `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` §20, milestones M0–M7 | PD-D02 |
| `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` §31, milestones M0–M7 | PD-D02 |
| `CADENCE_V1_IMPLEMENTATION_HANDOFF.md` §22, `DEV-Q01`–`DEV-Q05` | PD-D03 |
| `CADENCE_INITIAL.md` §2.1, formal title as the project title | PD-D01, re-scoped to Study 1 |

## Unchanged and still binding

Every decision in the research corpus remains binding. The authoritative index is
`research/decisions.yaml` (77 entries, generated and validated against the source documents):

| Group | Decisions | Hypotheses |
|---|---|---|
| `ARCH-D` architecture and controller contract | 12 | — |
| `CM-D` cross-method comparison | 9 | — |
| `TC-D` traffic engineering and actuated control | 8 | — |
| `MP-D` / `MP-H` Max-Pressure | 12 | 5 |
| `MPC-D` / `MPC-H` optimization and MPC | 11 | 4 |
| `RL-D` reinforcement learning | 8 | — |
| `PD-D` / `PD-Q` project direction (this document) | 7 | 1 deferred |

An earlier draft of this section under-counted several groups, and an example referred to
`MP-D01` as not yet existing. Both were wrong: `CADENCE_MAX_PRESSURE_RESEARCH.md` states at
§8 that no Max-Pressure decision is adopted, then records `MP-D01`–`MP-D12` in a register
later in the same file. The registry exists so that a document contradicting itself is
caught mechanically rather than propagated.

In particular `CM-D03` ("initial implementation must support Fixed-Time, Actuated, and
external plugin controllers before RL-specific code") is satisfied by M3 preceding M4, and
`CM-D07` ("strong claims about RL require comparison with Max-Pressure and a competent
predictive/non-learning method where feasible") is satisfied at M9 for the Max-Pressure
half. The predictive half is deliberately unscheduled under its own "where feasible"
clause; any Study 1 claim must state this explicitly rather than imply MPC was beaten.

The Phase 0–5 roadmap in `CADENCE_INITIAL.md` §24 remains valid as a conceptual arc.
PD-D02 is its operational form.

---

# 13. Decision Register

| ID | Decision |
|---|---|
| PD-D01 | CADENCE is a platform; the previous formal title becomes the title of Study 1. |
| PD-D02 | Milestone ladder M0–M9: contract first, validation controllers before RL, Max-Pressure at the corridor stage. |
| PD-D03 | Python 3.12, uv, SUMO 1.27.1 via PyPI, ruff, mypy --strict, Pydantic v2, pytest + hypothesis, SB3, YAML configs, Parquet results. |
| PD-D04 | Unit suffixes, `NewType` identifiers, versioned semantic identifiers, explicit temporal scope. |
| PD-D05 | Comments default to none and must fall into PROVENANCE, GOTCHA, DECISION, or CONTRACT. |
| PD-D06 | Four-layer documentation anti-rot: tests over comments, decision IDs over headings, registry, content hash, bidirectional validation. |
| PD-D07 | Zone A / Zone B separation with boundaries enforced as tests. |
| PD-Q01 | Scenario site and demand source deferred; must be resolved before M7. |

---

# 14. Gate

With PD-D01 through PD-D07 accepted, the next step is an implementation plan for M0–M2.
No production code is written before that plan is reviewed.
