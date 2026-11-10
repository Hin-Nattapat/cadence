# P2-01 Status moves to the tracker

> Written 2026-11-10 · a record of decisions as of that date, never updated after close · the current domain lives in `CLAUDE.md`, `docs/roadmap/cadence.md` and `docs/learn/overview.md`

## Problem

"Where does the work stand?" has four answers that nothing keeps in agreement:
`docs/DIRECTION.md` §1 (current milestone and plan), §2 (the ladder's State column), the
status lines inside the M2 plan file, and, since the roadmap landed, GitHub milestones and
issues. `DIRECTION.md` §7 adds a fifth: a backlog whose rows carry their own status
("now taken", strikethrough). Starting P2-02 today would mean flipping the same fact in two
places. Separately, `CLAUDE.md`'s anti-rot section prescribes a `cadence docs approve`
command and a content-hash check, neither of which exists (#11). What makes the shape
non-obvious: the old status machinery is enforced by tests and a session hook, so it has
to be replaced, not merely deleted, or a new session opens knowing nothing.

## Usage

- A new Claude Code session opens in the repo. The `SessionStart` hook runs
  `uv run python tools/work_status.py` and prints, for the current phase, the milestone
  title, closed / total tickets and each open ticket; offline or without `gh`, it prints
  nothing and exits 0.
- An agent asked "where does the work stand?" reads `docs/roadmap/cadence.md` for
  definitions and GitHub for status, live, as `CLAUDE.md` says.
- An agent hits unplanned work: it opens an issue or revises the roadmap through `/menu`
  before committing it.
- The doc-consistency check fails: `CLAUDE.md` tells the agent what `check_decisions`
  actually checks and how to resolve it, with no reference to a command that does not exist.

## Shape

`tools/work_status.py` (mypy `--strict`, like every tool):

```python
@dataclass(frozen=True, slots=True)
class Milestone:
    title: str
    open_count: int
    closed_count: int

@dataclass(frozen=True, slots=True)
class Ticket:
    number: int
    title: str

def current_milestone(milestones: Sequence[Milestone]) -> Milestone | None
def render(milestone: Milestone, open_tickets: Sequence[Ticket]) -> str
def main() -> int
```

- `current_milestone` is pure: among titles matching `^P(\d+) `, the lowest phase number
  with `open_count > 0`; if none has open tickets, the lowest phase number; no match → `None`.
- `render` is pure and deterministic: tickets in ascending `number`.
- `main` is the edge: it calls `gh` through `subprocess.run` with a timeout, parses JSON,
  and returns 0 whatever happens (`gh` missing, non-zero exit, timeout, bad JSON, no
  milestone), printing nothing on any failure. It never raises.
- Status is owned by GitHub; definitions by the roadmap. Nothing in the repo stores status.

## Decisions

- Status lives in GitHub milestones and issues; definitions in the roadmap, because two
  owners with disjoint jobs cannot drift (rejected: keep plan status lines alongside,
  because that is the drift this ticket removes).
- A `SessionStart` hook reads GitHub through `gh`, because the maintainer wants a session
  to open knowing where the work stands (rejected: no hook, because a fresh session would
  not know until asked).
- The hook fails silent and always exits 0, because a session must open offline and the
  status is a convenience, not a gate.
- The current phase is the lowest-numbered open milestone with open tickets, because P3–P9
  stay open and empty until `/menu` fills them.
- `DIRECTION.md` §7 is removed: rows still open become `noticed` issues (with a `phase:`
  label where the row names a destination: the cycle boundary → P2; jam spacing and
  turn-ratio estimation → P8), the deferred minor findings become one issue, and finished
  rows live in git history, because §7 holds status the tracker now owns. The `_SCHEMAS`
  row is already P2-02's scope and gets no issue. Noticed issues carry a label, never a
  milestone, so the milestone counts tickets only.
- `CLAUDE.md`'s anti-rot section states what `check_decisions` does today (registered ID,
  existing source file, dependable status) and that `PD-D06`'s content-hash layer and the
  approve command are not built, because a rule pointing at a missing command misleads
  every agent that reads it. `PD-D06`'s meaning is not edited. Closes #11.

## Comps

none

## Out of scope

- Building `PD-D06`'s content-hash layer or a `cadence docs approve` command.
- `DIRECTION.md` §3–§6 and §8–§10, beyond pointers.
- Specs, `research/`, anything under `src/`.
- Native GitHub "blocked by" links between tickets.

## Done when

Proven at seam: `make check`, and the hook script run by hand.

### Agent checks
- [ ] `rtk proxy make check` → exit 0, Documentation consistency OK, pytest passes
- [ ] `git grep -n "plan_status\|make status\|docs/programs\|Current plan" -- . ':!docs/specs' ':!docs/plans' ':!docs/roadmap' ':!docs/learn'` → no output
- [ ] `test ! -e docs/plans/2026-09-06-m2-signal-plan-and-executor.md && test ! -e docs/programs` → exit 0
- [ ] `uv run python tools/work_status.py` → first line names `P2 Signal Safety + Controller Contract`, then the open P2 tickets
- [ ] `uv run pytest tests/test_work_status.py -q` → passes, including the cases where `gh` is missing, not executable, exits non-zero, times out or returns bad JSON (each: no output, return 0)
- [ ] `grep -n "docs approve" CLAUDE.md` → no output
- [ ] `grep -n "Carried into" docs/DIRECTION.md` → no output
- [ ] `gh issue list --label noticed --state open` → the §7 issues exist

### Smoke
- [ ] Open a fresh Claude Code session in the repo; the first thing shown is the P2 milestone and its open tickets.

## Issues closed
- #14
- #11

## CONTEXT.md changes

none

## Size

single job, because it is one slice (where status is read) of about four steps.
