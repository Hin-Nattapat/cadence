# CADENCE — Current Direction

**Document Type:** Living document. Updated as milestones complete.
**Last updated:** 2026-08-24

The reasoning behind everything here is in
`docs/specs/2026-08-22-project-direction.md`. This file is the operational summary.

---

# 1. Status

```
Pre-implementation research        complete
Project direction and conventions  decided  (PD-D01 .. PD-D07)
Implementation                     M1a complete, M1b in progress
Current milestone                  M1 — Canonical State + Metrics
Current plan                       docs/plans/2026-08-27-m1b-metrics.md
```

---

# 2. Milestone Ladder (`PD-D02`)

| | Milestone | Delivers | State |
|---|---|---|---|
| **M0** | Simulation Harness | deterministic SUMO lifecycle, TraCI/libsumo wrapper, scenario loader, seed wiring, event capture | done |
| **M1** | Canonical State + Metrics | lane / movement / intersection / network state, metric registry, teleport capture | current |
| **M1b** | Metrics | metric registry, trip / queue / network metrics, vehicle accounting, `queue_length_m`, `cadence metrics`, `cadence verify-run` | in progress |
| **M2** | Signal Safety + Controller Contract | controller interface, action types, safety and transition executor, action masks, timeout and fallback | |
| **M3** | Validation Controllers | tuned fixed-time, SUMO native actuated — the acceptance test for M2 | |
| **M4** | RL Adapter | Gymnasium adapter, observation builder v1, action mapping, reward v1 | |
| **M5** | PPO (+ DQN reference) | training and evaluation pipelines, checkpointing, multiple seeds | |
| **M6** | Single-Intersection Experiments | fixed vs actuated vs RL on controlled synthetic demand | |
| **M7** | Real-World Intersection | OSM-derived validated intersection. **The demonstration milestone.** | |
| **M8** | Corridor + Max-Pressure | turn-ratio estimation and shared-lane queue attribution (moved here from M1b by `ST-D31`, since Max-Pressure is their first consumer), storage capacity, 3-5 signals, downstream storage, spillback metric | |
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
| 0 | Fixed-time, reasonably tuned | M3 | deterministic reference; must not be deliberately weak (`TC-D09`, `TC-D10`, `TC-D11`) |
| 0 | SUMO native actuated | M3 | how far strong local demand-responsive control goes (`TC-D05`) |
| 1 | PPO | M5 | primary generic RL baseline (`RL-D07`) |
| 1 | DQN | M5 | discrete-action reference connecting to the RL-TSC literature |
| 2 | Max-Pressure, queue-based | M8 | training-free network-aware baseline (`MP-D01`) |
| — | Capacity-aware pressure, MPC, MARL, GNN | unscheduled | supported by the architecture; not on the roadmap |

---

# 7. Carried into M1

Recorded at the end of M0 so that M1 starts from a written record rather than someone's
recollection. All four are now taken, at M1a; each row records where.

| # | What M0 left | Where it landed |
|---|---|---|
| 1 | `StepResult` and `EventLog.to_parquet` are shaped for events alone | `StepResult` grew a `state` payload (canonical state); `events.parquet` stays events-only and `RunRecorder` is a sibling writer, not an extension (`ST-D08`). |
| 2 | `RunManifest` records no run outcome | `terminal_time_s`, `step_count`, and `termination_reason` (`drained` / `horizon` / `aborted`) are recorded on every run (`ST-D10`). |
| 3 | `cadence_dirty` is compared as a plain boolean | `cadence_dirty_digest` hashes `git diff HEAD` plus `git status --porcelain -uall`; hashed, not rejected (`ST-D11`). |
| 4 | `validation.py` is a second Zone A surface handling `sumolib` | Moved to `simulation/sumo/validation.py`; every SUMO surface — `traci`, `libsumo`, `sumolib` — now lives under `simulation/sumo/` (`ST-D12`). |

## Carried into M1b

Found by the whole-branch review at the end of M1a, and deliberately not patched there.
Both are preconditions of M1b's first item, not improvements to schedule after it.

| # | What M1a leaves | Why it belongs to M1b |
|---|---|---|
| 1 | The cross-tab's per-lane turn split is unverified (`ST-D31`, superseding `ST-D22`) | A permutation confined to the movements one lane serves relabels 74% of the table and changes no assertion in the suite, because `LaneTurnCount` carries no vehicle key. The deadline splits: the **writer** change lands at M1b, because every run written before it is permanently unreconcilable; the **estimator** that consumes it moves to M8 with the rest of the turn-ratio work. |
| 2 | The privilege split bounds code, not data (`ST-D23`) | `state/traversal.parquet` carries per-vehicle turn identity and `evaluation/tripinfo.parquet` carries `departLane`; together they reconstruct 89% of the privileged cross-tab's vehicle-steps. The import ban and the allowlist test hold; a file read is fenced by nothing. `ST-D18`'s reasoning is about what a controller could see online, and the partition exists to bound an offline loader — the two have to be reconciled before the first loader is written. |

## Deferred minor findings

Triaged at the end of M0 and judged not load-bearing. Recorded rather than discarded.

- ~~`tests/conftest.py` — the `repo_root` fixture is defined and never consumed.~~ **Consumed
  at M1a**, by the integration tests that read a run directory.
- `config_digest` is implicitly coupled to `BaseModel.model_dump()`'s output shape; a
  future Pydantic major could change the digest silently. `uv.lock` is committed, so such
  a bump is itself a commit.
- `_HASH_CHUNK_BYTES` carries rationale rather than provenance.
- `tools/build_s0_scenario.py`'s `CAR_MAX_SPEED_MPS = 13.9` is commented as "50 km/h", but
  50 km/h is 13.888… m/s and `netgenerate` posts 13.89. The fleet is therefore 0.01 m/s
  faster than every lane it drives on, and 16.8% of measured `mean_speed_mps` rows sit above
  the posted limit because of it. Found at M1a by the test that first asserted the bound.
  Not fixed there: correcting the constant regenerates both scenarios and re-measures nine
  frozen numbers for a hundredth of a metre per second.
- `ruff format` splits each SUMO `--flag` from its value, so the pairing that carries the
  meaning of an argument vector is no longer adjacent. A `(flag, value)` tuple list that is
  flattened would keep each pair atomic.
- `--no-step-log` and `--duration-log.disable` carry no comment, unlike every other
  explicitly forced flag.
- `test_event_is_frozen` asserts on the exception message rather than
  `isinstance(error, dataclasses.FrozenInstanceError)`.
- `SumoConnection.__enter__` can leak a SUMO subprocess if `binding.start()` raises after
  `Popen` — that path is inside traci's own `start()` and is not reachable from
  `connection.py`.

---

# 8. Open Decisions

| ID | Question | Must be resolved by |
|---|---|---|
| `PD-Q01` | Scenario site and demand data source | before M7 |
| `PD-Q02` | Whether CADENCE needs a replay viewer of its own | not before M8 |

`PD-Q01` includes the choice between an established scenario (InTAS, LuST, MoST) and a Thai
site, the demand-realism level (L1 / L2 / L3), and how motorcycle-dense traffic is handled.
Full framing and selection criteria are in the spec, §11.

---

## PD-Q02 — visualisation, and the state of the SUMO GUI

Lowest priority. Recorded so the evidence does not have to be gathered twice.

**Plots carry more of the load than an animated map, and they arrive nearly free.** M1
builds the metric registry regardless, so plotting is reading Parquet and drawing. A map
viewer is a separate project no milestone requires, and no paper contains an animation.
The four-panel diagnostic that established S0's credibility was matplotlib over
`--fcd-output`, `--summary-output` and `--tripinfo-output`, and its five measured
quantities each agreed with the traffic-light program independently.

The one question plots answer poorly is *where* congestion propagates across a network,
which is the Study 1 thesis — but that question only becomes real at M8. A spillback
timeline per link, ordered upstream to downstream, shows propagation as a diagonal without
any map.

**On the SUMO GUI: it is X11-only on macOS, and the situation is better than a stale
reading suggests.** `sumo-gui` links FOX against X11; there is no Cocoa build, and SUMO's
"native macOS bundles" are launchers around the same binaries. `eclipse-sumo#17272`
reports the GUI failing on macOS Tahoe and blames `XQuartz#438` — but **that XQuartz issue
was closed on 2026-05-18**, and `XQuartz#497`, filed against macOS 26.5.2 specifically, was
closed on 2026-08-10 with the maintainer stating it is resolved in `2.8.7_beta2`. XQuartz
is actively maintained: four releases between July and August 2026, 86 issues closed in six
months, last commit 2026-08-18. A beta build is therefore worth trying before concluding
the GUI is unavailable, and `2.8.6` stable is not sufficient on 26.5.x.

If a viewer is ever built, three constraints from the M0 measurements apply:

- **It reads a run directory and nothing else** — never `import cadence.simulation`, never
  SUMO. It is a third kind of thing: not the measuring instrument, not a study, a tool.
- **FCD does not scale to the browser unconverted.** Measured at 135 bytes per
  vehicle-record: S0 is 1.9 MB, but an M8 corridor over an hour is 73–244 MB per run and a
  five-controller five-seed matrix is 1.8–6.1 GB. A conversion step belongs in the design
  from the start, not after S0 makes the naive approach look fine.
- **Overlays are blocked on milestones, not on effort.** Network geometry, vehicle
  animation, traffic-light state and export are possible today. Queue and occupancy
  overlays need M1's canonical state; a spillback overlay needs M8's metric definition;
  controller comparison needs more than one controller.

Two things the original sketch omitted and should carry: the manifest's provenance
(scenario, seed, controller, commit) visible on the frame, since a video without it proves
nothing about which run produced it; and jumping to an event rather than watching linearly,
for which `events.parquet` is already the index.

---

# 9. Non-Goals

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

# 10. Where Things Live

```
README.md                             what CADENCE is
CLAUDE.md                             working rules, conventions, test strategy
docs/CODEBASE.md                      what exists and how it fits together
docs/guide/                           dated read-only snapshots of that guide, as web pages
docs/ORIGIN.md                        why the project exists; lessons from 2020
docs/DIRECTION.md                     this file
docs/specs/                           dated decision records, immutable once accepted
research/INDEX.md                     the research corpus
research/decisions.yaml               every decision identifier
scenarios/<id>/v<N>/                  versioned scenario definitions
studies/<NN>-<slug>/                  experiments and their results
```
