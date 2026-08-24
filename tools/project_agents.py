from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = REPO_ROOT / "tools" / "agent_prompts"


def knowledge_command(question: str, output_path: Path) -> list[str]:
    prompt = (PROMPT_ROOT / "knowledge.md").read_text() + "\n\nUser question:\n" + question
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--model",
        "gpt-5.6-luna",
        "--config",
        'model_reasoning_effort="medium"',
        "--sandbox",
        "read-only",
        "--output-schema",
        str(PROMPT_ROOT / "knowledge.schema.json"),
        "--json",
        "--output-last-message",
        str(output_path),
        prompt,
    ]


def run_knowledge(question: str) -> int:
    with tempfile.TemporaryDirectory(prefix="cadence-knowledge-") as directory:
        output_path = Path(directory) / "answer.json"
        completed = subprocess.run(
            knowledge_command(question, output_path),
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            # GOTCHA: without this codex inherits our stdin and blocks reading it. Every
            # caller here is non-interactive, and the prompt is already in argv.
            stdin=subprocess.DEVNULL,
        )
        sys.stderr.write(completed.stdout)
        if completed.returncode:
            return completed.returncode
        if output_path.exists():
            sys.stdout.write(output_path.read_text())
    return 0


HANDOFF_PATH = Path("research/CHATGPT_KNOWLEDGE_HANDOFF.md")
REFERENCES_PATH = Path("research/references.bib")


def is_allowed_research_output(path: Path) -> bool:
    normalized = Path(path.as_posix())
    return normalized in {HANDOFF_PATH, REFERENCES_PATH} or (
        normalized.parent == Path("research/addenda") and normalized.suffix == ".md"
    )


def research_command(question: str, output_path: Path, model: str = "gpt-5.6-terra") -> list[str]:
    prompt = (PROMPT_ROOT / "research.md").read_text() + "\n\nResearch question:\n" + question
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--model",
        model,
        "--config",
        'model_reasoning_effort="high"',
        "--config",
        "sandbox_workspace_write.network_access=false",
        # `--search` is a top-level codex flag, not an exec one; exec takes the tool as config.
        "--config",
        "tools.web_search=true",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(REPO_ROOT / "research"),
        "--json",
        "--output-last-message",
        str(output_path),
        prompt,
    ]


class ResearchGuardError(RuntimeError):
    pass


class ResearchGuard:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.prepared = False
        self.quarantine_root: Path | None = None
        self.outside_before: dict[Path, str] = {}

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout

    def changed_paths(self) -> set[Path]:
        # GOTCHA: `git diff` compares the worktree to the index, so anything already
        # staged is invisible to it. HEAD is the only baseline that sees both.
        # GOTCHA: --no-renames is load-bearing. Rename detection collapses a staged
        # `git mv` into the new path alone, so the corpus file it moved away from never
        # appears as changed and never gets restored.
        tracked = self._git(
            "diff", "--name-only", "--no-renames", "HEAD", "--", "research"
        ).splitlines()
        untracked = self._git(
            "ls-files", "--others", "--exclude-standard", "--", "research"
        ).splitlines()
        return {Path(path) for path in tracked + untracked}

    # GOTCHA: this sees only what git shows. `ls-files --others --exclude-standard` omits
    # ignored paths and `git diff HEAD` never lists them, so .venv/, the caches and run
    # outputs are outside its reach. Widening it there would flag every `make check` run,
    # and a check that cries wolf gets switched off. The sandbox is the containment; this
    # is a backstop over git-visible content, and the spec now says so.
    def _changed_outside_research(self) -> set[Path]:
        tracked = self._git("diff", "--name-only", "--no-renames", "HEAD").splitlines()
        untracked = self._git("ls-files", "--others", "--exclude-standard").splitlines()
        return {
            Path(path) for path in tracked + untracked if not Path(path).is_relative_to("research")
        }

    def _outside_state(self) -> dict[Path, str]:
        """Content identity of every git-visible path outside research/ that differs from HEAD.

        Paths alone are not enough: a file already dirty when the run began would otherwise
        be exempt for the rest of it, and those are exactly the files someone is editing.
        """
        state: dict[Path, str] = {}
        for path in self._changed_outside_research():
            full = self.repo_root / path
            state[path] = (
                hashlib.sha256(full.read_bytes()).hexdigest() if full.is_file() else "absent"
            )
        return state

    def _paths_at_head(self) -> set[str]:
        # ls-tree, not ls-files: a staged deletion leaves the index but not HEAD, and a
        # deleted corpus file still has to be restorable.
        return set(self._git("ls-tree", "-r", "--name-only", "HEAD", "--", "research").splitlines())

    def prepare(self) -> None:
        if self.changed_paths():
            raise ResearchGuardError("existing research changes require review")
        # The sandbox is supposed to confine the agent to research/. Nothing here proves
        # it does, and a web-enabled workspace-write agent is not something to take on
        # trust, so record what lies outside and check it again afterwards.
        self.outside_before = self._outside_state()
        self.prepared = True

    def finish(self) -> Path | None:
        if not self.prepared:
            raise ResearchGuardError("guard was not prepared")
        after = self._outside_state()
        escaped = sorted(
            path
            for path in set(self.outside_before) | set(after)
            if self.outside_before.get(path) != after.get(path)
        )
        if escaped:
            raise ResearchGuardError(
                "the research agent wrote outside research/: "
                + ", ".join(str(path) for path in escaped)
            )
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
                cwd=self.repo_root,
                text=True,
                stdout=subprocess.PIPE,
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
            # shows it.
            self._git(
                "rm", "--cached", "--force", "--ignore-unmatch", "--quiet", "--", str(relative)
            )
            destination = self.repo_root / relative
            if destination.exists():
                rejected = self.quarantine_root / "rejected-files" / relative
                rejected.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(destination, rejected)
        return patch_path


# Codex itself exits 1 on a runtime error and 2 on a usage error, both measured against
# codex-cli 0.149.0. run_research passes its exit code through unchanged, so our own
# signals have to live outside that band or a caller cannot tell them apart.
GUARD_REJECTED_EXIT = 20
GUARD_INCOMPLETE_EXIT = 21
# Preflight refused, so nothing ran and research/ is exactly as the caller left it.
# Distinct from 21, which means the guard started and could not finish.
GUARD_REFUSED_EXIT = 22


def run_research(question: str, model: str = "gpt-5.6-terra") -> int:
    guard = ResearchGuard(REPO_ROOT)
    try:
        guard.prepare()
    except ResearchGuardError as error:
        print(f"research agent did not start: {error}", file=sys.stderr)
        return GUARD_REFUSED_EXIT
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
            # Any guard failure, not only ResearchGuardError: a filesystem error
            # partway through the restore loop leaves research/ half restored. That
            # must never be reported as a completed run, nor mask the error that
            # caused it.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    knowledge = subparsers.add_parser("knowledge")
    knowledge.add_argument("question")
    research = subparsers.add_parser("research")
    research.add_argument("question")
    research.add_argument(
        "--model", choices=["gpt-5.6-terra", "gpt-5.6-sol"], default="gpt-5.6-terra"
    )
    args = parser.parse_args(argv)
    if not args.question.strip():
        parser.error("question must not be empty")
    if args.command == "knowledge":
        return run_knowledge(args.question)
    return run_research(args.question, model=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
