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
    schema = json.loads((REPO_ROOT / "tools/agent_prompts/knowledge.schema.json").read_text())

    required = set(schema["required"])
    assert {"mode", "answer", "touched_decision_ids", "defer_to_user"} <= required
    assert schema["additionalProperties"] is False


def test_empty_question_is_rejected():
    with pytest.raises(SystemExit):
        main(["knowledge", ""])
