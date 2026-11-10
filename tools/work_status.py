"""The current phase and its open tickets, read live from GitHub.

Status is owned by GitHub milestones and issues; this prints it at session start. Offline,
without `gh`, or on any failure it prints nothing and returns 0: the status is a convenience,
not a gate.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

# Long enough for two GitHub API calls on a normal connection, short enough not to stall
# session start.
GITHUB_TIMEOUT_S = 5.0
# GitHub's maximum page size; a phase holds far fewer tickets, and P2-P9 are eight milestones.
GITHUB_PAGE_LIMIT = 100

_PHASE_TITLE_PATTERN = re.compile(r"^P(\d+) ")


@dataclass(frozen=True, slots=True)
class Milestone:
    title: str
    open_count: int
    closed_count: int


@dataclass(frozen=True, slots=True)
class Ticket:
    number: int
    title: str


def current_milestone(milestones: Sequence[Milestone]) -> Milestone | None:
    phased = sorted(
        (
            (int(match.group(1)), milestone)
            for milestone in milestones
            if (match := _PHASE_TITLE_PATTERN.match(milestone.title))
        ),
        key=lambda pair: pair[0],
    )
    for _, milestone in phased:
        if milestone.open_count > 0:
            return milestone
    return phased[0][1] if phased else None


def render(milestone: Milestone, open_tickets: Sequence[Ticket]) -> str:
    total = milestone.open_count + milestone.closed_count
    lines = [f"{milestone.title} · {milestone.closed_count}/{total} tickets closed"]
    lines.extend(
        f"  #{ticket.number} {ticket.title}"
        for ticket in sorted(open_tickets, key=lambda ticket: ticket.number)
    )
    return "\n".join(lines)


def main() -> int:
    try:
        milestones_json = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/milestones?state=open&per_page={GITHUB_PAGE_LIMIT}",
                "--jq",
                "[.[] | {title, open_issues, closed_issues}]",
            ],
            capture_output=True,
            text=True,
            timeout=GITHUB_TIMEOUT_S,
            check=True,
        ).stdout
        milestones = [
            Milestone(row["title"], row["open_issues"], row["closed_issues"])
            for row in json.loads(milestones_json)
        ]
        milestone = current_milestone(milestones)
        if milestone is None:
            return 0
        tickets_json = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--milestone",
                milestone.title,
                "--state",
                "open",
                "--json",
                "number,title",
                "--limit",
                str(GITHUB_PAGE_LIMIT),
            ],
            capture_output=True,
            text=True,
            timeout=GITHUB_TIMEOUT_S,
            check=True,
        ).stdout
        tickets = [Ticket(row["number"], row["title"]) for row in json.loads(tickets_json)]
        print(render(milestone, tickets))
    except (
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
