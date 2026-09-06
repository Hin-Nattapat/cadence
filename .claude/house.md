---
repos: [.]
base-branch: main
programs-dir: docs/programs
# Python test files here run 300-550 lines; 400 cannot be cut along a file boundary.
review-chunk-lines: 600
review-max-chunks: 4
---

# house rules

Per-project settings for the `prompt-corner` skills. `CLAUDE.md` is the authority on how code
and documents are written; this file only says how the skills run here.

## Default flow
1. Milestone spec in `docs/specs/` → one Opus agent review of the spec → maintainer confirms.
2. Plan in `docs/plans/` with `### Task N:` headings and `status:` lines (`CLAUDE.md` §14);
   flip the status when a task starts and ends, and print `make status` both times.
3. Implement on a feature branch; small commits; a fix round commits as `fix: review round <n>`.
4. `notes-call` per gate (3–4 gates per milestone, at subsystem edges, not per task).
5. Smoke, then STOP and wait for the maintainer; O bullets are decided there.
6. On "push and pr" → the git tail below.

## Git tail
Regroup to 3–6 commits counted against `origin/main` (`CLAUDE.md` §10): plan, subsystem,
the thing that ties them, closing docs. Use `--no-verify` while regrouping, then
`rtk proxy make check` on the tip and paste the raw output. `git push -u`, open the PR with
the session trailer, return the URL. Never merge. Delete any handoff file for the feature.

## Smoke
Everything here is a CLI: run it yourself. `make check`; `cadence run` on
`scenarios/s0_turning/v1` and `scenarios/s0_turning_oversaturated/v1`; `cadence metrics` and
`cadence verify-run` on the results. Nothing is handed over as a checklist.

## Runtime
No long-running service. `call-board` reports `runtime: not checked` and that is correct here.

## Reference locations
- `docs/DIRECTION.md` — roadmap and what each milestone carries forward (§7)
- `research/decisions.yaml` — every decision id; `research/INDEX.md` §6 — known defects in the corpus
- `research/CADENCE_ARCHITECTURE_CONTROLLER_CONTRACT.md` — state, contract, safety, metrics
- `research/CADENCE_SUMO_SIMULATION_RESEARCH.md` — SUMO behaviour; read before any TraCI premise
- `research/CADENCE_TRAFFIC_ENGINEERING_RESEARCH.md` — fixed-time and actuated tuning

## Known consumers
None outside this repository. Inside it: `studies/` (M6+) reads run directories and `metrics/`;
controllers (M3, M4, M8) consume the M2 contract.

## Review additions
- Every physical quantity carries its unit suffix (`_m`, `_s`, `_mps`, `_veh`, `_ratio`); bare
  `length`, `speed`, `time`, `queue` are findings (`CLAUDE.md` §4).
- No `traci` / `libsumo` / `sumolib` import outside `simulation/sumo/`; no raw lamp strings
  (`"GGrrG"`) outside the signal safety layer (`CLAUDE.md` §3, enforced by `tests/test_architecture.py`).
- Comments: no `DECISION:` / `PROVENANCE:` prefixes, only `GOTCHA:`; every numeric constant
  has a one-line provenance; no `Args:` / `Returns:` blocks (`CLAUDE.md` §5).
- Reference decision ids (`ST-D30`), never prose headings (`CLAUDE.md` §6). A claim that can
  be a test must be a test.
- Zone A is mypy `--strict`; a metric definition is never edited, it gets `_v2`.
- Raw output rule: run checks through `rtk proxy` so the token filter cannot hide an exit code.
