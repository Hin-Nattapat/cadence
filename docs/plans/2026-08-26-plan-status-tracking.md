# Plan Status Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current milestone's position — tasks done, task in progress, task next, tasks added after the plan was written — readable from a rendering printed into the session, backed by status lines in the plan file and enforced by the test suite.

**Architecture:** One module, `tools/plan_status.py`, in three layers: a parser that turns `docs/DIRECTION.md` §1 and the plan file it names into frozen dataclasses, a renderer that turns those into fixed-width text, and a `main()` that prints it. `tests/test_plan_status.py` tests the parser and renderer against inline fixtures and then asserts the repository's own files satisfy the invariants. Nothing imports SUMO, nothing imports `src/cadence`.

**Tech Stack:** Python 3.12, stdlib only (`re`, `dataclasses`, `pathlib`), pytest. `tools/` is inside `mypy --strict` (`pyproject.toml` `files = ["src", "tools"]`) and inside ruff's `select = ["E","F","W","I","N","UP","B","SIM","TID","ANN","RUF"]`.

**Spec:** `docs/specs/2026-08-26-plan-status-tracking.md`

## Global Constraints

- `mypy --strict` covers `tools/`. Every function needs annotations, including `-> None`.
- ruff `ANN` is on for `tools/` but off for `tests/` (`per-file-ignores`). Line length 100.
- No magic numbers without a provenance comment (`CLAUDE.md` §4).
- No `Args:` / `Returns:` docstring blocks (`CLAUDE.md` §5). Module docstring is a CONTRACT comment.
- Units-in-names does not apply here: nothing in this module is a physical quantity.
- This is tooling, not Zone A. It must not import `cadence.*`, `traci`, `libsumo`, or `sumolib`.
- Task headings in plan files are `### Task <n>: <title>` where `<n>` may be non-numeric (`6a` exists in the M1a plan). Parse it as a token, never as an `int`.

---

### Task 1: Parse DIRECTION and the plan file

**Files:**
- Create: `tools/plan_status.py`
- Test: `tests/test_plan_status.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Task` (frozen dataclass: `number: str`, `title: str`, `status: str`, `note: str | None`, `added: str | None`), `PlanStatus` (frozen dataclass: `milestone: str`, `plan_path: Path`, `tasks: tuple[Task, ...]`), `parse_direction(text: str) -> tuple[str, str]`, `parse_plan(text: str) -> tuple[Task, ...]`, `load(repo_root: Path) -> PlanStatus`, and the module constants `STATUSES`, `TASK_HEADING_RE`, `STATUS_LINE_RE`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plan_status.py`:

```python
from pathlib import Path

import pytest

from tools.plan_status import (
    PlanStatus,
    Task,
    load,
    parse_direction,
    parse_plan,
)

DIRECTION_FIXTURE = """# CADENCE — Current Direction

# 1. Status

```
Implementation                     M1a complete, M1b not started
Current milestone                  M1 — Canonical State + Metrics
Current plan                       docs/plans/2026-08-24-m1a-canonical-state.md
```
"""

PLAN_FIXTURE = """# A Plan

### Task 1: Fix `_approach_pairs`
`status: done`

Some prose that mentions ### Task in the middle of a line.

### Task 6a: Record what the reviews found missing
`status: doing` — tests written, estimator not implemented

### Task 7: Run artifacts
`status: todo`

### Task 10: Correct CAR_MAX_SPEED_MPS
`status: todo` `added: 2026-08-26` — found while doing Task 6a
"""


def test_parse_direction_reads_milestone_and_plan_path():
    milestone, plan = parse_direction(DIRECTION_FIXTURE)
    assert milestone == "M1 — Canonical State + Metrics"
    assert plan == "docs/plans/2026-08-24-m1a-canonical-state.md"


def test_parse_direction_rejects_a_missing_plan_pointer():
    text = DIRECTION_FIXTURE.replace(
        "Current plan                       docs/plans/2026-08-24-m1a-canonical-state.md\n",
        "",
    )
    with pytest.raises(ValueError, match="Current plan"):
        parse_direction(text)


def test_parse_plan_reads_every_task_in_order():
    tasks = parse_plan(PLAN_FIXTURE)
    assert [t.number for t in tasks] == ["1", "6a", "7", "10"]
    assert tasks[0].title == "Fix `_approach_pairs`"
    assert tasks[0].status == "done"


def test_parse_plan_reads_note_and_added():
    tasks = parse_plan(PLAN_FIXTURE)
    doing = tasks[1]
    assert doing.status == "doing"
    assert doing.note == "tests written, estimator not implemented"
    assert doing.added is None
    unplanned = tasks[3]
    assert unplanned.added == "2026-08-26"
    assert unplanned.note == "found while doing Task 6a"


def test_parse_plan_rejects_a_task_with_no_status_line():
    text = PLAN_FIXTURE.replace("`status: todo`\n\n### Task 10", "\n### Task 10")
    with pytest.raises(ValueError, match="Task 7"):
        parse_plan(text)


def test_parse_plan_rejects_an_unknown_status():
    text = PLAN_FIXTURE.replace("`status: doing`", "`status: nearly`")
    with pytest.raises(ValueError, match="nearly"):
        parse_plan(text)


def test_load_reads_the_repository_files(tmp_path: Path):
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "DIRECTION.md").write_text(DIRECTION_FIXTURE)
    (tmp_path / "docs" / "plans" / "2026-08-24-m1a-canonical-state.md").write_text(PLAN_FIXTURE)
    status = load(tmp_path)
    assert isinstance(status, PlanStatus)
    assert status.milestone == "M1 — Canonical State + Metrics"
    assert len(status.tasks) == 4
    assert isinstance(status.tasks[0], Task)


def test_load_rejects_a_plan_pointer_that_does_not_resolve(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DIRECTION.md").write_text(DIRECTION_FIXTURE)
    with pytest.raises(FileNotFoundError, match="2026-08-24-m1a-canonical-state.md"):
        load(tmp_path)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'tools.plan_status'`.

- [ ] **Step 3: Write the parser**

Create `tools/plan_status.py`:

```python
"""Where the current milestone stands, read from the plan file that holds it.

Parses `docs/DIRECTION.md` section 1 for the current milestone and the plan file it names,
then that plan file for one status line per `### Task` heading. The rendering this feeds is
the interface; the plan file is the state. Nothing here imports cadence, SUMO, or a plan
produced by any particular tool — a hand-written list of task headings parses identically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

STATUSES = ("todo", "doing", "done", "dropped")

TASK_HEADING_RE = re.compile(r"^### Task (?P<number>\S+): (?P<title>.+?)\s*$", re.MULTILINE)

# A task's status line is the first non-blank line under its heading. `added` is present
# only on tasks appended after the plan was written, which is what makes drift countable.
STATUS_LINE_RE = re.compile(
    r"^`status: (?P<status>\w+)`"
    r"(?: `added: (?P<added>\d{4}-\d{2}-\d{2})`)?"
    r"(?: — (?P<note>.+?))?\s*$"
)

_DIRECTION_MILESTONE_RE = re.compile(r"^Current milestone\s+(?P<value>.+?)\s*$", re.MULTILINE)
_DIRECTION_PLAN_RE = re.compile(r"^Current plan\s+(?P<value>.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Task:
    number: str
    title: str
    status: str
    note: str | None
    added: str | None


@dataclass(frozen=True)
class PlanStatus:
    milestone: str
    plan_path: Path
    tasks: tuple[Task, ...]


def parse_direction(text: str) -> tuple[str, str]:
    milestone = _DIRECTION_MILESTONE_RE.search(text)
    if milestone is None:
        raise ValueError("docs/DIRECTION.md section 1 names no 'Current milestone'.")
    plan = _DIRECTION_PLAN_RE.search(text)
    if plan is None:
        raise ValueError(
            "docs/DIRECTION.md section 1 names a 'Current milestone' but no 'Current plan'. "
            "A milestone may not open without a task list."
        )
    return milestone.group("value"), plan.group("value")


def parse_plan(text: str) -> tuple[Task, ...]:
    headings = list(TASK_HEADING_RE.finditer(text))
    tasks: list[Task] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        tasks.append(_parse_task(heading.group("number"), heading.group("title"), body))
    return tuple(tasks)


def _parse_task(number: str, title: str, body: str) -> Task:
    first = next((line for line in body.splitlines() if line.strip()), "")
    match = STATUS_LINE_RE.match(first.strip())
    if match is None:
        raise ValueError(
            f"Task {number} is not followed by a status line. Expected a line such as "
            f"`status: doing` — optional note, found: {first.strip()!r}"
        )
    status = match.group("status")
    if status not in STATUSES:
        raise ValueError(f"Task {number} has status {status!r}; expected one of {STATUSES}.")
    return Task(
        number=number,
        title=title,
        status=status,
        note=match.group("note"),
        added=match.group("added"),
    )


def load(repo_root: Path) -> PlanStatus:
    direction = repo_root / "docs" / "DIRECTION.md"
    milestone, plan_relative = parse_direction(direction.read_text(encoding="utf-8"))
    plan_path = repo_root / plan_relative
    if not plan_path.is_file():
        raise FileNotFoundError(
            f"docs/DIRECTION.md names {plan_relative}, which does not exist."
        )
    return PlanStatus(
        milestone=milestone,
        plan_path=plan_path,
        tasks=parse_plan(plan_path.read_text(encoding="utf-8")),
    )
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: 8 passed.

- [ ] **Step 5: Check types and lint**

Run: `uv run mypy && uv run ruff check tools/ tests/test_plan_status.py && uv run ruff format tools/ tests/test_plan_status.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add tools/plan_status.py tests/test_plan_status.py
git commit -m "feat(tools): parse milestone position out of DIRECTION and the plan file"
```

---

### Task 2: Render the status block

**Files:**
- Modify: `tools/plan_status.py`
- Test: `tests/test_plan_status.py`

**Interfaces:**
- Consumes: `PlanStatus`, `Task`, `load` from Task 1.
- Produces: `render(status: PlanStatus) -> str` and `main() -> int`. `render` returns the block without a trailing newline; `main` prints it and returns `0`, or prints the error to stderr and returns `1`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan_status.py`:

```python
from pathlib import Path

from tools.plan_status import PlanStatus, Task, render

def _status(*tasks: Task) -> PlanStatus:
    return PlanStatus(
        milestone="M1b — Derived Metrics",
        plan_path=Path("docs/plans/x.md"),
        tasks=tasks,
    )


def test_render_shows_the_milestone_and_the_done_count():
    block = render(
        _status(
            Task("1", "Queue attribution split", "done", None, None),
            Task("2", "The starvation guard", "todo", None, None),
        )
    )
    assert "M1b — Derived Metrics" in block
    assert "1/2 tasks" in block


def test_render_marks_each_status_with_its_own_glyph():
    block = render(
        _status(
            Task("1", "Done one", "done", None, None),
            Task("2", "Doing one", "doing", None, None),
            Task("3", "Todo one", "todo", None, None),
            Task("4", "Dropped one", "dropped", None, None),
        )
    )
    assert "✔ 1" in block
    assert "▶ 2" in block
    assert "✗ 4" in block
    # A todo task carries no glyph, so its number sits in blank columns.
    assert "\n    3  Todo one" in block


def test_render_puts_the_note_under_its_task():
    block = render(_status(Task("4", "Estimator", "doing", "tests written", None)))
    assert "▶ 4  Estimator" in block
    assert "\n        tests written" in block


def test_render_names_the_next_task():
    block = render(
        _status(
            Task("1", "Done one", "done", None, None),
            Task("2", "Doing one", "doing", "half way", None),
            Task("3", "Todo one", "todo", None, None),
        )
    )
    assert "next     Task 2 — half way" in block


def test_render_next_falls_back_to_the_first_todo_when_nothing_is_in_progress():
    block = render(
        _status(
            Task("1", "Done one", "done", None, None),
            Task("2", "Todo one", "todo", None, None),
        )
    )
    assert "next     Task 2 — Todo one" in block


def test_render_reports_the_milestone_complete_when_no_task_remains():
    block = render(_status(Task("1", "Done one", "done", None, None)))
    assert "next     milestone complete" in block


def test_render_counts_and_names_the_unplanned_tasks():
    block = render(
        _status(
            Task("1", "Planned", "done", None, None),
            Task("2", "Unplanned", "todo", None, "2026-08-26"),
        )
    )
    assert "added 2026-08-26" in block
    assert "drift    1 task added after the plan was written (2)" in block


def test_render_omits_the_drift_line_when_nothing_was_added():
    block = render(_status(Task("1", "Planned", "done", None, None)))
    assert "drift" not in block


def test_render_truncates_a_title_that_would_overflow_the_width():
    block = render(_status(Task("1", "x" * 200, "todo", None, None)))
    assert all(len(line) <= 62 for line in block.splitlines())
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: `ImportError: cannot import name 'render'`.

- [ ] **Step 3: Write the renderer**

Add `import sys` to the imports at the top of `tools/plan_status.py`, then append:

```python
# Width of the rendering. 62 columns fits an 80-column terminal with room for the
# quoting a chat client adds, and is narrow enough that the block does not rewrap.
_WIDTH = 62
_RULE = "─" * _WIDTH

_GLYPHS = {"done": "✔", "doing": "▶", "todo": " ", "dropped": "✗"}

# Left margin, glyph, space, then the number column. Task numbers are at most three
# characters in every plan written so far ("6a", "10"); wider ones simply push the title.
_NUMBER_WIDTH = 3
# Two margin spaces, the glyph, one space, then the number column.
_TITLE_INDENT = 2 + 1 + 1 + _NUMBER_WIDTH
_NOTE_INDENT = " " * (_TITLE_INDENT + 1)


def render(status: PlanStatus) -> str:
    done = sum(1 for task in status.tasks if task.status in ("done", "dropped"))
    header = f"CADENCE ── {status.milestone}"
    count = f"{done}/{len(status.tasks)} tasks"
    lines = [f"{header}{count.rjust(_WIDTH - len(header))}", _RULE]
    for task in status.tasks:
        lines.extend(_render_task(task))
    lines.append(_RULE)
    lines.append(f"  next     {_next_line(status.tasks)}")
    drift = [task for task in status.tasks if task.added is not None]
    if drift:
        numbers = ", ".join(task.number for task in drift)
        noun = "task" if len(drift) == 1 else "tasks"
        lines.append(
            f"  drift    {len(drift)} {noun} added after the plan was written ({numbers})"
        )
    lines.append(_RULE)
    return "\n".join(lines)


def _render_task(task: Task) -> list[str]:
    glyph = _GLYPHS[task.status]
    suffix = f"added {task.added}" if task.added is not None else ""
    room = _WIDTH - _TITLE_INDENT - (len(suffix) + 1 if suffix else 0)
    title = _clip(task.title, room)
    line = f"  {glyph} {task.number.ljust(_NUMBER_WIDTH)}{title}"
    if suffix:
        line = f"{line.ljust(_WIDTH - len(suffix))}{suffix}"
    lines = [line.rstrip()]
    if task.note is not None:
        lines.append(f"{_NOTE_INDENT}{_clip(task.note, _WIDTH - len(_NOTE_INDENT))}")
    return lines


def _clip(text: str, room: int) -> str:
    plain = text.replace("`", "")
    return plain if len(plain) <= room else plain[: room - 1] + "…"


def _next_line(tasks: tuple[Task, ...]) -> str:
    doing = next((task for task in tasks if task.status == "doing"), None)
    if doing is not None:
        return f"Task {doing.number} — {doing.note or doing.title}"
    todo = next((task for task in tasks if task.status == "todo"), None)
    if todo is not None:
        return f"Task {todo.number} — {todo.title}"
    return "milestone complete"


def main() -> int:
    try:
        print(render(load(Path(__file__).resolve().parent.parent)))
    except (ValueError, FileNotFoundError) as error:
        print(f"plan status unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: 17 passed.

- [ ] **Step 5: Check types and lint**

Run: `uv run mypy && uv run ruff check tools/ tests/test_plan_status.py && uv run ruff format tools/ tests/test_plan_status.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add tools/plan_status.py tests/test_plan_status.py
git commit -m "feat(tools): render the milestone position as a fixed-width block"
```

---

### Task 3: Seed the repository's own status, and gate it

**Files:**
- Modify: `docs/DIRECTION.md:11-16` (section 1 block)
- Modify: `docs/plans/2026-08-24-m1a-canonical-state.md` (ten task headings: lines 53, 331, 539, 989, 1497, 1866, 2163, 2323, 2833, 3117)
- Test: `tests/test_plan_status.py`

**Interfaces:**
- Consumes: `load`, `STATUSES` from Task 1.
- Produces: nothing importable. The repository's files become parseable, and the suite starts failing when they stop being.

- [ ] **Step 1: Write the failing repository tests**

Append to `tests/test_plan_status.py`:

```python
from tools.plan_status import load

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_the_repository_status_parses():
    status = load(REPO_ROOT)
    assert status.tasks, "the current plan declares no tasks"


def test_at_most_one_task_is_in_progress():
    doing = [task for task in load(REPO_ROOT).tasks if task.status == "doing"]
    assert len(doing) <= 1, f"more than one task is marked doing: {[t.number for t in doing]}"


def test_a_finished_milestone_is_not_still_marked_current():
    status = load(REPO_ROOT)
    remaining = [task for task in status.tasks if task.status in ("todo", "doing")]
    ladder = (REPO_ROOT / "docs" / "DIRECTION.md").read_text(encoding="utf-8")
    if not remaining:
        assert "| current |" not in ladder, (
            "every task in the current plan is finished, but section 2 still marks a "
            "milestone current. Move the pointer before the next task starts."
        )


def test_the_repository_status_renders():
    block = render(load(REPO_ROOT))
    assert "CADENCE ──" in block
    assert all(len(line) <= 62 for line in block.splitlines())
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: `ValueError: docs/DIRECTION.md section 1 names a 'Current milestone' but no 'Current plan'.`

- [ ] **Step 3: Add the plan pointer to DIRECTION section 1**

In `docs/DIRECTION.md`, the section 1 block becomes:

```
Pre-implementation research        complete
Project direction and conventions  decided  (PD-D01 .. PD-D07)
Implementation                     M1a complete, M1b not started
Current milestone                  M1 — Canonical State + Metrics
Current plan                       docs/plans/2026-08-24-m1a-canonical-state.md
```

- [ ] **Step 4: Add a status line under each M1a task heading**

Insert one line directly below each `### Task` heading in
`docs/plans/2026-08-24-m1a-canonical-state.md`, separated from the heading by nothing and
from the prose by a blank line. M1a is complete, so every one is `done`:

```markdown
### Task 1: Fix `_approach_pairs` and generate `s0_turning/v1`
`status: done`
```

Do this for tasks 1, 2, 3, 4, 5, 6, 6a, 7, 8, 9. Do not touch the 76 step checkboxes — they
stay unticked as the record of what the old mechanism produced (spec §8).

- [ ] **Step 5: Run the tests and watch them pass**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: 21 passed.

- [ ] **Step 6: Look at the rendering**

Run: `uv run python tools/plan_status.py`
Expected: ten `✔` rows, `10/10 tasks`, `next     milestone complete`, no drift line.

Note that `test_a_finished_milestone_is_not_still_marked_current` will now fail, because
M1a's tasks are all done while section 2 still marks M1 `current`. That is the check working:
M1 is not finished, M1a is. Resolve it by pointing section 1 at an M1b plan — which does not
exist yet — so for this task, mark the test `xfail` with the reason spelled out:

```python
@pytest.mark.xfail(
    reason="M1a's tasks are all done and M1b has no plan file yet; the pointer moves when it does",
    strict=True,
)
def test_a_finished_milestone_is_not_still_marked_current():
```

- [ ] **Step 7: Commit**

```bash
git add docs/DIRECTION.md docs/plans/2026-08-24-m1a-canonical-state.md tests/test_plan_status.py
git commit -m "feat(docs): give M1a task status lines and point DIRECTION at its plan"
```

---

### Task 4: Wire it into the session and the toolchain

**Files:**
- Modify: `Makefile:1` (the `.PHONY` line) and append a `status` target
- Modify: `.claude/settings.json` (add a `SessionStart` hook beside the existing `PreToolUse` one)
- Modify: `CLAUDE.md` (a new section 14)
- Test: `tests/test_plan_status.py`

**Interfaces:**
- Consumes: `tools/plan_status.py` as a script.
- Produces: `make status`, and a rendering printed at session start.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan_status.py`:

```python
import json

def test_make_exposes_a_status_target():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\nstatus:\n" in makefile
    assert "tools/plan_status.py" in makefile


def test_the_session_start_hook_is_registered():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entry in settings["hooks"]["SessionStart"]
        for hook in entry["hooks"]
    ]
    assert any("plan_status.py" in command for command in commands)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: 2 failed — `assert '\nstatus:\n' in makefile` and `KeyError: 'SessionStart'`.

- [ ] **Step 3: Add the Makefile target**

`Makefile` line 1 becomes:

```make
.PHONY: check lint format type test docs-check install status
```

and append:

```make
status:
	uv run python tools/plan_status.py
```

- [ ] **Step 4: Register the SessionStart hook**

`.claude/settings.json` becomes:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|MultiEdit|NotebookEdit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/tools/protect_research_hook.py"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && uv run python tools/plan_status.py || true"
          }
        ]
      }
    ]
  }
}
```

The `|| true` is deliberate: a plan file mid-edit must never stop a session from opening.

- [ ] **Step 5: Add the repository rule**

Append to `CLAUDE.md` a section 14:

```markdown
# 14. Where the Work Stands

The current milestone's position lives in the plan file `docs/DIRECTION.md` §1 names, one
status line under each `### Task` heading:

`status: todo | doing | done | dropped` `added: YYYY-MM-DD` — optional note

`make status` renders it. A `SessionStart` hook renders it at the top of every session, so
a new chat opens knowing where the work stands.

**The maintainer never writes these lines.** Change the status when a task starts and when
it ends, and print the rendering both times — a stale marker has to be wrong in front of
someone within one task, because no test can catch it.

**Work that was not planned becomes a task before it becomes a commit.** Append it to the
current plan with an `added:` date and the reason it was not foreseen. This is the only
place it can be recorded, so the work gets placed against the plan while it is still being
decided rather than after it is done. The count of `added:` tasks is the drift line in the
rendering.

`tests/test_plan_status.py` enforces what a test can: the pointer resolves, every task
heading has a well-formed status line, at most one task is `doing`, and a plan with nothing
left to do does not sit under a milestone still marked `current`.
```

- [ ] **Step 6: Run the tests and watch them pass**

Run: `uv run pytest tests/test_plan_status.py -q`
Expected: 23 passed (one xfailed).

- [ ] **Step 7: Run the whole gate**

Run: `make check`
Expected: clean. Paste the real output (`CLAUDE.md` §9).

- [ ] **Step 8: Commit**

```bash
git add Makefile .claude/settings.json CLAUDE.md tests/test_plan_status.py
git commit -m "feat: print where the work stands at session start, and write the rule down"
```

---

## Self-Review

**Spec coverage.** §3 status lines → Task 1 parser, Task 3 seeding. §3 unplanned-as-task →
Task 4 step 5 rule, Task 2 drift line. §4 pointer → Task 1 `parse_direction`, Task 3 step 3.
§4 milestone may not open without a plan → Task 1 `test_parse_direction_rejects_a_missing_plan_pointer`.
§5 renderer and `make status` → Task 2, Task 4 step 3. §6 checks 1-4 → Task 3 step 1; check 5
(`added:` on appended tasks) has **no test** — it cannot be checked without knowing the
original plan's highest task number, which nothing records. Dropped deliberately; the drift
line makes an unmarked appended task visible instead. §7 display → Task 4.

**Placeholders.** None. Every code step carries the code.

**Column arithmetic.** `_TITLE_INDENT` is 7 (`  ` + glyph + ` ` + a three-column number),
so a `todo` task renders as four spaces, its number, two spaces, its title — which is what
`test_render_marks_each_status_with_its_own_glyph` asserts. Notes indent one further, to 8.

**Type consistency.** `Task(number, title, status, note, added)` positional order is the
same in the dataclass, in `_parse_task`, and in all Task 2 tests. `render` takes `PlanStatus`
everywhere. `load` returns `PlanStatus` everywhere.
