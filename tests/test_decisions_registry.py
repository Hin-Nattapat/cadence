import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from check_decisions import check, load_registry

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_registry_loads_every_entry():
    registry = load_registry(REPO_ROOT / "research" / "decisions.yaml")
    assert len(registry) >= 83  # 83 at M0 (77 research decisions + AP-01..AP-06)
    assert registry["ARCH-D02"].status == "adopted"
    assert "TraCI" in registry["ARCH-D02"].statement


def test_repository_passes_its_own_check():
    assert check(REPO_ROOT) == []


def test_check_reports_an_id_missing_from_its_source(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D01:\n  statement: "A statement."\n  source:    ghost.md\n  status:    adopted\n'
    )
    (tmp_path / "research" / "ghost.md").write_text("This file never mentions the id.\n")
    problems = check(tmp_path)
    assert any("XX-D01" in p and "not found in source" in p for p in problems)


def test_check_reports_a_missing_source_file(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        "XX-D02:\n"
        '  statement: "A statement."\n'
        "  source:    does_not_exist.md\n"
        "  status:    adopted\n"
    )
    problems = check(tmp_path)
    assert any("XX-D02" in p and "source file missing" in p for p in problems)


def test_check_reports_code_depending_on_a_superseded_decision(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D03:\n  statement: "An old statement."\n  source:    old.md\n  status:    superseded\n'
    )
    (tmp_path / "research" / "old.md").write_text("XX-D03 lives here.\n")
    (tmp_path / "src" / "thing.py").write_text("# implements XX-D03\nx = 1\n")
    problems = check(tmp_path)
    assert any("XX-D03" in p and "superseded" in p for p in problems)


def test_check_reports_a_code_reference_to_an_unknown_id(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D04:\n  statement: "A statement."\n  source:    real.md\n  status:    adopted\n'
    )
    (tmp_path / "research" / "real.md").write_text("XX-D04 lives here.\n")
    (tmp_path / "src" / "thing.py").write_text("# see XX-D99\ny = 2\n")
    problems = check(tmp_path)
    assert any("XX-D99" in p and "not in the registry" in p for p in problems)


def test_check_reports_a_document_reference_to_an_unknown_id(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "research" / "decisions.yaml").write_text(
        'XX-D04:\n  statement: "A statement."\n  source:    real.md\n  status:    adopted\n'
    )
    (tmp_path / "research" / "real.md").write_text("XX-D04 lives here.\n")
    (tmp_path / "docs" / "direction.md").write_text("Deferred under XX-Q99.\n")
    problems = check(tmp_path)
    assert any("XX-Q99" in p and "not in the registry" in p for p in problems)


def _registry(tmp_path, body: str) -> None:
    (tmp_path / "research").mkdir(exist_ok=True)
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "research" / "decisions.yaml").write_text(body)


def test_the_successor_source_may_cite_the_decision_it_supersedes(tmp_path):
    _registry(
        tmp_path,
        'XX-D01:\n  statement: "Old."\n  source:    old.md\n  status:    superseded\n'
        "  superseded_by: XX-D02\n"
        'XX-D02:\n  statement: "New."\n  source:    ../docs/successor.md\n  status:    adopted\n',
    )
    (tmp_path / "research" / "old.md").write_text("XX-D01 lives here.\n")
    (tmp_path / "docs" / "successor.md").write_text("XX-D02 supersedes XX-D01.\n")

    assert check(tmp_path) == []


def test_any_other_document_may_not_cite_a_superseded_decision(tmp_path):
    _registry(
        tmp_path,
        'XX-D01:\n  statement: "Old."\n  source:    old.md\n  status:    superseded\n'
        "  superseded_by: XX-D02\n"
        'XX-D02:\n  statement: "New."\n  source:    ../docs/successor.md\n  status:    adopted\n',
    )
    (tmp_path / "research" / "old.md").write_text("XX-D01 lives here.\n")
    (tmp_path / "docs" / "successor.md").write_text("XX-D02 supersedes XX-D01.\n")
    (tmp_path / "docs" / "elsewhere.md").write_text("We still rely on XX-D01.\n")

    problems = check(tmp_path)
    assert any("elsewhere.md" in p and "XX-D01" in p and "superseded" in p for p in problems)


def test_superseded_by_must_name_a_registered_decision(tmp_path):
    _registry(
        tmp_path,
        'XX-D01:\n  statement: "Old."\n  source:    old.md\n  status:    superseded\n'
        "  superseded_by: XX-D99\n",
    )
    (tmp_path / "research" / "old.md").write_text("XX-D01 lives here.\n")

    problems = check(tmp_path)
    assert any("XX-D99" in p and "not in the registry" in p for p in problems)
