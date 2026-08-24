#!/usr/bin/env python3
"""PreToolUse guard: Claude may not write research output.

GOTCHA: a hook that raises exits non-zero without a decision, and Claude Code treats that
as a non-blocking error - the write proceeds. Every failure path here must therefore end
in an explicit deny, including a missing environment variable or a malformed payload.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_FILES = ("INDEX.md", "decisions.yaml")


def is_inside(target: Path, root: Path) -> bool:
    if target.is_relative_to(root):
        return True
    if not root.exists():
        # No research tree in this checkout, so nothing can be inside one. Without this,
        # samefile() below raises FileNotFoundError on the ROOT side for every ancestor and
        # the blanket deny then refuses every write in the project.
        return False
    # GOTCHA: on a case-insensitive filesystem, resolve() does not canonicalise
    # directory case, so research/ reached as RESEARCH/ compares as a different tree
    # while naming the same inode. Identity on the nearest existing ancestor is the
    # only reliable test.
    # GOTCHA: Path.exists() re-raises OSError for EACCES - Python swallows only ENOENT,
    # ENOTDIR, EBADF and ELOOP. That escapes to main's boundary and denies, on purpose:
    # answering "not inside" when the filesystem refused to say would allow the write.
    for ancestor in (target, *target.parents):
        if ancestor.exists() and ancestor.samefile(root):
            return True
    return False


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def main() -> int:
    try:
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or DEFAULT_ROOT).resolve()
        research_root = root / "research"
        allowed = {research_root / name for name in GOVERNANCE_FILES}
        payload = json.load(sys.stdin)
        tool_input = payload["tool_input"]
        # NotebookEdit names its target notebook_path, every other writing tool file_path.
        # Matching a tool without knowing its payload shape denies every call it makes.
        raw = Path(tool_input.get("file_path") or tool_input["notebook_path"])
        target = (raw if raw.is_absolute() else root / raw).resolve()
        inside = is_inside(target, research_root)
    except Exception as error:
        deny(f"research write guard could not evaluate this call: {error!r}")
        return 0
    if inside and target not in allowed:
        deny(
            "Claude may edit only research/INDEX.md and research/decisions.yaml. "
            "Delegate research output to the Research Agent."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
