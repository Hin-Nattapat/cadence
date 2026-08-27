"""Where the current milestone stands, read from the plan file that holds it.

Parses `docs/DIRECTION.md` section 1 for the current milestone and the plan file it names,
then that plan file for one status line per `### Task` heading. The rendering this feeds is
the interface; the plan file is the state. Nothing here imports cadence, SUMO, or a plan
produced by any particular tool — a hand-written list of task headings parses identically.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

STATUSES = ("todo", "doing", "done", "dropped")

TASK_HEADING_RE = re.compile(r"^### Task (?P<number>\S+): (?P<title>.+?)\s*$", re.MULTILINE)

# Any line that opens a `### Task` heading but that TASK_HEADING_RE does not also match is
# malformed (missing colon, empty title) rather than a task that silently does not exist.
_TASK_HEADING_START_RE = re.compile(r"^### Task\b.*$", re.MULTILINE)

# A task's status line is the first non-blank line under its heading. `added` is present
# only on tasks appended after the plan was written, which is what makes drift countable.
STATUS_LINE_RE = re.compile(
    r"^`status: (?P<status>\w+)`"
    r"(?: `added: (?P<added>\d{4}-\d{2}-\d{2})`)?"
    r"(?: — (?P<note>.+?))?\s*$"
)

_DIRECTION_MILESTONE_RE = re.compile(r"^Current milestone\s+(?P<value>.+?)\s*$", re.MULTILINE)
_DIRECTION_PLAN_RE = re.compile(r"^Current plan\s+(?P<value>.+?)\s*$", re.MULTILINE)

# A fence is three or more backticks or tildes, optionally followed by an info string
# (```markdown). Only the run of fence characters is captured; the info string is ignored.
_FENCE_RE = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")


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


def _strip_fenced_code_blocks(text: str) -> str:
    # A plan file that documents its own format can contain a fenced example of a
    # `### Task` heading. Scanning it verbatim would parse the example as a real task, so
    # fenced regions are dropped before the heading and status-line scan ever sees them.
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    fence: str | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if fence is None:
            if match is not None:
                fence = match.group("fence")
                continue
            kept.append(line)
            continue
        closes = (
            match is not None
            and match.group("fence")[0] == fence[0]
            and len(match.group("fence")) >= len(fence)
        )
        if closes:
            fence = None
        # An unterminated fence consumes the rest of the file rather than raising: a plan
        # file is prose the maintainer edits by hand, not a linted Markdown document.
    return "".join(kept)


def parse_plan(text: str) -> tuple[Task, ...]:
    scanned = _strip_fenced_code_blocks(text)
    _reject_malformed_task_headings(scanned)
    headings = list(TASK_HEADING_RE.finditer(scanned))
    tasks: list[Task] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(scanned)
        body = scanned[heading.end() : end]
        tasks.append(_parse_task(heading.group("number"), heading.group("title"), body))
    return tuple(tasks)


def _reject_malformed_task_headings(text: str) -> None:
    for start in _TASK_HEADING_START_RE.finditer(text):
        line = start.group(0)
        if TASK_HEADING_RE.match(line) is None:
            raise ValueError(
                f"Malformed task heading {line!r}. Expected '### Task <number>: <title>', "
                "with a colon and a non-empty title."
            )


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
    note = match.group("note")
    if note is not None and "added:" in note:
        raise ValueError(
            f"Task {number}'s status line has `added:` after the note, so it parsed as text "
            "instead of the drift date. Field order is fixed: `status: ...` `added: "
            "YYYY-MM-DD` — note."
        )
    return Task(
        number=number,
        title=title,
        status=status,
        note=note,
        added=match.group("added"),
    )


def load(repo_root: Path) -> PlanStatus:
    direction = repo_root / "docs" / "DIRECTION.md"
    milestone, plan_relative = parse_direction(direction.read_text(encoding="utf-8"))
    plan_path = repo_root / plan_relative
    if not plan_path.is_file():
        raise FileNotFoundError(f"docs/DIRECTION.md names {plan_relative}, which does not exist.")
    return PlanStatus(
        milestone=milestone,
        plan_path=plan_path,
        tasks=parse_plan(plan_path.read_text(encoding="utf-8")),
    )


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

_NEXT_PREFIX = "  next     "
_DRIFT_PREFIX = "  drift    "

_MILESTONE_COMPLETE = "milestone complete — move the pointer, DIRECTION.md"


def render(status: PlanStatus) -> str:
    done = sum(1 for task in status.tasks if task.status in ("done", "dropped"))
    header = f"CADENCE ── {status.milestone}"
    count = f"{done}/{len(status.tasks)} tasks"
    # A milestone name long enough to collide with the count would make `rjust` a no-op and
    # glue the two together; clip the header first so the count always keeps its column,
    # leaving one blank column between them.
    header = _clip(header, max(_WIDTH - len(count) - 1, 0))
    lines = [f"{header}{count.rjust(_WIDTH - len(header))}", _RULE]
    for task in status.tasks:
        lines.extend(_render_task(task))
    lines.append(_RULE)
    lines.append(f"{_NEXT_PREFIX}{_next_line(status.tasks)}")
    drift = [task for task in status.tasks if task.added is not None]
    if drift:
        numbers = ", ".join(task.number for task in drift)
        noun = "task" if len(drift) == 1 else "tasks"
        lines.append(
            f"{_DRIFT_PREFIX}{len(drift)} {noun} added after the plan was written ({numbers})"
        )
    lines.append(_RULE)
    return "\n".join(lines)


def _render_task(task: Task) -> list[str]:
    glyph = _GLYPHS[task.status]
    # A task number wider than the reserved column would otherwise push the title and any
    # `added` suffix past it; grow the column to fit the number instead.
    number_width = max(_NUMBER_WIDTH, len(task.number))
    title_indent = _TITLE_INDENT + (number_width - _NUMBER_WIDTH)
    suffix = f"added {task.added}" if task.added is not None else ""
    room = _WIDTH - title_indent - (len(suffix) + 1 if suffix else 0)
    title = _clip(task.title, room)
    line = f"  {glyph} {task.number.ljust(number_width)}{title}"
    if suffix:
        line = f"{line.ljust(_WIDTH - len(suffix))}{suffix}"
    lines = [line.rstrip()]
    if task.note is not None:
        note_indent = " " * (title_indent + 1)
        lines.append(f"{note_indent}{_clip(task.note, _WIDTH - len(note_indent))}")
    return lines


def _clip(text: str, room: int) -> str:
    plain = text.replace("`", "")
    if room <= 0:
        return ""
    return plain if len(plain) <= room else plain[: room - 1] + "…"


def _next_line(tasks: tuple[Task, ...]) -> str:
    available = _WIDTH - len(_NEXT_PREFIX)
    doing = next((task for task in tasks if task.status == "doing"), None)
    if doing is not None:
        prefix = f"Task {doing.number} — "
        note_or_title = doing.note or doing.title
        clipped = _clip(note_or_title, available - len(prefix))
        return f"{prefix}{clipped}"
    todo = next((task for task in tasks if task.status == "todo"), None)
    if todo is not None:
        prefix = f"Task {todo.number} — "
        clipped = _clip(todo.title, available - len(prefix))
        return f"{prefix}{clipped}"
    return _clip(_MILESTONE_COMPLETE, available)


def main() -> int:
    try:
        print(render(load(Path(__file__).resolve().parent.parent)))
    except (ValueError, FileNotFoundError) as error:
        print(f"plan status unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
