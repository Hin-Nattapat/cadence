# CADENCE — Working Rules

Authoritative for how code and documents are written in this repository, for humans and
agents alike. The reasoning behind these rules is in
`docs/specs/2026-08-22-project-direction.md`; this file is what to follow.

---

# 1. What This Project Is

**CADENCE is a controller-agnostic platform** for network-aware adaptive traffic signal
control on real-world road networks, built on a validated SUMO core. RL is one controller
family running on it, not the shape of it (`PD-D01`, `ARCH-D01`).

Current milestone and roadmap: `docs/DIRECTION.md`.

---

# 2. Two Zones, Two Standards (`PD-D07`)

```
Zone A — PLATFORM CORE     simulation/  traffic/  control/  experiments/
         The measuring instrument. If it is wrong, every experiment ever run is void.
         TDD, mypy --strict, unit suffixes, frozen state, stable interfaces.

Zone B — STUDIES           studies/<NN>-<slug>/
         The lab notebook. Append-only. Not retro-refactored. Duplication tolerated.
         Configs and results are immutable artifacts.
         Formatted and linted, but not mypy --strict, and tests are not required.
```

**Zone A must not know Zone B exists.** No `import studies.*`, no `if study_name == ...`.

---

# 3. Boundaries That Must Not Be Crossed

| Rule | Source |
|---|---|
| No `traci` / `libsumo` import outside `simulation/sumo/` | `ARCH-D02`, `AP-03` |
| No raw lamp strings (`"GGrrG"`) outside the signal safety layer | `ARCH §13` |
| Controllers consume canonical domain state, never raw simulator data | `ARCH-D03` |
| Controllers request actions; the safety layer owns legal transitions | `ARCH-D04`, `AP-04` |
| KPI / metric code never imports reward code | `ARCH-D05`, `AP-05` |
| No RL concepts (policy objects, replay buffers, PPO, DQN) in the simulation core | `AP-02` |
| An MPC-style controller never receives future simulator truth | `ARCH-D07` |

Two of these — no `traci`/`libsumo` import outside `simulation/sumo/`, and no raw lamp
strings outside the signal safety layer — are enforced today by `tests/test_architecture.py`,
not by good intentions. The other five govern controller, reward, and MPC code that does not
exist until M2 or later; each must gain its own architecture test as that code is written.

---

# 4. Code Rules (`PD-D04`)

**Units are part of the name.** Every physical quantity carries its unit as a suffix.

```
length_m  time_s  speed_mps  accel_mps2  queue_count_veh  flow_vehph
occupancy_ratio (0-1)  saturation_pct (0-100)
```

Bare `length`, `speed`, `time`, `queue` are rejected. The failure this prevents is not a
crash; it is a `km/h` value used as `m/s`, staying plausible and wrong until it reaches a
report.

**Identifiers are distinct types.** In SUMO `"e1"` is an edge and `"e1_0"` is a lane; both
are `str`. Use `NewType`: `LaneId`, `EdgeId`, `MovementId`, `IntersectionId`, `PhaseId`.

**Anything with an interpretation carries a version.**
`"ppo:v1"`, `"corridor_peak:v2"`, `"rl_downstream:v1"`, `"spillback_event_v1"`.
Changing observation or action semantics requires a version bump. A metric definition is
never edited; add `_v2`.

**Temporal scope is explicit.** `halting_count_now`, `arrived_count_window_60s`,
`waiting_total_episode_s`. Never `avg_waiting` — averaged over what?

**Determinism.** No wall-clock, no unseeded randomness, no dict-ordering dependence in
Zone A. Every source of randomness is seeded from experiment metadata (`AP-06`).

**No magic numbers.** Every numeric constant is a named constant with a provenance comment.

**No abbreviations** outside the whitelist `id, tls, veh, osm, rl, mp, mpc`.

---

# 5. Comments (`PD-D05`)

**Default is no comment.** Each one must fall in a category or be deleted.

| Category | Content | Typical length |
|---|---|---|
| PROVENANCE | where a number, formula, or definition came from | 1-2 lines |
| GOTCHA | counter-intuitive behaviour, SUMO quirk | 1-2 lines |
| DECISION | why this approach rather than the obvious one | 1-2 lines |
| CONTRACT | what a module or public interface guarantees | up to ~5 lines, module docstrings and public interfaces only |

Lengths are guidance, not a limit enforced by counting. The binding test is whether every
line carries information the code and its types do not. A comment that keeps growing past
its guidance is a signal the explanation belongs in `research/` or `docs/` behind a
decision ID — not a signal to compress it into something cryptic.

Mandatory: every numeric constant gets a PROVENANCE comment.
Forbidden: `Args:` / `Returns:` blocks; any comment restating the code in English.
Longer than budget: it belongs in `research/` or `docs/`, referenced by decision ID.

Expect roughly 80% of Zone A functions to carry no comment. `compute_queue_length_m(lane:
LaneState) -> float` already says everything.

The four categories are a test a comment must pass to earn its place, **not a tagging
syntax**. Do not prefix comments with `PROVENANCE:` or `DECISION:`. The one exception is
`GOTCHA:`, which may be written out when the comment warns about behaviour that looks
wrong but is not — there the label tells a reader to stop and take it seriously.

Zone B is exempt.

---

# 6. Documentation Anti-Rot (`PD-D06`)

**If a claim can be a test, it must be a test, not a comment.** A comment rots silently; a
test rots loudly.

**Reference decision IDs, never prose headings.** `-> MP-D02`, not
`-> research/..., "Finite Storage"`. Headings get renamed; IDs cannot change meaning.
The registry is `research/decisions.yaml`.

**When the doc-consistency check fails, never update the hash to silence it.** Re-read the
section and state the outcome: meaning changed means fix the code; wording only means
`cadence docs approve <ID> --reason "..."`.

**Never edit an `adopted` decision's meaning.** Issue a new ID, mark the old one
`superseded`, point it at the replacement.

---

# 7. Testing

Testing is a primary engineering concern in Zone A, not an afterthought. Write the test
first.

## Unit
Storage-capacity calculation, queue normalisation, action validation, phase-transition
generation, metric aggregation.

## Property (hypothesis)
Physical invariants that must hold for any input: queue length never exceeds lane length,
occupancy stays within `[0, 1]`, phase elapsed time never exceeds max green.

## Architecture
Every rule in §3, as an executable test.

## Contract
Every controller, internal or external, must pass: `initialize`, `reset`, a valid `decide`
result, timeout behaviour, `close`.

## SUMO integration
| Test | Asserts |
|---|---|
| network smoke | the simulation starts and progresses |
| queue discharge | a known queue under green clears within expected bounds |
| downstream storage | a finite downstream link can reach congestion and spillback |
| signal transition | a requested phase produces a valid yellow / clearance sequence |
| reproducibility | the same seed and config produce matching output |

## Registry
Every emitted metric has a registry entry with name, version, unit, and definition.
Every decision reference resolves, is `adopted`, and matches its recorded content.

---

# 8. Milestone Discipline

Follow `docs/DIRECTION.md` §2. Do not build ahead of the current milestone.

- No RL code before M4.
- No Max-Pressure before M8.
- No MPC, MARL, or GNN at all unless an experiment demands it and it is agreed first.

Building the next milestone early is not progress; it is unreviewed scope.

---

# 9. Before Claiming Anything Is Done

Run `make check` and paste the real output. Never assert that something passes without
having run it. If tests fail, say so with the output. If a step was skipped, say that.

---

# 10. Commits and Pull Requests

Commit freely while working. Small, frequent commits are the safest way to work, and a
review loop depends on being able to see each round separately.

**Regroup them before opening a pull request.** A branch arrives for review as **3 to 6
commits**, each a coherent unit someone can read on its own — the plan, the toolchain, the
guardrails, a subsystem, the thing that ties them together, the closing docs. Not one
commit per fix round, and not one squashed lump either.

The test is whether a reviewer can read `git log --oneline` and see the shape of the work.
`fix: address review round 2` tells them nothing: it is bookkeeping from a process that is
over by the time anyone reads it.

The branch tip must be green, and `make check` is run on it after the regroup. Do not claim
the intermediate commits are individually green unless you checked each one out and ran the
suite — on a branch that bootstraps its own toolchain, the early commits predate the tools
and cannot be.

Regrouping is a history rewrite, so it is safe only before the branch is pushed; after
that, regroup only if the maintainer asks. Use `--no-verify` while regrouping and verify
the tip afterwards: `pre-commit` stashes unstaged changes before each hook run, which
manufactures an intermediate state no commit actually represents — a tracked file reverts
to its old content while untracked files stay, and checks that read the working tree fail
against a tree that never existed.

---

# 11. What to Read Before Designing

| Task | Read first |
|---|---|
| anything | `docs/DIRECTION.md` |
| simulation, network, scenario | `research/CADENCE_SUMO_SIMULATION_RESEARCH.md` |
| state, contract, safety, metrics | `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` |
| a controller of any kind | that family's file, via `research/INDEX.md` |
| fixed-time or actuated tuning | `research/CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` |
| reward, observation, RL setup | `research/CADENCE_RL_TSC_RESEARCH.md` |
| why the project exists | `docs/ORIGIN.md` |

`research/INDEX.md` §6 lists known defects in the corpus. Check it before trusting a single
passage.

---

# 12. Conversation

Discussion with the maintainer is in **Thai**. All code, comments, documents, commit
messages, and identifiers are in **English**.

One exception, and it is the only one: `docs/CODEBASE.md` is written in **Thai**. Its whole
purpose is that the maintainer can reload the structure of a Python codebase he does not
work in daily, and a document that fails at that fails entirely. It is an orientation guide,
not a decision record and not research — nothing depends on it, and it says so at the top.
Do not translate it back.

---

# 13. Research and Knowledge Agents

Two local Codex CLI agents carry project knowledge and research so Claude does not have to
hold or produce either from memory. Design: `docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md`.

Call `uv run python tools/project_agents.py knowledge '<question>'` for project facts,
rationale, decisions, or option evaluation. Call
`uv run python tools/project_agents.py research '<question>'` when the user asks for
research explicitly, or when the Knowledge Agent's answer is missing, contradictory,
uncited, or plausibly stale. Before an automatic research call, tell the user why.

**Claude does not write research.** Not through `Write`, `Edit`, `Bash`, or any other tool,
except governance updates to `research/INDEX.md` and `research/decisions.yaml`. A research
diff is the Research Agent's output; Claude reviews it, reruns the Knowledge Agent against
the updated corpus, and only then commits.

The Research Agent writes three destinations and nothing else: `research/addenda/*.md`,
`research/references.bib`, and the temporary handoff ledger. Every other file under
`research/` is immutable to it, whether or not it currently sources an adopted decision, so
a correction arrives as a dated addendum rather than an edit to corpus history.

A `PreToolUse` hook (`tools/protect_research_hook.py`, registered in `.claude/settings.json`)
enforces this for `Write`, `Edit`, `MultiEdit`, and `NotebookEdit`. It does not cover `Bash`: a shell
command that edits `research/` is not intercepted. That half of the rule is a repository
rule with no mechanical enforcement.
