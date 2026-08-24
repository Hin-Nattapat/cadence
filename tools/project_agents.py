from __future__ import annotations

import argparse
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
