"""Documentation consistency checker — PD-D06 layers 1 and 3.

Validates that every decision identifier resolves to its source document, that no code
depends on a superseded or retracted decision, and that no code cites an identifier the
registry does not know. Layer 2 (section content hashing) arrives at M1.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Identifier grammar shared by the research corpus: PREFIX-Dnn, PREFIX-Hnn, PREFIX-Qnn,
# and the bare-numeric AP-nn family (e.g. AP-06) used by the architecture principles.
ID_PATTERN = re.compile(r"\b([A-Z]{2,4}-(?:[DHQ]\d{2}|\d{2}))\b")

DEPENDABLE_STATUSES = frozenset({"adopted", "hypothesis", "deferred"})
# tests/ is deliberately excluded: the checker's own tests contain fabricated ids.
SCANNED_PATHS = (("src", "*.py"), ("tools", "*.py"), ("docs", "*.md"))


@dataclass(frozen=True)
class Decision:
    id: str
    statement: str
    source: str
    status: str
    superseded_by: str | None = None


def load_registry(path: Path) -> dict[str, Decision]:
    raw = yaml.safe_load(path.read_text()) or {}
    return {
        key: Decision(
            id=key,
            statement=value["statement"],
            source=value["source"],
            superseded_by=value.get("superseded_by"),
            status=value["status"],
        )
        for key, value in raw.items()
    }


def _resolve_source(registry_path: Path, source: str) -> Path:
    return (registry_path.parent / source).resolve()


def check(repo_root: Path) -> list[str]:
    registry_path = repo_root / "research" / "decisions.yaml"
    registry = load_registry(registry_path)
    problems: list[str] = []

    for decision in registry.values():
        source_path = _resolve_source(registry_path, decision.source)
        if not source_path.is_file():
            problems.append(f"{decision.id}: source file missing — {decision.source}")
            continue
        if decision.id not in source_path.read_text():
            problems.append(f"{decision.id}: not found in source — {decision.source}")
        if decision.superseded_by and decision.superseded_by not in registry:
            problems.append(
                f"{decision.id}: superseded_by names {decision.superseded_by}, "
                "which is not in the registry"
            )

    # CLAUDE.md section 6 mandates superseding rather than editing: issue a new id, mark the
    # old one superseded, point it at the replacement. The document recording that
    # replacement has to name what it replaces, so the successor's source is the one place a
    # superseded id may still be cited.
    supersede_records: dict[str, set[str]] = {}
    for decision in registry.values():
        successor = registry.get(decision.superseded_by or "")
        if successor is None:
            continue
        record = _resolve_source(registry_path, successor.source).resolve()
        supersede_records.setdefault(str(record), set()).add(decision.id)

    for directory, pattern in SCANNED_PATHS:
        root = repo_root / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(pattern)):
            if directory == "docs" and "plans" in path.relative_to(root).parts:
                continue  # Historical plans contain fabricated IDs in test examples.
            text = path.read_text()
            paragraphs = re.split(r"\n\s*\n", text)
            for cited in sorted(set(ID_PATTERN.findall(text))):
                location = path.relative_to(repo_root)
                if cited not in registry:
                    problems.append(f"{location}: cites {cited}, which is not in the registry")
                    continue
                if registry[cited].status in DEPENDABLE_STATUSES:
                    continue
                if cited in supersede_records.get(str(path.resolve()), set()):
                    continue
                # A reader who meets a superseded id must be able to reach its replacement
                # without leaving the paragraph. Naming both together is a citation of
                # history rather than a dependency on it, and it is the only way a document
                # can point forward to a decision issued after it was written.
                # Paragraph, not file: DIRECTION.md names nearly every live id, so a
                # whole-file test would silence this check there permanently.
                successor_id = registry[cited].superseded_by
                if successor_id and any(
                    cited in block and successor_id in block for block in paragraphs
                ):
                    continue
                problems.append(
                    f"{location}: depends on {cited}, which is {registry[cited].status}"
                )

    return problems


def main() -> int:
    problems = check(Path(__file__).resolve().parents[1])
    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} documentation consistency problem(s).")
        return 1
    print("Documentation consistency: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
