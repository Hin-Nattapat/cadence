import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tools import protect_research_hook

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "tools/protect_research_hook.py"


def run_hook(payload: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"CLAUDE_PROJECT_DIR": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        text=True,
        capture_output=True,
        env=environment,
    )


def write_payload(path: Path) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})


def notebook_payload(path: Path) -> str:
    return json.dumps({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(path)}})


def decision(result: subprocess.CompletedProcess[str]) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_hook_denies_claude_write_to_research_output():
    result = run_hook(write_payload(REPO_ROOT / "research/addenda/new.md"))
    assert decision(result) == "deny"


def test_hook_denies_corpus_rewrites():
    corpus = REPO_ROOT / "research/CADENCE_MAX_PRESSURE_RESEARCH.md"
    assert decision(run_hook(write_payload(corpus))) == "deny"


def test_hook_allows_registry_and_index_updates():
    assert run_hook(write_payload(REPO_ROOT / "research/decisions.yaml")).stdout == ""
    assert run_hook(write_payload(REPO_ROOT / "research/INDEX.md")).stdout == ""


def test_hook_ignores_paths_outside_research():
    assert run_hook(write_payload(REPO_ROOT / "src/cadence/types.py")).stdout == ""


def test_hook_fails_closed_on_an_unusable_payload():
    assert decision(run_hook("not json")) == "deny"
    assert decision(run_hook(json.dumps({"tool_input": {}}))) == "deny"


def test_hook_denies_a_directory_case_variant_of_research():
    # Same inode as research/ on a case-insensitive filesystem, different string.
    corpus = REPO_ROOT / "RESEARCH/CADENCE_MAX_PRESSURE_RESEARCH.md"
    assert decision(run_hook(write_payload(corpus))) == "deny"


def test_hook_denies_a_mixed_case_directory_variant():
    corpus = REPO_ROOT / "ReSeArCh/CADENCE_MAX_PRESSURE_RESEARCH.md"
    assert decision(run_hook(write_payload(corpus))) == "deny"


def test_hook_denies_a_relative_research_path():
    relative = Path("research/CADENCE_MAX_PRESSURE_RESEARCH.md")
    assert decision(run_hook(write_payload(relative))) == "deny"


def test_hook_allows_a_relative_path_outside_research():
    assert run_hook(write_payload(Path("src/cadence/types.py"))).stdout == ""


def test_hook_allows_a_traversal_that_leaves_research():
    outside = REPO_ROOT / "research/../src/cadence/types.py"
    assert run_hook(write_payload(outside)).stdout == ""


def _filesystem_is_case_insensitive(directory: Path) -> bool:
    probe = directory / "case_probe"
    probe.write_text("x")
    return (directory / "CASE_PROBE").exists()


def test_hook_denies_when_an_ancestor_cannot_be_stat_ed(tmp_path):
    # Built under a throwaway project root, not the real research/ tree, so a permission
    # probe cannot leave anything behind in the repository even if cleanup is interrupted.
    if os.geteuid() == 0:
        pytest.skip("root ignores permission bits, so this probe cannot fail closed")
    if not _filesystem_is_case_insensitive(tmp_path):
        pytest.skip("the probe needs a case variant to reach the ancestor walk")
    project_root = tmp_path
    blocked = project_root / "research" / "_hook_eacces_probe"
    (blocked / "sub").mkdir(parents=True)
    (blocked / "sub" / "file.md").write_text("probe\n")
    blocked.chmod(0o000)
    try:
        target = project_root / "RESEARCH" / "_hook_eacces_probe" / "sub" / "file.md"
        environment = os.environ | {"CLAUDE_PROJECT_DIR": str(project_root)}
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=write_payload(target),
            text=True,
            capture_output=True,
            env=environment,
        )
        assert result.returncode == 0
        assert decision(result) == "deny"
    finally:
        blocked.chmod(0o755)
        shutil.rmtree(blocked)


def test_hook_allows_a_write_when_the_project_has_no_research_tree(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "thing.py"
    target.write_text("x\n")
    environment = os.environ | {"CLAUDE_PROJECT_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=write_payload(target),
        text=True,
        capture_output=True,
        env=environment,
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_hook_denies_when_containment_cannot_be_determined(monkeypatch, capsys):
    # Filesystem-independent: the EACCES probe only bites on a case-insensitive volume
    # as a non-root user, so the contract needs a test that always runs.
    monkeypatch.setattr(
        protect_research_hook,
        "is_inside",
        lambda target, root: (_ for _ in ()).throw(PermissionError(13, "Permission denied")),
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(REPO_ROOT))
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(write_payload(REPO_ROOT / "src/cadence/types.py"))
    )

    assert protect_research_hook.main() == 0

    decision_made = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert decision_made["permissionDecision"] == "deny"


def test_hook_allows_a_notebook_edit_outside_research():
    notebook = REPO_ROOT / "studies" / "analysis.ipynb"
    assert run_hook(notebook_payload(notebook)).stdout == ""


def test_hook_denies_a_notebook_edit_inside_research():
    notebook = REPO_ROOT / "research" / "notes.ipynb"
    assert decision(run_hook(notebook_payload(notebook))) == "deny"


def test_hook_denies_a_payload_with_neither_path_key():
    assert decision(run_hook(json.dumps({"tool_input": {"other": "x"}}))) == "deny"
