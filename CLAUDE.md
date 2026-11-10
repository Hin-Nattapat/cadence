# CADENCE — Working Rules

How code and documents are written in this repository, for humans and agents alike. The
reasoning is in `docs/specs/2026-08-22-project-direction.md`; this file is what to follow.

**CADENCE is a controller-agnostic platform** for network-aware adaptive traffic signal
control on real-world road networks, built on a validated SUMO core. RL is one controller
family running on it, not the shape of it (`PD-D01`, `ARCH-D01`). Current milestone and
roadmap: `docs/DIRECTION.md`.

## Read first

| Task | Read |
|---|---|
| any Python, written, changed or reviewed | `docs/STYLE.md`, in full |
| anything | `docs/DIRECTION.md` |
| simulation, network, scenario | `research/CADENCE_SUMO_SIMULATION_RESEARCH.md` |
| state, contract, safety, metrics | `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` |
| a controller of any kind | that family's file, via `research/INDEX.md` |
| fixed-time or actuated tuning | `research/CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` |
| reward, observation, RL setup | `research/CADENCE_RL_TSC_RESEARCH.md` |
| why the project exists | `docs/ORIGIN.md` |

`research/INDEX.md` §6 lists known defects in the corpus; check it before trusting a single
passage.

## Two zones (`PD-D07`)

```
Zone A — PLATFORM CORE     simulation/  traffic/  control/  experiments/  metrics/
         The measuring instrument. If it is wrong, every experiment ever run is void.
         TDD, mypy --strict, unit suffixes, frozen state, stable interfaces.

Zone B — STUDIES           studies/<NN>-<slug>/
         The lab notebook. Append-only, never retro-refactored, duplication tolerated.
         Configs and results are immutable artifacts. Formatted and linted only.
```

Zone A never knows Zone B exists: no `import studies.*`, no `if study_name == ...`.

## Boundaries

| Rule | Source |
|---|---|
| `traci` / `libsumo` are imported only under `simulation/sumo/` | `ARCH-D02`, `AP-03` |
| Raw lamp strings (`"GGrrG"`) live only in the signal safety layer | `ARCH §13` |
| Controllers consume canonical domain state, never raw simulator data | `ARCH-D03` |
| Controllers request actions; the safety layer owns legal transitions | `ARCH-D04`, `AP-04` |
| KPI and metric code never imports reward code | `ARCH-D05`, `AP-05` |
| The simulation core holds no RL concept (policy objects, replay buffers, PPO, DQN) | `AP-02` |
| An MPC-style controller never receives future simulator truth | `ARCH-D07` |

The first is enforced by ruff's banned-api list and `tests/test_architecture.py`, the second
by `tests/test_architecture.py` alone. Each of the others gains its own architecture test
in the milestone that writes the code it governs.

## Documentation anti-rot (`PD-D06`)

- **A claim that can be a test is a test,** not a comment: a comment rots silently, a test
  rots loudly.
- **Cite decision IDs** (`-> MP-D02`), never prose headings. The registry
  is `research/decisions.yaml`.
- **When the doc-consistency check fails,** re-read the section and state the outcome:
  meaning changed means fix the code; wording only means
  `cadence docs approve <ID> --reason "..."`. The hash is never updated to silence it.
- **An `adopted` decision's meaning is never edited.** Issue a new ID, mark the old one
  `superseded`, point it at the replacement.

## Milestone discipline

Follow `docs/DIRECTION.md` §2 and build only the current milestone: no RL code before M4, no
Max-Pressure before M8, and no MPC, MARL or GNN unless an experiment demands it and it is
agreed first. Building the next milestone early is unreviewed scope.

## Done means `make check`

Run `make check` (through `rtk proxy` where it is installed) and paste the real output before claiming anything passes. If
tests fail, say so with the output; if a step was skipped, say that. A plan status flip is a
change the suite reads, so run the check after the last flip, not before it.

## Commits and pull requests

Commit freely while working. **Before a pull request, regroup the branch into 3 to 6
commits**, each a coherent unit a reviewer can read on its own (the plan, the toolchain, a
subsystem, what ties them together, the closing docs). `git log --oneline` should show the
shape of the work; `fix: address review round 2` does not.

- Regroup only before the branch is pushed; after that, only if the maintainer asks.
- Regroup with `--no-verify`, then run `make check` on the tip. `pre-commit` stashes unstaged
  changes before each hook, which manufactures a tree no commit represents.
- The tip is green. Claim an intermediate commit green only after checking it out and
  running the suite.

## Language

Discussion with the maintainer is in **Thai**. Code, comments, documents, commit messages
and identifiers are in **English**. The one exception is `docs/CODEBASE.md`, written in Thai
so the maintainer can reload the structure of a Python codebase he does not work in daily.
It is an orientation guide, not a decision record; keep it in Thai.

## Research and knowledge agents

Two local Codex CLI agents carry project knowledge and research (design:
`docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md`).

- Project facts, rationale, decisions or option evaluation:
  `uv run python tools/project_agents.py knowledge '<question>'`.
- Research, when the user asks for it or the Knowledge Agent's answer is missing,
  contradictory, uncited or plausibly stale:
  `uv run python tools/project_agents.py research '<question>'`. Before an automatic research
  call, tell the user why.

**Research is written only by the Research Agent,** into `research/addenda/*.md`,
`research/references.bib` and its temporary handoff ledger. Every other file under
`research/` is immutable to it, so a correction arrives as a dated addendum. Claude's own edits
there are limited to governance updates of `research/INDEX.md` and
`research/decisions.yaml`; it reviews a research diff, reruns the Knowledge Agent against
the updated corpus, and only then commits. `tools/protect_research_hook.py` enforces this for
file-editing tools; a `Bash` command that edits `research/` is not intercepted, so that half
is a rule with no mechanical guard.

## Where the work stands

The plan file that `docs/DIRECTION.md` §1 names carries one status line under each
`### Task` heading:

`status: todo | doing | done | dropped` `added: YYYY-MM-DD` — optional note

`make status` renders it, and a `SessionStart` hook prints it at the top of every session.
The maintainer never writes these lines: flip a task's status when it starts and when it
ends, and print the rendering both times. Unplanned work becomes a task, with an `added:`
date and the reason it was not foreseen, before it becomes a commit. `tests/test_plan_status.py`
enforces the pointer, the line format, and at most one `doing` task.

## brigade

Work runs on the brigade skills (`recipe`, `cook`, `taste`, `menu`). Their project settings
(issue inbox, the project reviewer) live in `docs/agents/brigade.md`.
