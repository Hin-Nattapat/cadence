import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadence.simulation.manifest import NON_REPRODUCIBLE_FIELDS, RunManifest, git_commit

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
    sha, dirty = git_commit(REPO_ROOT)
    assert len(sha) == 40
    assert isinstance(dirty, bool)


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
        started_at_utc="2026-08-23T00:00:00+00:00",
        finished_at_utc="2026-08-23T00:00:10+00:00",
    )
