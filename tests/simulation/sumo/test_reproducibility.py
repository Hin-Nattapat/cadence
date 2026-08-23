import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from cadence.cli import run_scenario
from cadence.simulation.manifest import RunManifest
from cadence.simulation.sumo.binding import BindingKind

S0_ROOT = Path(__file__).resolve().parents[3] / "scenarios" / "s0_single_intersection" / "v1"

pytestmark = pytest.mark.sumo


def _run(tmp_path, name, seed):
    return run_scenario(S0_ROOT, tmp_path / name, seed=seed, binding=BindingKind.TRACI)


def test_the_same_seed_produces_an_identical_event_stream(tmp_path):
    first = pl.read_parquet(_run(tmp_path, "a", 1) / "events.parquet")
    second = pl.read_parquet(_run(tmp_path, "b", 1) / "events.parquet")
    # Two empty frames compare equal, which would make the assertion below vacuous.
    assert first.height > 0
    assert first.equals(second)


def test_a_different_seed_produces_a_different_event_stream(tmp_path):
    # The seed reaching SUMO is otherwise unproven: test_seed_overrides_the_scenario_default
    # only inspects the argument vector. Seeds 1 and 2 differ in hundreds of arrival times.
    first = pl.read_parquet(_run(tmp_path, "c", 1) / "events.parquet")
    second = pl.read_parquet(_run(tmp_path, "c2", 2) / "events.parquet")
    assert first.height > 0
    assert not first.equals(second)


def test_manifests_match_except_for_timestamps(tmp_path):
    first = RunManifest(**json.loads((_run(tmp_path, "d", 1) / "manifest.json").read_text()))
    second = RunManifest(**json.loads((_run(tmp_path, "e", 1) / "manifest.json").read_text()))
    assert first.reproducible_fields() == second.reproducible_fields()


def test_a_same_second_run_refuses_to_overwrite(tmp_path, monkeypatch):
    # A real run takes over a second, so the second-resolution stamp differs on its own
    # and the collision path is never reached by accident. Freeze the clock to reach it.
    import cadence.cli as cli

    frozen = datetime(2026, 8, 23, 3, 0, 0, tzinfo=UTC)

    class FrozenClock:
        @staticmethod
        def now(tz: object = None) -> datetime:
            return frozen

    monkeypatch.setattr(cli, "datetime", FrozenClock)
    first = _run(tmp_path, "g", 1)
    assert (first / "manifest.json").is_file()
    with pytest.raises(FileExistsError):
        _run(tmp_path, "g", 1)


def test_the_manifest_records_the_scenario_content_hashes(tmp_path):
    manifest = json.loads((_run(tmp_path, "f", 1) / "manifest.json").read_text())
    assert len(manifest["network_sha256"]) == 64
    assert len(manifest["demand_sha256"]) == 64
    assert manifest["sumo_version"] == "1.27.1"
    assert manifest["seed"] == 1
