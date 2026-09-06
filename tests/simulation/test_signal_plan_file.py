import pytest
import yaml
from pydantic import ValidationError

from cadence.simulation.scenario import SIGNAL_PLAN_FILE_NAME, load_scenario
from cadence.simulation.signal_plan_file import (
    SignalPlanFile,
    load_signal_plan_file,
    signal_plan_digest,
)

VALID = """
signal_plan_version: 1
intersections:
  A0:
    stages:
      0: {min_green_s: 10.0, max_green_s: 60.0}
      2: {min_green_s: 10.0, max_green_s: 60.0}
"""


def _write(tmp_path, text=VALID):
    path = tmp_path / SIGNAL_PLAN_FILE_NAME
    path.write_text(text)
    return path


def test_loads_the_placeholder_envelope(tmp_path):
    plan = load_signal_plan_file(_write(tmp_path), step_length_s=1.0)
    assert set(plan.intersections) == {"A0"}
    assert set(plan.intersections["A0"].stages) == {0, 2}
    assert plan.intersections["A0"].stages[0].max_green_s == 60.0


def test_refuses_an_unknown_key(tmp_path):
    path = _write(
        tmp_path, VALID.replace("max_green_s: 60.0}", "max_green_s: 60.0, yellow_s: 3}", 1)
    )
    with pytest.raises(ValidationError):
        load_signal_plan_file(path, step_length_s=1.0)


def test_refuses_a_maximum_below_the_minimum(tmp_path):
    path = _write(
        tmp_path,
        VALID.replace(
            "2: {min_green_s: 10.0, max_green_s: 60.0}", "2: {min_green_s: 10.0, max_green_s: 5.0}"
        ),
    )
    with pytest.raises(ValidationError, match="max_green_s"):
        load_signal_plan_file(path, step_length_s=1.0)


def test_refuses_a_minimum_shorter_than_one_step(tmp_path):
    # spec §4.2: the executor decides once per step, so a shorter hold cannot be expressed.
    path = _write(tmp_path, VALID.replace("0: {min_green_s: 10.0", "0: {min_green_s: 0.5"))
    with pytest.raises(ValueError, match="shorter than step_length_s"):
        load_signal_plan_file(path, step_length_s=1.0)


def test_refuses_an_empty_file(tmp_path):
    # An empty envelope reached the model as None and raised TypeError, which
    # `validate-scenario` does not catch: the command promised a FAIL line and gave a
    # traceback.
    with pytest.raises(ValidationError):
        load_signal_plan_file(_write(tmp_path, ""), step_length_s=1.0)


def test_refuses_a_file_that_is_not_yaml(tmp_path):
    with pytest.raises(yaml.YAMLError):
        load_signal_plan_file(_write(tmp_path, "intersections: [unclosed\n"), step_length_s=1.0)


def test_refuses_an_envelope_with_no_intersection(tmp_path):
    # shortest_min_green_s() calls min() over the stages, which raises ValueError on an
    # empty envelope rather than saying what is wrong with the file.
    with pytest.raises(ValidationError):
        load_signal_plan_file(
            _write(tmp_path, "signal_plan_version: 1\nintersections: {}\n"), step_length_s=1.0
        )


def test_refuses_an_intersection_with_no_stage(tmp_path):
    with pytest.raises(ValidationError):
        load_signal_plan_file(
            _write(tmp_path, "signal_plan_version: 1\nintersections:\n  A0:\n    stages: {}\n"),
            step_length_s=1.0,
        )


def test_the_digest_is_content_sensitive_and_none_when_absent(tmp_path):
    path = _write(tmp_path)
    first = signal_plan_digest(path)
    assert first == signal_plan_digest(path)
    path.write_text(VALID.replace("60.0", "61.0"))
    assert signal_plan_digest(path) != first
    assert signal_plan_digest(None) is None


def test_the_model_is_frozen():
    plan = SignalPlanFile.model_validate(
        {
            "signal_plan_version": 1,
            "intersections": {"A0": {"stages": {0: {"min_green_s": 1, "max_green_s": 2}}}},
        }
    )
    with pytest.raises(ValidationError):
        plan.signal_plan_version = 2


def test_load_scenario_discovers_the_envelope_only_when_present(tmp_path):
    root = tmp_path / "s" / "v1"
    root.mkdir(parents=True)
    (root / "scenario.yaml").write_text(
        "scenario_id: s\nscenario_version: 1\ndescription: t\nnetwork_file: n.xml\n"
        "demand_file: d.xml\nbegin_s: 0.0\nend_s: 10.0\nstep_length_s: 1.0\n"
        "time_to_teleport_s: 300.0\ndefault_seed: 1\n"
    )
    (root / "n.xml").write_text("<net/>")
    (root / "d.xml").write_text("<routes/>")
    _, without = load_scenario(root)
    assert without.signal_plan is None
    _write(root)
    _, with_plan = load_scenario(root)
    assert with_plan.signal_plan == root / SIGNAL_PLAN_FILE_NAME
