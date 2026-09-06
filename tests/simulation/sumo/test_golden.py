"""Map R6 / SIG-D08: the M1 artifact set of a run with no controller, recorded before M2's
first line of code and compared on every run after it. The layer must be able to disappear.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from cadence.cli import run_scenario
from cadence.simulation.sumo.binding import BindingKind

pytestmark = pytest.mark.sumo

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "s0_turning-v1-seed1.json"

# spec §7.3: the M1 artifact set, named partition by partition rather than as "every parquet
# minus what M2 adds" -- a run directory also grows metrics/ under `cadence metrics`, and the
# session fixture this test reads is scored by other tests in the same session.
_M1_PARTITIONS = ("topology", "state", "ground_truth")
_M1_FILES = ("events.parquet", "evaluation/tripinfo.parquet")
_OUTSIDE_THE_M1_ARTIFACT_SET = frozenset({"state/signal_event.parquet"})


def _m1_artifact_paths(run_dir: Path) -> list[Path]:
    paths = [run_dir / relative for relative in _M1_FILES]
    for partition in _M1_PARTITIONS:
        paths.extend(sorted((run_dir / partition).glob("*.parquet")))
    return [
        path for path in paths if str(path.relative_to(run_dir)) not in _OUTSIDE_THE_M1_ARTIFACT_SET
    ]


def m1_artifact_digests(run_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(run_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in _m1_artifact_paths(run_dir)
    }


def _assert_matches_the_golden_digest(run_dir: Path) -> None:
    measured = m1_artifact_digests(run_dir)
    assert measured, f"{run_dir}: the run wrote no parquet at all"
    if not GOLDEN.exists():
        # GOTCHA: a golden value is never recorded and trusted in one motion. The first run
        # writes it and fails, so the value that gets committed is one a person has seen.
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n")
        pytest.fail(f"golden digest recorded at {GOLDEN}; rerun to compare against it")
    expected = json.loads(GOLDEN.read_text())
    differing = {
        relative: (expected.get(relative), measured.get(relative))
        for relative in sorted(set(expected) | set(measured))
        if expected.get(relative) != measured.get(relative)
    }
    assert not differing, (
        f"the M1 artifact set changed for a run with no controller (SIG-D08): {differing}"
    )


def test_a_controller_less_run_matches_the_golden_digest_under_libsumo(turning_run_dir):
    _assert_matches_the_golden_digest(turning_run_dir)


def test_a_missing_golden_file_is_recorded_and_still_fails(tmp_path, monkeypatch, turning_run_dir):
    # The branch that bootstraps the fixture: it runs once in the life of the file and
    # otherwise never again, so the only way it is known to work is to make it run.
    committed = GOLDEN
    recorded = tmp_path / "recorded" / "s0_turning-v1-seed1.json"
    monkeypatch.setattr(sys.modules[__name__], "GOLDEN", recorded)

    with pytest.raises(pytest.fail.Exception, match="rerun to compare"):
        _assert_matches_the_golden_digest(turning_run_dir)

    assert set(json.loads(recorded.read_text())) == set(json.loads(committed.read_text()))


def test_a_controller_less_run_matches_the_golden_digest_under_traci(tmp_path, repo_root):
    run_dir = run_scenario(
        repo_root / "scenarios/s0_turning/v1", tmp_path, seed=1, binding=BindingKind.TRACI
    )
    _assert_matches_the_golden_digest(run_dir)
