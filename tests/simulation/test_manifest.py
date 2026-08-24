import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadence.simulation.manifest import (
    NON_REPRODUCIBLE_FIELDS,
    RunManifest,
    TerminationReason,
    git_commit,
    working_tree_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FIELDS = {
    "cadence_commit",
    "cadence_dirty",
    "cadence_version",
    "sumo_version",
    "python_version",
    "platform_tag",
    "binding",
    "controller_id",
    "controller_version",
    "scenario_id",
    "scenario_version",
    "network_sha256",
    "demand_sha256",
    "config_sha256",
    "seed",
    "begin_s",
    "end_s",
    "step_length_s",
    "time_to_teleport_s",
    "terminal_time_s",
    "step_count",
    "unmatched_traversal_count",
    "termination_reason",
    "cadence_dirty_digest",
    "started_at_utc",
    "finished_at_utc",
}


def test_manifest_declares_every_reproducibility_field():
    assert set(RunManifest.model_fields) == FIELDS


def test_manifest_is_frozen(manifest_fixture):
    with pytest.raises(ValidationError):
        manifest_fixture.seed = 99


def test_manifest_round_trips_through_json(tmp_path, manifest_fixture):
    path = tmp_path / "manifest.json"
    path.write_text(manifest_fixture.model_dump_json(indent=2))
    assert RunManifest(**json.loads(path.read_text())) == manifest_fixture


def test_the_exclusion_set_names_only_real_fields():
    # Exact equality, not a subset check: a subset check keeps passing even if a real
    # field (e.g. `seed`) is added to NON_REPRODUCIBLE_FIELDS, silently dropping it from
    # every reproducibility comparison with nothing left to catch that. Lives here rather
    # than beside the reproducibility tests because it needs no simulator and must stay
    # reachable under `-m "not sumo"`.
    assert {"started_at_utc", "finished_at_utc"} == NON_REPRODUCIBLE_FIELDS


def test_git_commit_reports_the_repository_head():
    assert len(git_commit(REPO_ROOT)) == 40


@pytest.fixture
def manifest_fixture():
    return RunManifest(
        cadence_commit="0" * 40,
        cadence_dirty=False,
        cadence_version="0.0.0",
        sumo_version="1.27.1",
        python_version="3.12.0",
        platform_tag="Darwin-arm64",
        binding="traci",
        controller_id="none",
        controller_version="v1",
        scenario_id="s0_single_intersection",
        scenario_version=1,
        network_sha256="a" * 64,
        demand_sha256="b" * 64,
        config_sha256="c" * 64,
        seed=1,
        begin_s=0.0,
        end_s=600.0,
        step_length_s=1.0,
        time_to_teleport_s=300.0,
        terminal_time_s=558.0,
        step_count=558,
        unmatched_traversal_count=0,
        termination_reason=TerminationReason.DRAINED,
        cadence_dirty_digest=None,
        started_at_utc="2026-08-23T00:00:00+00:00",
        finished_at_utc="2026-08-23T00:00:10+00:00",
    )


def _repository_with_one_commit(root: Path) -> None:
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.com"],
        ["git", "config", "user.name", "T"],
    ):
        subprocess.run(command, cwd=root, check=True)
    (root / "a.txt").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=root, check=True)


def test_the_manifest_records_how_the_run_ended(manifest_fixture):
    assert manifest_fixture.terminal_time_s == 558.0
    assert manifest_fixture.step_count == 558
    assert manifest_fixture.termination_reason is TerminationReason.DRAINED


def test_run_outcome_is_part_of_the_reproducible_comparison(manifest_fixture):
    # Two runs of the same scenario and seed that ended differently are not the same run,
    # and saying so is exactly what M1b's verify-run has to be able to do.
    fields = manifest_fixture.reproducible_fields()
    assert {"terminal_time_s", "step_count", "termination_reason"} <= set(fields)


def test_a_clean_tree_has_no_digest(tmp_path):
    _repository_with_one_commit(tmp_path)
    assert working_tree_digest(tmp_path) is None


def test_two_different_dirty_trees_produce_different_digests(tmp_path):
    _repository_with_one_commit(tmp_path)

    (tmp_path / "a.txt").write_text("first change\n")
    first = working_tree_digest(tmp_path)
    (tmp_path / "a.txt").write_text("second change\n")
    second = working_tree_digest(tmp_path)

    assert first is not None and second is not None
    assert first != second, "ST-D11: a boolean cannot tell these two runs apart"


def test_an_untracked_file_alone_makes_the_tree_dirty(tmp_path):
    # `git diff HEAD` is blind to a file git has never seen, and a scenario or a scratch
    # script added but not committed changes what a run does.
    _repository_with_one_commit(tmp_path)
    (tmp_path / "new.txt").write_text("untracked\n")
    assert working_tree_digest(tmp_path) is not None


def test_two_untracked_files_in_one_directory_are_told_apart(tmp_path):
    # `git status --porcelain` without -uall collapses an untracked directory to a single
    # `?? scratch/` line, so two trees differing only inside it hash the same. A scratch
    # directory of generated scenarios is exactly where that happens.
    _repository_with_one_commit(tmp_path)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    (scratch / "a.txt").write_text("a\n")
    first = working_tree_digest(tmp_path)
    (scratch / "a.txt").unlink()
    (scratch / "b.txt").write_text("b\n")
    second = working_tree_digest(tmp_path)

    assert first is not None and second is not None
    assert first != second
