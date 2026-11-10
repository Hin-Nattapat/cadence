import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import work_status
from work_status import Milestone, Ticket, current_milestone, main, render

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_milestone_picks_the_lowest_phase_with_open_tickets():
    milestones = [Milestone("P3 B", 0, 0), Milestone("P2 A", 4, 2), Milestone("P10 C", 1, 0)]
    assert current_milestone(milestones) == Milestone("P2 A", 4, 2)


def test_current_milestone_compares_phase_numbers_numerically():
    milestones = [Milestone("P10 C", 1, 0), Milestone("P9 B", 1, 0)]
    assert current_milestone(milestones) == Milestone("P9 B", 1, 0)


def test_current_milestone_falls_back_to_the_lowest_phase_when_none_has_open_tickets():
    milestones = [Milestone("P4 D", 0, 3), Milestone("P3 C", 0, 5)]
    assert current_milestone(milestones) == Milestone("P3 C", 0, 5)


def test_current_milestone_ignores_titles_without_a_phase():
    assert current_milestone([Milestone("Backlog", 3, 0)]) is None


def test_render_lists_open_tickets_by_number():
    text = render(Milestone("P2 Signal", 2, 1), [Ticket(15, "[P2-02] B"), Ticket(14, "[P2-01] A")])
    assert text == "P2 Signal · 1/3 tickets closed\n  #14 [P2-01] A\n  #15 [P2-02] B"


def _raising(error):
    def run(*args, **kwargs):
        raise error

    return run


def _returning(stdout):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return run


def test_main_is_silent_when_gh_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(work_status.subprocess, "run", _raising(FileNotFoundError("gh")))
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_gh_is_not_executable(monkeypatch, capsys):
    monkeypatch.setattr(work_status.subprocess, "run", _raising(PermissionError("gh")))
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_gh_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        work_status.subprocess, "run", _raising(subprocess.CalledProcessError(1, "gh"))
    )
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_gh_times_out(monkeypatch, capsys):
    monkeypatch.setattr(
        work_status.subprocess, "run", _raising(subprocess.TimeoutExpired("gh", 5.0))
    )
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_gh_returns_bad_json(monkeypatch, capsys):
    monkeypatch.setattr(work_status.subprocess, "run", _returning("not json"))
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_the_session_start_hook_runs_work_status():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"] for entry in settings["hooks"]["SessionStart"] for hook in entry["hooks"]
    ]
    assert any("tools/work_status.py" in command for command in commands)


def _returning_in_turn(*outcomes):
    queue = list(outcomes)

    def run(*args, **kwargs):
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(args, 0, stdout=outcome, stderr="")

    return run


_P2_MILESTONES = json.dumps([{"title": "P2 Signal", "open_issues": 2, "closed_issues": 1}])


def test_main_prints_the_current_phase_and_its_open_tickets(monkeypatch, capsys):
    tickets = json.dumps(
        [{"number": 15, "title": "[P2-02] B"}, {"number": 14, "title": "[P2-01] A"}]
    )
    monkeypatch.setattr(work_status.subprocess, "run", _returning_in_turn(_P2_MILESTONES, tickets))
    assert main() == 0
    assert (
        capsys.readouterr().out
        == "P2 Signal · 1/3 tickets closed\n  #14 [P2-01] A\n  #15 [P2-02] B\n"
    )


def test_main_is_silent_when_no_milestone_names_a_phase(monkeypatch, capsys):
    backlog = json.dumps([{"title": "Backlog", "open_issues": 3, "closed_issues": 0}])
    monkeypatch.setattr(work_status.subprocess, "run", _returning_in_turn(backlog))
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_the_ticket_query_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        work_status.subprocess,
        "run",
        _returning_in_turn(_P2_MILESTONES, subprocess.CalledProcessError(1, "gh")),
    )
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_a_count_is_null(monkeypatch, capsys):
    milestones = json.dumps([{"title": "P2 Signal", "open_issues": 2, "closed_issues": None}])
    monkeypatch.setattr(work_status.subprocess, "run", _returning_in_turn(milestones, "[]"))
    assert main() == 0
    assert capsys.readouterr().out == ""


def test_main_is_silent_when_a_ticket_number_is_null(monkeypatch, capsys):
    tickets = json.dumps([{"number": None, "title": "A"}, {"number": 14, "title": "B"}])
    monkeypatch.setattr(work_status.subprocess, "run", _returning_in_turn(_P2_MILESTONES, tickets))
    assert main() == 0
    assert capsys.readouterr().out == ""
