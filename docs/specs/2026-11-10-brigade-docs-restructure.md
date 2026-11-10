# Agent-facing docs restructured for brigade

> Written 2026-11-10 · a record of decisions as of that date, never updated after close · the current domain lives in `CLAUDE.md` and `docs/DIRECTION.md`

## Problem

CADENCE moved from the prompt-corner skills to brigade on 2026-11-10. The agent-facing
documents still describe the old flow and carry three structural faults. CLAUDE.md is 310
lines loaded on every turn and mixes working rules, Python style, testing strategy, process
and history; one paragraph (§14's `xfail(strict=True)`) describes a test marker that no
longer exists. A Codex station (the sous-chef today, possibly the cook) reads only
AGENTS.md, which does not exist, so it sees none of CADENCE's rules. And brigade's `taste`
has no project reviewer to run, although agent review is the maintainer's only deep review.
Finished milestone plans (~8,800 lines) and prompt-corner's settings file are sediment.
What makes the shape non-obvious: code comments cite CLAUDE.md by section number, so moving
a section breaks them, and every spec is the `source:` of a registered decision, so specs
cannot be deleted while plans can.

## Usage

- A Claude Code session opens in the repo. It loads CLAUDE.md (short: what CADENCE is, the
  zones, the boundaries, the anti-rot rules, milestone discipline, git, language, research
  agents, where work stands, brigade). When it first touches a `.py` file, Claude Code also
  loads the style rules through the path-scoped rule file.
- A Codex sous-chef or cook starts in the repo. It loads AGENTS.md, which says `lang: th`
  and sends it to CLAUDE.md, and from there to STYLE.md before any Python.
- `taste` reaches a diff and reads `docs/agents/brigade.md`. Its `reviewers: ./` line names
  the CADENCE reviewer agent, which runs the boundary probes and reports findings against
  CLAUDE.md and STYLE.md.
- A reader meets `# PD-D04` in a comment where `CLAUDE.md §4` used to be, and the decision
  registry resolves it.

## Shape

| document | owns | loaded |
|---|---|---|
| CLAUDE.md | project identity, Zone A/B, boundaries, doc anti-rot, milestone discipline, done-means-`make check`, git and commit regroup, language, research agents, plan status (unchanged mechanism), brigade pointer, read-first table | every Claude turn |
| AGENTS.md | `lang: th` and one pointer to CLAUDE.md | every Codex / brigade run |
| STYLE.md (docs) | how Python is written in CADENCE: principles, layout, data and types, units and identifiers, errors, naming, functions, seams, determinism, comments, testing, tooling, what the tools already cover | Claude: path-scoped on `**/*.py` and `pyproject.toml`; others: via CLAUDE.md |
| reviewer agent | the review checklist and the probes it must execute | dispatched by taste |
| brigade settings | `inbox: gh`, `reviewers: ./ <reviewer agent>` | read by brigade skills |

Each rule lives in exactly one of these. CLAUDE.md points at STYLE.md and never restates it;
the reviewer cites CLAUDE.md and STYLE.md and restates only the probes it runs.

## Decisions

- CLAUDE.md is canonical and AGENTS.md is a pointer holding `lang: th`, because that is the
  owner's established pattern in phinit and Codex reads only AGENTS.md (no
  `project_doc_fallback_filenames` in the Codex config) (rejected: AGENTS.md canonical with
  CLAUDE.md importing it, because it diverges from phinit for no gain).
  (source: `~/.codex/config.toml`, phinit `AGENTS.md`, checked 2026-11-10)
- Python style moves out of CLAUDE.md into STYLE.md, loaded path-scoped through a
  `.claude/rules/style.md` symlink, because CLAUDE.md is paid on every turn and style
  matters only when Python is touched (rejected: keep in CLAUDE.md, because it is sprawl).
- STYLE.md takes phinit's structure and CADENCE's content: CLAUDE.md §4, §5 and §7 move in
  whole in meaning; phinit's general rules (functions before classes, two cases before an
  abstraction, no `utils.py` module names, module order, keyword-only arguments beyond the
  obvious first, named return types instead of bare tuples, `raise … from`, narrow catches,
  `Protocol` seams) are added **for new and touched code only**, with no retrofit.
  (rejected: an error hierarchy, because CADENCE has none and too little user-facing input
  to need one; rejected: only rules the code already follows, because the maintainer chose
  the forward-only adoption.)
- The "what the tools already cover" table is built from CADENCE's own ruff selection
  (`E, F, W, I, N, UP, B, SIM, TID, ANN, RUF`), its `TID251` banned-api list, mypy
  `--strict`, the architecture tests and `check_decisions`; phinit-only tools are not copied.
- Comments and messages that cite `CLAUDE.md §<n>` cite a decision ID instead (§4 →
  `PD-D04`, §5 → `PD-D05`, §6 → `PD-D06`, §7's registry rule → `PD-D06`, §7's property-test
  rule → STYLE.md's testing section by name of the file only), because §6 forbids heading
  citations and section numbers are headings by another name.
- The reviewer is a Claude agent definition on `model: opus` that executes probes (git grep
  for simulator imports and lamp strings outside their owners, bare-unit names in the diff,
  the architecture tests, `make check`) rather than only reading, because the maintainer
  relies on agent review as the deep review and its value came from executed probes.
- The commit regroup rule (3 to 6 commits before a PR) stays, because the maintainer chose
  it over brigade's one-commit-per-step history.
- Plan status lines, `make status`, the SessionStart hook and the plan-status tests stay
  unchanged in this job, because M2's remaining tasks have no other status source until
  `/menu` creates their issues; a later job removes them.
- Finished plans (M0, M1a, M1b, plan-status tracking, CLI research agents) and
  `.claude/house.md` are deleted, because git history keeps them and nothing sources a
  decision from them. Every spec is kept, because each is a registered decision source.
  The current M2 plan and program map stay until `/menu` replaces them.
- The stale `xfail(strict=True)` paragraph is dropped, because the marker no longer exists.

## Comps

none

## Out of scope

- Moving status to GitHub issues and removing the plan-status machinery (a later job, after `/menu`).
- `/menu` for the rest of M2.
- Any file under `research/`.
- Retrofitting existing code to the newly adopted style rules.
- The gitignored local review artifacts from the M2 phase-1 gate.
- docs/CODEBASE.md content beyond its pointers to CLAUDE.md sections.

## Done when

Proven at seam: `make check` on the branch tip, plus the greps below.

### Agent checks
- [ ] `rtk proxy make check` → exit 0; ruff, mypy, Documentation consistency OK, pytest all pass
- [ ] `git grep -n "CLAUDE.md §\|CLAUDE.md\` §\|CLAUDE.md section" -- src tests tools` → no output
- [ ] `wc -l CLAUDE.md` → at most 150
- [ ] `git grep -n "xfail(strict" CLAUDE.md` → no output
- [ ] `test -L .claude/rules/style.md && head -5 .claude/rules/style.md` → a `paths:` frontmatter naming `**/*.py`
- [ ] `grep -n "^lang: th" AGENTS.md` → one line
- [ ] `grep -n "^reviewers: ./ " docs/agents/brigade.md` → one line naming the reviewer agent file, which exists
- [ ] `git ls-files docs/plans docs/superpowers/plans .claude/house.md` → only the M2 signal-plan-and-executor plan and this job's own plan
- [ ] `git grep -n "house.md\|prompt-corner" -- CLAUDE.md AGENTS.md docs/STYLE.md docs/DIRECTION.md README.md` → no output

### Smoke
- [ ] Open a fresh Claude Code session in the repo, ask "which style rules apply to a new function in `src/cadence/control/`?", expect an answer drawn from STYLE.md after a `.py` file is read.

## Issues closed

none

## CONTEXT.md changes

none (the project has no CONTEXT.md; domain terms live in CLAUDE.md and the research corpus)

## Size

single job, because it is one vertical slice (the documents an agent loads) of about five steps with no expand–contract.
