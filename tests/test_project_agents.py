import json
import subprocess
from pathlib import Path

import pytest
from tools import project_agents
from tools.project_agents import (
    REPO_ROOT,
    ResearchGuard,
    ResearchGuardError,
    is_allowed_research_output,
    knowledge_command,
    main,
    research_command,
)


def test_knowledge_command_is_read_only_and_cost_bounded(tmp_path: Path):
    command = knowledge_command("Which controller is first?", tmp_path / "answer.json")

    assert command[:2] == ["codex", "exec"]
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--model") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="medium"' in command
    assert "--search" not in command
    assert "--output-schema" in command
    assert "--json" in command
    assert "--ephemeral" in command
    assert command[-1].endswith("User question:\nWhich controller is first?")


def test_knowledge_schema_exposes_decision_support_fields():
    schema = json.loads((REPO_ROOT / "tools/agent_prompts/knowledge.schema.json").read_text())

    required = set(schema["required"])
    assert {"mode", "answer", "touched_decision_ids", "defer_to_user"} <= required
    assert schema["additionalProperties"] is False


def test_empty_question_is_rejected():
    with pytest.raises(SystemExit):
        main(["knowledge", ""])


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("research/addenda/2026-08-23-turn-ratios.md", True),
        ("research/references.bib", True),
        ("research/CHATGPT_KNOWLEDGE_HANDOFF.md", True),
        ("research/INDEX.md", False),
        ("research/decisions.yaml", False),
        ("research/CADENCE_SUMO_SIMULATION_RESEARCH.md", False),
        ("src/cadence/types.py", False),
    ],
)
def test_research_output_allowlist(path: str, allowed: bool):
    assert is_allowed_research_output(Path(path)) is allowed


def test_research_command_uses_search_without_shell_network(tmp_path: Path):
    command = research_command("Find the authoritative definition.", tmp_path / "answer.txt")

    assert command[command.index("--model") + 1] == "gpt-5.6-terra"
    assert 'model_reasoning_effort="high"' in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert command[command.index("--cd") + 1] == str(REPO_ROOT / "research")
    assert "tools.web_search=true" in command
    assert "sandbox_workspace_write.network_access=false" in command


def test_research_command_allows_only_explicit_sol_escalation(tmp_path: Path):
    command = research_command(
        "Resolve conflicting evidence.", tmp_path / "answer.txt", model="gpt-5.6-sol"
    )
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    research = tmp_path / "research"
    research.mkdir()
    (research / "INDEX.md").write_text("index\n")
    (research / "decisions.yaml").write_text("{}\n")
    (research / "CORPUS.md").write_text("immutable\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "research"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    return tmp_path


def test_research_guard_requires_a_clean_research_tree(git_repo: Path):
    (git_repo / "research/INDEX.md").write_text("dirty\n")
    with pytest.raises(ResearchGuardError, match="existing research changes"):
        ResearchGuard(git_repo).prepare()


def test_research_guard_keeps_allowed_changes_and_restores_forbidden_ones(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/addenda").mkdir()
    (git_repo / "research/addenda/2026-08-23-test.md").write_text("allowed\n")
    (git_repo / "research/INDEX.md").write_text("forbidden\n")

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert rejected_patch.is_file()
    assert (git_repo / "research/INDEX.md").read_text() == "index\n"
    assert (git_repo / "research/addenda/2026-08-23-test.md").read_text() == "allowed\n"


def test_research_guard_sees_a_staged_forbidden_change(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/CORPUS.md").write_text("rewritten\n")
    subprocess.run(["git", "add", "research/CORPUS.md"], cwd=git_repo, check=True)

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=git_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    assert staged == ""


def test_research_guard_quarantines_a_forbidden_untracked_file(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    forbidden = git_repo / "research/forbidden.md"
    forbidden.write_text("forbidden content\n")

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert "forbidden content" in rejected_patch.read_text()
    assert not forbidden.exists()


def test_research_guard_restores_a_staged_rename_of_a_corpus_file(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    subprocess.run(
        ["git", "mv", "research/CORPUS.md", "research/CORPUS2.md"], cwd=git_repo, check=True
    )

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    assert not (git_repo / "research/CORPUS2.md").exists()
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=git_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    assert staged == ""


def test_research_guard_refuses_a_pre_existing_staged_rename(git_repo: Path):
    subprocess.run(
        ["git", "mv", "research/CORPUS.md", "research/CORPUS2.md"], cwd=git_repo, check=True
    )
    with pytest.raises(ResearchGuardError, match="existing research changes"):
        ResearchGuard(git_repo).prepare()


def test_research_guard_restores_an_unstaged_move_of_a_corpus_file(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/CORPUS2.md").write_text((git_repo / "research/CORPUS.md").read_text())
    (git_repo / "research/CORPUS.md").unlink()

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    assert not (git_repo / "research/CORPUS2.md").exists()


def test_research_guard_refuses_a_nested_path_under_addenda(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    nested = git_repo / "research/addenda/sub/x.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("sneaky\n")

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert not nested.exists()


def test_research_guard_handles_a_staged_rename_with_further_edits(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    subprocess.run(["git", "mv", "research/CORPUS.md", "research/X.md"], cwd=git_repo, check=True)
    (git_repo / "research/X.md").write_text("immutable\nextra\n")

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    assert not (git_repo / "research/X.md").exists()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=git_repo,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    assert status == ""


def test_run_research_reports_a_guard_that_could_not_finish(monkeypatch, capsys):
    monkeypatch.setattr(ResearchGuard, "prepare", lambda self: None)
    monkeypatch.setattr(
        ResearchGuard,
        "finish",
        lambda self: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(
        project_agents.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(["codex"], 0, stdout=""),
    )

    assert project_agents.run_research("anything") == project_agents.GUARD_INCOMPLETE_EXIT
    error_output = capsys.readouterr().err
    assert "partially restored" in error_output
    assert "disk full" in error_output


def test_run_research_catches_a_called_process_error_from_the_guard(monkeypatch):
    monkeypatch.setattr(ResearchGuard, "prepare", lambda self: None)
    monkeypatch.setattr(
        ResearchGuard,
        "finish",
        lambda self: (_ for _ in ()).throw(subprocess.CalledProcessError(1, ["git", "rm"])),
    )
    monkeypatch.setattr(
        project_agents.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(["codex"], 0, stdout=""),
    )

    assert project_agents.run_research("anything") == project_agents.GUARD_INCOMPLETE_EXIT


def test_run_research_returns_the_codex_exit_code_on_a_clean_run(monkeypatch):
    monkeypatch.setattr(ResearchGuard, "prepare", lambda self: None)
    monkeypatch.setattr(ResearchGuard, "finish", lambda self: None)
    monkeypatch.setattr(
        project_agents.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(["codex"], 0, stdout=""),
    )

    assert project_agents.run_research("anything") == 0


def test_run_research_signals_a_rejected_patch_outside_codex_exit_codes(monkeypatch, tmp_path):
    patch = tmp_path / "rejected.patch"
    patch.write_text("x")
    monkeypatch.setattr(ResearchGuard, "prepare", lambda self: None)
    monkeypatch.setattr(ResearchGuard, "finish", lambda self: patch)
    monkeypatch.setattr(
        project_agents.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(["codex"], 0, stdout=""),
    )

    assert project_agents.run_research("anything") == project_agents.GUARD_REJECTED_EXIT


def test_guard_exit_codes_do_not_collide_with_codex_exit_codes():
    # Codex exits 1 on a runtime error and 2 on a usage error; a caller must be able to
    # tell those from a guard that rejected a change, could not finish one, or refused
    # to start at all.
    codex_exit_codes = {0, 1, 2}
    guard_exit_codes = {
        project_agents.GUARD_REJECTED_EXIT,
        project_agents.GUARD_INCOMPLETE_EXIT,
        project_agents.GUARD_REFUSED_EXIT,
    }
    assert guard_exit_codes.isdisjoint(codex_exit_codes)
    assert len(guard_exit_codes) == 3


def test_research_command_enables_web_search_as_config_not_a_flag():
    command = research_command("q", Path("/tmp/out.txt"))

    assert "--search" not in command
    assert "tools.web_search=true" in command


def test_knowledge_command_still_has_no_web_search():
    command = knowledge_command("q", Path("/tmp/out.txt"))

    assert "tools.web_search=true" not in command
    assert "--search" not in command


def test_neither_runner_lets_codex_inherit_stdin(monkeypatch, tmp_path):
    seen: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        seen.append(kwargs)
        index = command.index("--output-last-message")
        Path(command[index + 1]).write_text("{}")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(project_agents.subprocess, "run", fake_run)
    monkeypatch.setattr(ResearchGuard, "prepare", lambda self: None)
    monkeypatch.setattr(ResearchGuard, "finish", lambda self: None)

    project_agents.run_knowledge("q")
    project_agents.run_research("q")

    assert [captured.get("stdin") for captured in seen] == [
        subprocess.DEVNULL,
        subprocess.DEVNULL,
    ]


def test_research_guard_reports_a_write_outside_research(git_repo: Path):
    (git_repo / "src").mkdir()
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "src", "--allow-empty"], cwd=git_repo, check=True)
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "src" / "escaped.py").write_text("pwned\n")

    with pytest.raises(ResearchGuardError, match="wrote outside research/"):
        guard.finish()


def test_research_guard_detects_an_overwrite_of_an_already_dirty_file(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src/app.py").write_text("original\n")
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "app"], cwd=git_repo, check=True)
    (git_repo / "src/app.py").write_text("developer work in progress\n")
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "src/app.py").write_text("PWNED\n")

    with pytest.raises(ResearchGuardError, match="wrote outside research/"):
        guard.finish()


def test_research_guard_detects_a_revert_outside_research(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src/app.py").write_text("original\n")
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "app"], cwd=git_repo, check=True)
    (git_repo / "src/app.py").write_text("developer work in progress\n")
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "src/app.py").write_text("original\n")

    with pytest.raises(ResearchGuardError, match="wrote outside research/"):
        guard.finish()


def test_research_guard_ignores_pre_existing_changes_outside_research(git_repo: Path):
    (git_repo / "unrelated.txt").write_text("work in progress\n")
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/addenda").mkdir()
    (git_repo / "research/addenda/2026-08-23-x.md").write_text("ok\n")

    assert guard.finish() is None


def test_run_research_signals_a_refused_preflight_distinctly(monkeypatch):
    monkeypatch.setattr(
        ResearchGuard,
        "prepare",
        lambda self: (_ for _ in ()).throw(ResearchGuardError("existing research changes")),
    )

    assert project_agents.run_research("q") == project_agents.GUARD_REFUSED_EXIT
