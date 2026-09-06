import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadence.simulation.manifest import (
    COMPARABILITY_FIELDS,
    DIRTINESS_FIELDS,
    INTENDED_DIFFERENCE_FIELDS,
    NON_REPRODUCIBLE_FIELDS,
    OUTCOME_FIELDS,
    ComparisonKind,
    RunManifest,
    TerminationReason,
    compare_manifests,
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


# --- ST-D33: comparability is a different question from reproducibility -----------------


def test_the_five_field_sets_partition_the_manifest_exactly():
    # A field added later must land in exactly one set, or this fails until someone
    # classifies it as input, intended difference, outcome, dirtiness or noise.
    sets = (
        COMPARABILITY_FIELDS,
        INTENDED_DIFFERENCE_FIELDS,
        OUTCOME_FIELDS,
        DIRTINESS_FIELDS,
        NON_REPRODUCIBLE_FIELDS,
    )
    assert frozenset().union(*sets) == set(RunManifest.model_fields)
    assert sum(len(fields) for fields in sets) == len(RunManifest.model_fields)


def test_two_identical_runs_are_a_reproducibility_check(manifest_fixture):
    comparison = compare_manifests(manifest_fixture, manifest_fixture)
    assert comparison.comparable
    assert comparison.kind is ComparisonKind.REPRODUCIBILITY
    assert comparison.intended_differences == {}


def test_two_runs_differing_only_in_controller_identity_are_comparable(manifest_fixture):
    # The defect the plan's first draft would have shipped: reusing reproducible_fields()
    # refuses exactly this, M3's fixed-time-versus-actuated comparison.
    other = manifest_fixture.model_copy(
        update={"controller_id": "actuated", "controller_version": "v2"}
    )
    comparison = compare_manifests(manifest_fixture, other)
    assert comparison.comparable
    assert comparison.kind is ComparisonKind.CONTROLLER_COMPARISON
    assert comparison.intended_differences == {
        "controller_id": ("none", "actuated"),
        "controller_version": ("v1", "v2"),
    }
    assert comparison.mismatched_comparability_fields == {}


def test_two_runs_differing_only_in_seed_are_a_seed_replicate(manifest_fixture):
    # Spec §7: two seeds of one controller is a replicate of that controller, not a
    # comparison between two of them -- the first thing anyone runs after M2, and the
    # headline word is what a reader takes the pair to be.
    other = manifest_fixture.model_copy(update={"seed": 7})
    comparison = compare_manifests(manifest_fixture, other)
    assert comparison.comparable
    assert comparison.kind is ComparisonKind.SEED_REPLICATE
    assert comparison.intended_differences == {"seed": (1, 7)}


def test_a_run_outcome_never_decides_comparability(manifest_fixture):
    other = manifest_fixture.model_copy(
        update={
            "terminal_time_s": 600.0,
            "step_count": 600,
            "unmatched_traversal_count": 3,
            "termination_reason": TerminationReason.HORIZON,
            "started_at_utc": "2026-08-24T00:00:00+00:00",
            "finished_at_utc": "2026-08-24T00:00:10+00:00",
        }
    )
    assert compare_manifests(manifest_fixture, other).comparable


def _a_different_value(value: object) -> object:
    # Every comparability and intended-difference field is a str, an int or a float, and
    # which different value it takes never matters -- only that it differs.
    if isinstance(value, str):
        return value + "_changed"
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    raise AssertionError(f"no rule for changing a {type(value).__name__}")


@pytest.mark.parametrize("field", sorted(COMPARABILITY_FIELDS))
def test_every_comparability_field_alone_refuses_the_comparison(manifest_fixture, field):
    # The partition test catches a field belonging to no set or to two. It does not catch a
    # field *moved*: with time_to_teleport_s in OUTCOME_FIELDS instead, two runs whose
    # teleport threshold differs by 10x stay comparable and every other test stays green.
    # Each field is tied to the refusal here, one at a time, or none of them is.
    original = getattr(manifest_fixture, field)
    changed = _a_different_value(original)
    other = manifest_fixture.model_copy(update={field: changed})

    comparison = compare_manifests(manifest_fixture, other)

    assert not comparison.comparable
    assert comparison.mismatched_comparability_fields == {field: (original, changed)}


@pytest.mark.parametrize("field", sorted(INTENDED_DIFFERENCE_FIELDS))
def test_every_intended_difference_field_alone_is_accepted_and_reported(manifest_fixture, field):
    original = getattr(manifest_fixture, field)
    changed = _a_different_value(original)
    other = manifest_fixture.model_copy(update={field: changed})

    comparison = compare_manifests(manifest_fixture, other)

    assert comparison.comparable
    assert comparison.intended_differences == {field: (original, changed)}
    assert comparison.mismatched_comparability_fields == {}


def test_the_dirty_flag_without_a_digest_still_refuses(manifest_fixture):
    # The two dirtiness fields are one signal. This manifest is where reading the boolean
    # says "refuse" and reading the digest says "compare", so both have to be read.
    flagged = manifest_fixture.model_copy(update={"cadence_dirty": True})
    comparison = compare_manifests(manifest_fixture, flagged)
    assert flagged.cadence_dirty_digest is None
    assert not comparison.comparable
    assert (comparison.left_dirty, comparison.right_dirty) == (False, True)


def test_a_dirty_run_is_refused_even_when_every_field_agrees(manifest_fixture):
    # M1a spec §9.2 / ST-D11: the digest is the detection; this is the refusal.
    dirty = manifest_fixture.model_copy(
        update={"cadence_dirty": True, "cadence_dirty_digest": "e" * 64}
    )
    comparison = compare_manifests(manifest_fixture, dirty)
    assert not comparison.comparable
    assert (comparison.left_dirty, comparison.right_dirty) == (False, True)
    assert comparison.mismatched_comparability_fields == {}
