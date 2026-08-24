# CLI Research and Knowledge Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Claude Code a read-only Knowledge Agent and a web-enabled Research Agent that can add reviewed research without modifying the existing corpus.

**Architecture:** A single Python CLI composes and runs `codex exec` commands. Knowledge calls are schema-constrained and read-only; research calls run from `research/`, use native web search, and pass a post-run allowlist guard that restores forbidden changes. A Claude Code `PreToolUse` hook reserves `research/decisions.yaml` and `research/INDEX.md` for Claude while blocking its other Write/Edit calls under `research/`.

**Tech Stack:** Python 3.12 standard library, Codex CLI 0.149+, Claude Code project hooks, pytest, JSON Schema consumed directly by `codex exec --output-schema`.

**Spec:** `docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md`

## Global Constraints

- Discussion and agent-facing summaries are Thai; repository files, prompts, identifiers, and commits are English.
- Knowledge uses `gpt-5.6-luna` with medium reasoning and no network or web search.
- Research uses `gpt-5.6-terra` with high reasoning, web search enabled as
  `-c tools.web_search=true`, and shell network disabled. `--search` is top-level only;
  `codex exec` rejects it.
- `gpt-5.6-sol` requires an explicit manual rerun; never retry automatically.
- Existing top-level research corpus Markdown is immutable except `INDEX.md` and the temporary handoff ledger.
- Research writes only `research/addenda/*.md`, `research/references.bib`, and `research/CHATGPT_KNOWLEDGE_HANDOFF.md`.
- Claude writes only `research/decisions.yaml` and `research/INDEX.md` under `research/`.
- Neither agent commits or pushes. Claude reviews and commits research with the task that required it.
- No MCP server, SDK orchestrator, vector database, new dependency, or custom JSON Schema validator.
- Every behavior change follows a red-green test cycle; no paid inference is used in deterministic tests.

---

### Task 1: Adopt the design and confirm the migration baseline

**Files:**
- Modify: `docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md`

**Interfaces:**
- Consumes: `main`, which already carries the registry cleanup, the document-scanning
  decision checker, `PD-Q02`, `ST-D14`, and the tracked handoff ledger with its migration
  table.
- Produces: an adopted design spec and a verified baseline for the agent work.

- [ ] **Step 1: Mark the approved design adopted**

Change the spec header from:

```markdown
**Status:** proposed
```

to:

```markdown
**Status:** adopted
```

- [ ] **Step 2: Confirm the migration baseline is already in place**

Run:

```bash
rg -n "KH-010|pending M1b" research/CHATGPT_KNOWLEDGE_HANDOFF.md
rg -n "PD-Q02|ST-D14" research/decisions.yaml
```

Expected: the migration table marks `KH-010`-`KH-014` pending M1b and names `KH-010` a
mandatory anti-leakage rule; both `PD-Q02` and `ST-D14` are registered. These landed on
`main` before this branch. Do not re-register `KH-010` or `KH-011` against the M1a spec;
they belong to the M1b specification.

- [ ] **Step 3: Run the focused verification**

```bash
uv run pytest tests/test_decisions_registry.py -q
uv run python tools/check_decisions.py
```

Expected: the registry tests pass and the checker prints `Documentation consistency: OK`.

- [ ] **Step 4: Commit the adopted status**

```bash
git add docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md
git commit -m "docs: adopt the CLI agent design"
```

### Task 2: Define the Knowledge Agent contract and command

**Files:**
- Create: `tools/project_agents.py`
- Create: `tools/agent_prompts/knowledge.md`
- Create: `tools/agent_prompts/knowledge.schema.json`
- Create: `tests/test_project_agents.py`

**Interfaces:**
- Consumes: repository root discovered from `Path(__file__).resolve().parents[1]` and an arbitrary user question.
- Produces: `knowledge_command(question: str, output_path: Path) -> list[str]` and CLI command `knowledge` whose stdout is the schema-valid final JSON response.

- [ ] **Step 1: Write failing command-construction tests**

Create `tests/test_project_agents.py`:

```python
import json
from pathlib import Path

import pytest

from tools.project_agents import REPO_ROOT, knowledge_command, main


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
    schema = json.loads(
        (REPO_ROOT / "tools/agent_prompts/knowledge.schema.json").read_text()
    )

    required = set(schema["required"])
    assert {"mode", "answer", "touched_decision_ids", "defer_to_user"} <= required
    assert schema["additionalProperties"] is False


def test_empty_question_is_rejected():
    with pytest.raises(SystemExit):
        main(["knowledge", ""])
```

- [ ] **Step 2: Run the tests and observe the missing module failure**

Run:

```bash
uv run pytest tests/test_project_agents.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'tools.project_agents'`.

- [ ] **Step 3: Add the strict Knowledge output schema**

Create `tools/agent_prompts/knowledge.schema.json` with this top-level contract. Define every nested object with `additionalProperties: false`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "mode": {"enum": ["lookup", "decision_support"]},
    "answer": {"type": "string"},
    "recommended_option": {"type": ["string", "null"]},
    "recommended_refinement": {"type": ["string", "null"]},
    "opinion": {"type": ["string", "null"]},
    "defer_to_user": {"type": "boolean"},
    "touched_decision_ids": {"type": "array", "items": {"type": "string"}},
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {"type": "string"},
          "type": {"enum": ["evidence", "inference", "hypothesis", "decision", "open_question", "opinion"]},
          "sources": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "file": {"type": "string"},
                "decision_id": {"type": ["string", "null"]}
              },
              "required": ["file", "decision_id"],
              "additionalProperties": false
            }
          }
        },
        "required": ["text", "type", "sources"],
        "additionalProperties": false
      }
    },
    "tradeoffs": {"type": "array", "items": {"type": "string"}},
    "alternatives_rejected": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "option": {"type": "string"},
          "reason": {"type": "string"}
        },
        "required": ["option", "reason"],
        "additionalProperties": false
      }
    },
    "conflicts": {"type": "array", "items": {"type": "string"}},
    "confidence": {"enum": ["high", "medium", "low"]},
    "needs_research": {"type": "boolean"},
    "research_question": {"type": ["string", "null"]}
  },
  "required": ["mode", "answer", "recommended_option", "recommended_refinement", "opinion", "defer_to_user", "touched_decision_ids", "claims", "tradeoffs", "alternatives_rejected", "conflicts", "confidence", "needs_research", "research_question"],
  "additionalProperties": false
}
```

- [ ] **Step 4: Add the Knowledge Agent prompt**

Create `tools/agent_prompts/knowledge.md`:

```markdown
You are CADENCE's read-only Knowledge Agent. Answer only from the repository.

Use lookup mode for project facts, rationale, research, and adopted decisions. Use
decision_support mode to evaluate choices. Recommend a choice only when repository evidence
and clearly labelled professional judgment support it; otherwise set defer_to_user=true.
You may refine or combine options when the refinement is better supported than the options
as written.

Every material claim must cite a real repository path. Include a decision ID when applicable.
Separate evidence, inference, hypothesis, decision, open_question, and opinion. Never turn
missing knowledge into a guess. If new authoritative evidence is required, set
needs_research=true and provide one self-contained research_question.

Return only the requested schema. Write the answer text in Thai; preserve source titles,
technical terms, paths, identifiers, and citations in their original language.
```

- [ ] **Step 5: Implement the minimal Knowledge command**

Create `tools/project_agents.py` with these public pieces:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = REPO_ROOT / "tools" / "agent_prompts"


def knowledge_command(question: str, output_path: Path) -> list[str]:
    prompt = (PROMPT_ROOT / "knowledge.md").read_text() + "\n\nUser question:\n" + question
    return [
        "codex", "exec", "--ephemeral",
        "--model", "gpt-5.6-luna",
        "--config", 'model_reasoning_effort="medium"',
        "--sandbox", "read-only",
        "--output-schema", str(PROMPT_ROOT / "knowledge.schema.json"),
        "--json", "--output-last-message", str(output_path), prompt,
    ]


def run_knowledge(question: str) -> int:
    with tempfile.TemporaryDirectory(prefix="cadence-knowledge-") as directory:
        output_path = Path(directory) / "answer.json"
        completed = subprocess.run(
            knowledge_command(question, output_path), cwd=REPO_ROOT,
            # GOTCHA: without stdin=DEVNULL codex inherits the caller's stdin and blocks
            # reading it. Every caller here is non-interactive; the prompt is in argv.
            text=True, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
        )
        sys.stderr.write(completed.stdout)
        if completed.returncode:
            return completed.returncode
        sys.stdout.write(output_path.read_text())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    knowledge = subparsers.add_parser("knowledge")
    knowledge.add_argument("question")
    args = parser.parse_args(argv)
    if not args.question.strip():
        parser.error("question must not be empty")
    return run_knowledge(args.question)


if __name__ == "__main__":
    raise SystemExit(main())
```

Remove the unused `json` import if Ruff reports it; the schema is intentionally enforced by Codex rather than revalidated locally.

- [ ] **Step 6: Run focused checks**

Run:

```bash
uv run pytest tests/test_project_agents.py -q
uv run ruff check tools/project_agents.py tests/test_project_agents.py
uv run ruff format tools/project_agents.py tests/test_project_agents.py
uv run mypy tools/project_agents.py
```

Expected: all three tests pass and both static checks exit zero. Run the formatter rather
than `--check`: the code above is written compactly for reading, and `ruff format` owns the
committed layout. `make check` runs `ruff format --check .` at Task 5 and fails on any
file that was never formatted.

- [ ] **Step 7: Commit the Knowledge Agent contract**

```bash
git add tools/project_agents.py tools/agent_prompts/knowledge.md \
  tools/agent_prompts/knowledge.schema.json tests/test_project_agents.py
git commit -m "feat: add the knowledge agent contract"
```

### Task 3: Add the guarded Research Agent

**Files:**
- Modify: `tools/project_agents.py`
- Create: `tools/agent_prompts/research.md`
- Modify: `tests/test_project_agents.py`

**Interfaces:**
- Consumes: `research_command(question: str, output_path: Path, model: str = "gpt-5.6-terra") -> list[str]`, a clean `research/` tree, and the fixed output allowlist.
- Produces: CLI command `research`, allowed research diffs, and `ResearchGuardError` with a persistent temporary rejected-patch path for forbidden changes.

- [ ] **Step 1: Write failing allowlist and command tests**

Add `import subprocess` to `tests/test_project_agents.py`, then append:

```python
from tools.project_agents import is_allowed_research_output, research_command


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
    assert "--search" not in command
    assert "tools.web_search=true" in command
    assert "sandbox_workspace_write.network_access=false" in command


def test_research_command_allows_only_explicit_sol_escalation(tmp_path: Path):
    command = research_command(
        "Resolve conflicting evidence.", tmp_path / "answer.txt", model="gpt-5.6-sol"
    )
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
```

- [ ] **Step 2: Run the new tests and observe missing symbols**

Run:

```bash
uv run pytest tests/test_project_agents.py -q
```

Expected: import fails for `is_allowed_research_output` or `research_command`.

- [ ] **Step 3: Add the Research Agent prompt**

Create `tools/agent_prompts/research.md`:

```markdown
You are CADENCE's Research Agent. Read the entire repository and use native web search, but
write only English research outputs under the allowed paths.

Use only peer-reviewed papers, official standards/specifications, official documentation,
labelled preprints, and official issue trackers for software behavior. Do not use blogs,
forums, Reddit, secondary summaries, or AI answers as evidence. Verify bibliographic data
against publisher, official proceedings, or DOI landing pages. Never invent metadata or
results. Shell network is unavailable.

The current workspace is the repository's research/ directory. Existing corpus files,
INDEX.md, and decisions.yaml are immutable. Put new evidence or a correction in
addenda/YYYY-MM-DD-<topic>.md. You may update references.bib and the temporary
CHATGPT_KNOWLEDGE_HANDOFF.md. Classify statements as evidence, inference,
hypothesis, decision proposal, or open question. One question gets one research pass; if it
cannot be resolved, record the open question and stop. Do not commit or push.

Return a concise Thai summary of files changed, evidence quality, limitations, and any
decision or INDEX updates Claude should consider.
```

- [ ] **Step 4: Implement command construction and the allowlist**

Add to `tools/project_agents.py`:

```python
HANDOFF_PATH = Path("research/CHATGPT_KNOWLEDGE_HANDOFF.md")
REFERENCES_PATH = Path("research/references.bib")


def is_allowed_research_output(path: Path) -> bool:
    normalized = Path(path.as_posix())
    return (
        normalized in {HANDOFF_PATH, REFERENCES_PATH}
        or (normalized.parent == Path("research/addenda") and normalized.suffix == ".md")
    )


def research_command(
    question: str, output_path: Path, model: str = "gpt-5.6-terra"
) -> list[str]:
    prompt = (PROMPT_ROOT / "research.md").read_text() + "\n\nResearch question:\n" + question
    return [
        "codex", "exec", "--ephemeral",
        "--model", model,
        "--config", 'model_reasoning_effort="high"',
        "--config", "sandbox_workspace_write.network_access=false",
        # `--search` is a top-level codex flag, not an exec one; exec takes the tool as config.
        "--config", "tools.web_search=true",
        "--sandbox", "workspace-write",
        "--cd", str(REPO_ROOT / "research"),
        "--json", "--output-last-message", str(output_path), prompt,
    ]
```

- [ ] **Step 5: Write failing guard tests against a temporary Git repository**

Add this fixture and the guard tests:

```python
@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    research = tmp_path / "research"
    research.mkdir()
    (research / "INDEX.md").write_text("index\n")
    (research / "decisions.yaml").write_text("{}\n")
    (research / "CORPUS.md").write_text("immutable\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Tests"], cwd=tmp_path, check=True
    )
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
```

- [ ] **Step 6: Run guard tests and observe missing classes**

Run:

```bash
uv run pytest tests/test_project_agents.py -q
```

Expected: import or name failure for `ResearchGuard` and `ResearchGuardError`.

- [ ] **Step 7: Implement the minimal preflight/post-run guard**

Implement:

```python
class ResearchGuardError(RuntimeError):
    pass


class ResearchGuard:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.prepared = False
        self.quarantine_root: Path | None = None

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo_root, check=True, text=True,
            stdout=subprocess.PIPE,
        ).stdout

    def changed_paths(self) -> set[Path]:
        # GOTCHA: `git diff` compares the worktree to the index, so anything already
        # staged is invisible to it. HEAD is the only baseline that sees both.
        # GOTCHA: --no-renames is load-bearing too. Rename detection collapses a staged
        # `git mv` into the new path alone, so the corpus file it moved away from never
        # appears as changed and never gets restored.
        tracked = self._git(
            "diff", "--name-only", "--no-renames", "HEAD", "--", "research"
        ).splitlines()
        untracked = self._git(
            "ls-files", "--others", "--exclude-standard", "--", "research"
        ).splitlines()
        return {Path(path) for path in tracked + untracked}

    def _paths_at_head(self) -> set[str]:
        # ls-tree, not ls-files: a staged deletion leaves the index but not HEAD, and a
        # deleted corpus file still has to be restorable.
        return set(self._git("ls-tree", "-r", "--name-only", "HEAD", "--", "research").splitlines())

    def prepare(self) -> None:
        if self.changed_paths():
            raise ResearchGuardError("existing research changes require review")
        self.prepared = True

    def finish(self) -> Path | None:
        if not self.prepared:
            raise ResearchGuardError("guard was not prepared")
        forbidden = sorted(
            path for path in self.changed_paths() if not is_allowed_research_output(path)
        )
        if not forbidden:
            return None

        self.quarantine_root = Path(tempfile.mkdtemp(prefix="cadence-research-rejected-"))
        patch_path = self.quarantine_root / "rejected.patch"
        at_head = self._paths_at_head()
        tracked_forbidden = [str(path) for path in forbidden if str(path) in at_head]
        chunks = []
        if tracked_forbidden:
            chunks.append(self._git("diff", "--binary", "HEAD", "--", *tracked_forbidden))
        for relative in forbidden:
            if str(relative) in at_head:
                continue
            diff = subprocess.run(
                ["git", "diff", "--no-index", "--binary", "/dev/null", str(relative)],
                cwd=self.repo_root, text=True, stdout=subprocess.PIPE,
            )
            if diff.returncode not in {0, 1}:
                raise ResearchGuardError(f"could not preserve rejected file: {relative}")
            chunks.append(diff.stdout)
        patch_path.write_text("".join(chunks))

        # checkout restores the worktree and the index together. Copying a snapshot back
        # would leave the forbidden content staged, and the next commit would take it.
        if tracked_forbidden:
            self._git("checkout", "HEAD", "--", *tracked_forbidden)
        for relative in forbidden:
            if str(relative) in at_head:
                continue
            # A forbidden path absent from HEAD may still be staged - the destination half
            # of a `git mv`, or a plain `git add`. Dropping the file without dropping the
            # index entry leaves the change committable from a worktree that no longer
            # shows it. --force because git refuses when the worktree differs from both the
            # index and HEAD, and the content is already captured in the rejected patch.
            self._git(
                "rm", "--cached", "--force", "--ignore-unmatch", "--quiet", "--", str(relative)
            )
            destination = self.repo_root / relative
            if destination.exists():
                rejected = self.quarantine_root / "rejected-files" / relative
                rejected.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(destination, rejected)
        return patch_path
```

Import `shutil`. `prepare()` no longer snapshots: it refuses to run unless `research/` is
clean, so HEAD is already the baseline every restore needs.

Add these seven guard tests. The last four are regression tests for two holes a review found in an earlier draft of this guard: rename detection hides the moved-from path, and a quarantined file can leave its index entry behind.

```python
def test_research_guard_sees_a_staged_forbidden_change(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/CORPUS.md").write_text("rewritten\n")
    subprocess.run(["git", "add", "research/CORPUS.md"], cwd=git_repo, check=True)

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=git_repo,
        text=True, stdout=subprocess.PIPE, check=True,
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
    subprocess.run(["git", "mv", "research/CORPUS.md", "research/CORPUS2.md"],
                   cwd=git_repo, check=True)

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    assert not (git_repo / "research/CORPUS2.md").exists()
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=git_repo,
        text=True, stdout=subprocess.PIPE, check=True,
    ).stdout
    assert staged == ""


def test_research_guard_refuses_a_pre_existing_staged_rename(git_repo: Path):
    subprocess.run(["git", "mv", "research/CORPUS.md", "research/CORPUS2.md"],
                   cwd=git_repo, check=True)
    with pytest.raises(ResearchGuardError, match="existing research changes"):
        ResearchGuard(git_repo).prepare()


def test_research_guard_restores_an_unstaged_move_of_a_corpus_file(git_repo: Path):
    guard = ResearchGuard(git_repo)
    guard.prepare()
    (git_repo / "research/CORPUS2.md").write_text(
        (git_repo / "research/CORPUS.md").read_text()
    )
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
    subprocess.run(["git", "mv", "research/CORPUS.md", "research/X.md"],
                   cwd=git_repo, check=True)
    (git_repo / "research/X.md").write_text("immutable\nextra\n")

    rejected_patch = guard.finish()

    assert rejected_patch is not None
    assert (git_repo / "research/CORPUS.md").read_text() == "immutable\n"
    assert not (git_repo / "research/X.md").exists()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=git_repo,
        text=True, stdout=subprocess.PIPE, check=True,
    ).stdout
    assert status == ""
```

- [ ] **Step 8: Wire the guarded research subcommand**

Add `research` to `main()` and implement:

```python
def run_research(question: str, model: str = "gpt-5.6-terra") -> int:
    guard = ResearchGuard(REPO_ROOT)
    guard.prepare()
    guard_completed = True
    with tempfile.TemporaryDirectory(prefix="cadence-research-result-") as directory:
        output_path = Path(directory) / "answer.txt"
        try:
            completed = subprocess.run(
                research_command(question, output_path, model=model),
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
        finally:
            # Any guard failure, not only ResearchGuardError: a filesystem error partway
            # through the restore loop leaves research/ half restored. That must never be
            # reported as a completed run, nor mask the error that caused it.
            try:
                rejected_patch = guard.finish()
            except Exception as error:
                print(
                    f"research guard did not complete: {error!r}. research/ may be "
                    "partially restored; inspect it before committing.",
                    file=sys.stderr,
                )
                guard_completed = False
                rejected_patch = None
        sys.stderr.write(completed.stdout)
        if output_path.exists():
            sys.stdout.write(output_path.read_text())
        if not guard_completed:
            return GUARD_INCOMPLETE_EXIT
        if rejected_patch is not None:
            print(f"Rejected research patch: {rejected_patch}", file=sys.stderr)
            return GUARD_REJECTED_EXIT
        return completed.returncode
```

Add the constant beside the other module constants:

```python
# Codex itself exits 1 on a runtime error and 2 on a usage error, both measured against
# codex-cli 0.149.0. run_research passes its exit code through unchanged, so our own signals
# have to live outside that band or a caller cannot tell them apart.
GUARD_REJECTED_EXIT = 20
GUARD_INCOMPLETE_EXIT = 21
```

Do not write `# noqa: BLE001` on the bare `except Exception`. `BLE` is not in this
repository's ruff select list, so the directive would be unused and `RUF100` — which is
selected — would fail on it.

Create both subparsers in `main()` with the same required positional `question`. On the
research parser, add `--model` with choices `gpt-5.6-terra` and `gpt-5.6-sol`, defaulting to
Terra. Reject a blank value before dispatch, then dispatch `knowledge` to `run_knowledge()`
and `research` to `run_research(args.question, model=args.model)`. Do not add a Sol retry
path; Sol is reachable only through the explicit flag.

- [ ] **Step 9: Run focused checks**

Run:

```bash
uv run pytest tests/test_project_agents.py -q
uv run ruff check tools/project_agents.py tests/test_project_agents.py
uv run ruff format tools/project_agents.py tests/test_project_agents.py
uv run mypy tools/project_agents.py
```

Expected: all tests and static checks pass.

- [ ] **Step 10: Commit the Research Agent**

```bash
git add tools/project_agents.py tools/agent_prompts/research.md tests/test_project_agents.py
git commit -m "feat: add the guarded research agent"
```

### Task 4: Enforce Claude's research ownership boundary

**Files:**
- Create: `.claude/settings.json`
- Create: `tools/protect_research_hook.py`
- Create: `tests/test_research_write_hook.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Claude Code `PreToolUse` JSON with an absolute `tool_input.file_path`.
- Produces: `hookSpecificOutput.permissionDecision="deny"` for research paths other than
  `INDEX.md` and `decisions.yaml`, deny on any unusable payload, and silence for permitted
  paths.

The hook lives in `tools/`, not `.claude/hooks/`. `pyproject.toml` sets mypy
`files = ["src", "tools"]`, so a script under `.claude/` would be type-checked once by hand
and never again by `make check`. A security boundary needs a standing gate, and
`tools/check_decisions.py` is the existing precedent for repository tooling.

- [ ] **Step 1: Write failing hook unit tests**

Create `tests/test_research_write_hook.py`:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "tools/protect_research_hook.py"


def run_hook(payload: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"CLAUDE_PROJECT_DIR": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
    )


def write_payload(path: Path) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})


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
```

- [ ] **Step 2: Run the tests and observe the missing hook failure**

Run:

```bash
uv run pytest tests/test_research_write_hook.py -q
```

Expected: every test fails because `tools/protect_research_hook.py` does not exist.

- [ ] **Step 3: Implement the fail-closed hook**

Create `tools/protect_research_hook.py`:

```python
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


def is_inside(target: Path, root: Path) -> bool:
    if target.is_relative_to(root):
        return True
    # GOTCHA: on a case-insensitive filesystem, resolve() does not canonicalise directory
    # case, so research/ reached as RESEARCH/ compares as a different tree while naming the
    # same inode. Identity on the nearest existing ancestor is the only reliable test.
    if not root.exists():
        # No research tree in this checkout, so nothing can be inside one. Without this,
        # samefile() below raises FileNotFoundError on the ROOT side for every ancestor and
        # the blanket deny then refuses every write in the project.
        return False
    # GOTCHA: Path.exists() re-raises OSError for EACCES - Python swallows only ENOENT,
    # ENOTDIR, EBADF and ELOOP. That escapes to main's boundary and denies, on purpose:
    # answering "not inside" when the filesystem refused to say would allow the write.
    for ancestor in (target, *target.parents):
        if ancestor.exists() and ancestor.samefile(root):
            return True
    return False


def main() -> int:
    try:
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or DEFAULT_ROOT).resolve()
        research_root = root / "research"
        allowed = {research_root / name for name in GOVERNANCE_FILES}
        payload = json.load(sys.stdin)
        raw = Path(payload["tool_input"]["file_path"])
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
```

The environment variable is an override, not a requirement: the repository root is
derivable from the script's own location, so a hook invoked without Claude Code's
environment still evaluates rather than crashing open.

- [ ] **Step 4: Register the project hook**

Create `.claude/settings.json`:

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
    ]
  }
}
```

A matcher that omits a writing tool is a silent hole, and the cost of an extra name is
zero. `NotebookEdit` is inert today because no notebook lives under `research/`, which is
exactly why it would be missed.

The governance allowlist stays an exact match, so `research/DECISIONS.YAML` is denied
rather than allowed. That is the safe direction: Claude uses the canonical lowercase path,
and a case-insensitive allowlist would open a hole opposite the one `is_inside` closes.

- [ ] **Step 5: Document routing and the Bash boundary**

Add a `Research and knowledge agents` section to `CLAUDE.md` that:

- invokes `uv run python tools/project_agents.py knowledge '<question>'` for project facts,
  rationale, decisions, or option evaluation;
- invokes `uv run python tools/project_agents.py research '<question>'` explicitly or when
  knowledge is missing, contradictory, uncited, or stale;
- tells the user why before an automatic research call;
- prohibits Claude from modifying research through Write, Edit, Bash, or any other tool
  except governance updates to `INDEX.md` and `decisions.yaml`;
- requires review of the research diff before a Knowledge rerun and commit;
- records that the hook covers Write/Edit/MultiEdit only, and that the Bash prohibition is
  a repository rule with no mechanical enforcement;
- removes the incorrect `PD-D03` citation from the existing English/Thai language rule
  without changing the rule.

Add the same Bash caveat to the design specification. A reader of the spec should not
conclude the boundary is mechanically sealed when one tool still reaches around it.

- [ ] **Step 6: Run focused checks**

Run:

```bash
uv run pytest tests/test_research_write_hook.py -q
uv run ruff check tools/protect_research_hook.py tests/test_research_write_hook.py
uv run ruff format tools/protect_research_hook.py tests/test_research_write_hook.py
uv run mypy
```

Expected: five tests pass and the static checks exit zero. `mypy` is run bare on purpose:
it must pick the hook up from the configured `files`, which is the point of placing it in
`tools/`.

- [ ] **Step 7: Commit the Claude boundary**

```bash
git add .claude/settings.json tools/protect_research_hook.py \
  tests/test_research_write_hook.py CLAUDE.md \
  docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md
git commit -m "feat: enforce research ownership in Claude"
```

### Task 5: Verify real CLI wiring and close the feature

**Files:**
- Modify: `docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md` only if the smoke test disproves an invocation assumption.
- Modify: `CLAUDE.md` only if the verified invocation differs from its documented command.

**Interfaces:**
- Consumes: both CLI subcommands, the Claude hook, and a clean research tree.
- Produces: evidence that local Codex reads the intended context and honors the output/write boundaries.

- [ ] **Step 1: Run the complete deterministic suite**

Run:

```bash
make check
git diff --check
```

Expected: Ruff, formatting, mypy, documentation consistency, and all tests pass; `git diff --check` exits zero.

- [ ] **Step 2: Smoke-test Knowledge output**

Run one paid/local-account inference:

```bash
uv run python tools/project_agents.py knowledge \
  'Which milestone first introduces RL-specific code, and which decision establishes it?'
```

Expected: valid JSON, Thai `answer`, `needs_research=false`, and a claim citing `PD-D02` plus its repository source. Confirm the JSONL progress is not mixed into the final stdout payload.

- [ ] **Step 3: Smoke-test Research context without creating research output**

Run:

```bash
uv run python tools/project_agents.py research \
  'Read ../CLAUDE.md and ../docs/DIRECTION.md. Do not edit files. Report the current milestone and the two research governance files.'
```

Expected: Thai summary naming the current milestone, `research/INDEX.md`, and `research/decisions.yaml`; no research diff. This proves `-C research` can read the parent repository and root instructions in the installed Codex CLI.

- [ ] **Step 4: Inspect usage and model identity**

From each command's captured `turn.completed` JSONL event, report usage.

Measured: the event carries token counts only and names no model, so model identity cannot
be confirmed from the transcript. It is pinned at the call site instead, by the
command-construction tests that assert the `--model` value. Record the usage and say that
plainly rather than claiming a confirmation the stream does not support.

What the transcript does confirm is the search asymmetry: the research run contains a
`web_search` item and the knowledge run contains none.

- [ ] **Step 5: Re-run verification after smoke tests**

Run:

```bash
make check
git status --short
git log --oneline -6
```

Expected: the suite passes, no smoke-test research diff remains, and the branch contains coherent cleanup, Knowledge Agent, Research Agent, and Claude-boundary commits.

- [ ] **Step 6: Commit only smoke-driven documentation corrections, if any**

If Step 2 or 3 required a documented command correction:

```bash
git add docs/superpowers/specs/2026-08-23-cli-research-knowledge-agents-design.md CLAUDE.md
git commit -m "docs: record verified agent invocation"
```

If no correction was required, do not create an empty closing commit.
