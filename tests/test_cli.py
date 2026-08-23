import json

from cadence.cli import DIRTY_TREE_WARNING, _warn_if_dirty

MANIFEST_FIELDS = {
    "cadence_commit": "0" * 40,
    "cadence_dirty": False,
    "cadence_version": "0.0.0",
    "sumo_version": "1.27.1",
    "python_version": "3.12.0",
    "platform_tag": "Darwin-arm64",
    "binding": "traci",
    "controller_id": "none",
    "controller_version": "v1",
    "scenario_id": "s0_single_intersection",
    "scenario_version": 1,
    "network_sha256": "a" * 64,
    "demand_sha256": "b" * 64,
    "config_sha256": "c" * 64,
    "seed": 1,
    "begin_s": 0.0,
    "end_s": 600.0,
    "step_length_s": 1.0,
    "time_to_teleport_s": 300.0,
    "started_at_utc": "2026-08-23T00:00:00+00:00",
    "finished_at_utc": "2026-08-23T00:00:10+00:00",
}


def _write_manifest(tmp_path, *, dirty: bool):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fields = {**MANIFEST_FIELDS, "cadence_dirty": dirty}
    (run_dir / "manifest.json").write_text(json.dumps(fields))
    return run_dir


def test_warns_on_stderr_when_the_working_tree_is_dirty(tmp_path, capsys):
    run_dir = _write_manifest(tmp_path, dirty=True)
    _warn_if_dirty(run_dir)
    captured = capsys.readouterr()
    assert DIRTY_TREE_WARNING in captured.err
    assert captured.out == ""


def test_does_not_warn_when_the_working_tree_is_clean(tmp_path, capsys):
    run_dir = _write_manifest(tmp_path, dirty=False)
    _warn_if_dirty(run_dir)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
