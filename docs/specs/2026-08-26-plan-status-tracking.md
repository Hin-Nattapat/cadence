# Plan Status Tracking — Design

**Date:** 2026-08-26
**Status:** draft, awaiting maintainer review

---

## 1. The problem

Two failures, reported by the maintainer on 2026-08-26.

**Losing the thread.** In a long session — or after moving to a new chat — there is no way
to answer *where are we in the plan, what is finished, what is next*. The plan lives in
`docs/plans/`, but progress lives only in the conversation, so it is lost when the
conversation is.

**Patch-on-patch.** When implementation hits a problem, the fix is made in front of the
problem, without re-placing the work against the plan. Nothing records that the fix was
never a planned task, so drift accumulates invisibly.

## 2. Why a new document is not the answer

The repository already has the mechanism and it is dead:

```
docs/plans/2026-08-23-m0-simulation-harness.md    0 of 83 boxes ticked   (M0 complete)
docs/plans/2026-08-24-m1a-canonical-state.md      0 of 76 boxes ticked   (M1a complete)
```

Two completed milestones, 159 checkboxes, none ever ticked. The cause is not a missing
place to write; it is that nothing required writing, and that the boxes sat at the wrong
altitude — `Step 2: Run the tests and watch them fail` is finer than any question anyone
asks of a plan. A second document with the same properties dies the same way.

Two consequences shape everything below:

- **The maintainer never marks status.** The agent marks it; a check catches the agent.
- **The maintainer does not read `docs/plans/*.md`.** The file is machine state. The
  interface is a rendering printed into the session.

## 3. State: task status lines in the plan file

Status lives in the plan file itself. A second file would be a second claim about the same
fact, and would drift — the failure `PD-D06` exists to prevent.

Granularity moves from `Step` to `Task`. Plans already carry `### Task N:` headings, nine
or ten per milestone, which is the altitude the questions are asked at.

The plan file is a CADENCE artifact under `docs/plans/`, not a skill's output. Nothing here
depends on `superpowers` or on `docs/superpowers/`, which this repository does not track. A
hand-written list of ten `### Task N:` headings serves the mechanism exactly as well as one
produced by `writing-plans`; the skill is one way to obtain the file, never a precondition
for status being recorded.

Each task heading is followed by exactly one status line:

```markdown
### Task 4: Canonical state and the per-step extractor
`status: doing` — tests written, estimator not implemented
```

- `status:` is one of `todo`, `doing`, `done`, `dropped`.
- The trailing `— <note>` is optional and free text, shown in the rendering.
- Headings are not edited, so anchors and cross-references survive.

**Unplanned work** is not a separate log. A fix that was not a planned task becomes a new
task appended to the plan, carrying an `added:` date that tasks from the original plan do
not have:

```markdown
### Task 10: Correct CAR_MAX_SPEED_MPS and regenerate both scenarios
`status: doing` `added: 2026-08-26` — found while doing Task 4
```

This is the zoom-out guard, and it is a guard because it is the only way to record the work
at all: unplanned work must be written into the plan before it can be marked, which forces
the work to be placed against the plan at the moment it is invented rather than afterwards.
The renderer counts `added:` tasks and shows the count, so drift is visible rather than
inferred.

## 4. Pointer: which plan is current

`docs/DIRECTION.md` §1 gains one line naming the plan file for the current milestone:

```
Current plan                       docs/plans/2026-08-24-m1a-canonical-state.md
```

Without it the renderer has to guess from filenames. One explicit line is testable; a
naming convention is not.

**A milestone may not open without one.** If `DIRECTION.md` §2 marks a milestone `current`
and §1 names no plan file, the check in §6 fails. This closes the hole where work begins
before any task list exists and therefore has nowhere to be recorded: the cost of opening a
milestone is writing down its tasks, and five lines satisfy it.

## 5. Renderer

`tools/plan_status.py` parses `docs/DIRECTION.md` §1 and the plan file it names, and writes
a fixed-width rendering to stdout. `make status` is the human alias.

```
CADENCE ── M1b  Derived Metrics                       3/9 tasks
──────────────────────────────────────────────────────────────
  ✔ 1  Verify the per-lane turn split                   ST-D22
  ✔ 2  Reconcile the privilege split                    ST-D23
  ✔ 3  Queue attribution split
  ▶ 4  turn_ratio_sliding_window_v1
        tests written, estimator not implemented
    5  The starvation guard
    6  Residual-bias limitation
    7  Derived lane quantities
    8  Correct CAR_MAX_SPEED_MPS, regenerate      added 2026-08-26
    9  M1b review and record
──────────────────────────────────────────────────────────────
  next     Task 4 — write the estimator until the tests pass
  drift    1 task added after the plan was written (8)
──────────────────────────────────────────────────────────────
```

The glyph column carries the status and nothing else; an unplanned task is marked by the
trailing `added` date, which survives the task reaching `done` where a separate glyph would
not. The parser is a module function returning a structure; the rendering is a second function
over that structure. The check in §6 consumes the parse, not the text.

## 6. The gate

A test, `tests/test_plan_status.py`, run by `make check`. Not a `pre-commit` hook.

**Decision, open to challenge at review:** `pre-commit` fires on the maintainer's own
commits and during the branch regroup of `CLAUDE.md` §10, where `--no-verify` is mandatory
and a status hook would be routinely bypassed — a gate that is normally skipped teaches
that skipping it is normal. `make check` is already the point at which `CLAUDE.md` §9 says
work may be called done, which is exactly the moment the status must be true.

The test asserts:

1. `docs/DIRECTION.md` §1 names a plan file, and that file exists. A milestone marked
   `current` in §2 without one is a failure, not an empty rendering.
2. Every `### Task N:` heading in it is followed by a well-formed status line.
3. At most one task is `doing`.
4. If every task is `done` or `dropped`, the milestone is not still marked `current` in
   `DIRECTION.md` §2.
5. Any task numbered above the original plan's highest carries an `added:` date.

**What this does not catch:** a task finished but left at `doing`. No test can know that.
The defence is §7 — the rendering is printed after every task, so a stale marker is wrong
in front of the maintainer within one task rather than at the end of a milestone.

## 7. Display

- **Session start.** A `SessionStart` hook in `.claude/settings.json`, alongside the
  existing `PreToolUse` hook, runs the renderer so every session — including a fresh chat —
  opens with the current position.
- **Task close.** `CLAUDE.md` gains a rule: when a task's status changes, print the
  rendering. This is a repository rule with no mechanical enforcement, like the `Bash` half
  of the research-protection rule.

## 8. Out of scope

- Retrofitting the M0 plan. It is complete and is not the current milestone.
- Retrofitting *step* checkboxes anywhere. All 159 stay untouched, as a record of what the
  old mechanism produced. The M1a plan does gain ten task status lines, all `done`, because
  §1 points at it while M1 is current and §6 requires the current plan to be well-formed.
- Cross-milestone rendering. `DIRECTION.md` §2 already holds the milestone ladder.
- A `--drift` subcommand. The drift line in the rendering is the whole feature.

## 9. Risks

- **The rendering is only as honest as the marker.** Mitigated by §7, not eliminated.
- **`make check` runs the whole suite.** If the status check is wanted more cheaply,
  `make docs-check` is the natural second home; both call the same function.
