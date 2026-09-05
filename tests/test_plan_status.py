import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from plan_status import (
    _WIDTH,
    PlanStatus,
    Task,
    _clip,
    load,
    parse_direction,
    parse_plan,
    render,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

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


def test_parse_direction_rejects_a_missing_milestone_pointer():
    text = DIRECTION_FIXTURE.replace(
        "Current milestone                  M1 — Canonical State + Metrics\n",
        "",
    )
    with pytest.raises(ValueError, match="Current milestone"):
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


def test_parse_plan_rejects_a_heading_with_no_colon():
    text = PLAN_FIXTURE.replace("### Task 7: Run artifacts", "### Task 7 Run artifacts")
    with pytest.raises(ValueError, match="Task 7 Run artifacts"):
        parse_plan(text)


def test_parse_plan_rejects_a_heading_with_an_empty_title():
    text = PLAN_FIXTURE.replace("### Task 7: Run artifacts", "### Task 7: ")
    with pytest.raises(ValueError, match="Task 7"):
        parse_plan(text)


def test_parse_plan_rejects_added_placed_after_the_note():
    text = PLAN_FIXTURE.replace(
        "`status: todo` `added: 2026-08-26` — found while doing Task 6a",
        "`status: todo` — found while doing Task 6a `added: 2026-08-26`",
    )
    with pytest.raises(ValueError, match="Task 10"):
        parse_plan(text)


def test_parse_plan_ignores_a_task_heading_inside_a_fenced_code_block():
    text = PLAN_FIXTURE + (
        "\n```markdown\n### Task 99: An example heading, not a real task\n`status: done`\n```\n"
    )
    tasks = parse_plan(text)
    assert [t.number for t in tasks] == ["1", "6a", "7", "10"]


def test_parse_plan_handles_an_unterminated_fence_without_crashing():
    text = PLAN_FIXTURE + "\n```markdown\n### Task 99: never closed\n`status: done`\n"
    tasks = parse_plan(text)
    assert [t.number for t in tasks] == ["1", "6a", "7", "10"]


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
    with pytest.raises(FileNotFoundError, match=r"2026-08-24-m1a-canonical-state\.md"):
        load(tmp_path)


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
    assert "next     milestone complete — move the pointer, DIRECTION.md" in block
    assert all(len(line) <= _WIDTH for line in block.splitlines())


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
    assert all(len(line) <= _WIDTH for line in block.splitlines())


def test_render_keeps_the_header_within_width_for_a_long_milestone_name():
    long_milestone = "M9 — Network-Aware Reinforcement Learning versus Max-Pressure Control"
    status = PlanStatus(
        milestone=long_milestone,
        plan_path=Path("docs/plans/x.md"),
        tasks=(Task("1", "Done one", "done", None, None),),
    )
    block = render(status)
    header_line = block.splitlines()[0]
    assert len(header_line) <= _WIDTH
    assert "1/1 tasks" in header_line


def test_render_keeps_a_four_character_task_number_within_width():
    block = render(
        _status(
            Task("10a1", "x" * 100, "todo", None, None),
            Task("10a2", "y" * 100, "todo", None, "2026-08-26"),
        )
    )
    assert all(len(line) <= _WIDTH for line in block.splitlines())
    assert "added 2026-08-26" in block


def test_clip_returns_the_empty_string_when_there_is_no_room():
    assert _clip("anything", 0) == ""
    assert _clip("anything", -1) == ""


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
    assert all(len(line) <= _WIDTH for line in block.splitlines())


def test_make_exposes_a_status_target():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\nstatus:\n" in makefile
    assert "tools/plan_status.py" in makefile


def test_the_session_start_hook_is_registered():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"] for entry in settings["hooks"]["SessionStart"] for hook in entry["hooks"]
    ]
    assert any("plan_status.py" in command for command in commands)
