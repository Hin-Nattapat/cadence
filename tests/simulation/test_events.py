import polars as pl

from cadence.simulation.events import EventKind, EventLog, SimulationEvent


def _events(time_s, kinds):
    return tuple(
        SimulationEvent(time_s=time_s, kind=kind, vehicle_id=f"v{index}")
        for index, kind in enumerate(kinds)
    )


def test_event_is_frozen():
    event = SimulationEvent(time_s=1.0, kind=EventKind.DEPARTED, vehicle_id="v0")
    try:
        event.time_s = 2.0
    except Exception as error:
        # CPython's FrozenInstanceError message is "cannot assign to field 'x'" on every
        # 3.7+ release (verified against the stdlib dataclasses source); it never contains
        # "frozen" or "attribute" even though the type subclasses AttributeError.
        message = str(error).lower()
        assert "frozen" in message or "attribute" in message or "cannot assign" in message
    else:
        raise AssertionError("SimulationEvent must be immutable")


def test_log_accumulates_events_in_order():
    log = EventLog()
    log.append(_events(1.0, [EventKind.DEPARTED]))
    log.append(_events(2.0, [EventKind.ARRIVED, EventKind.TELEPORT_STARTED]))
    assert [event.time_s for event in log.events] == [1.0, 2.0, 2.0]


def test_log_counts_by_kind():
    log = EventLog()
    log.append(_events(1.0, [EventKind.DEPARTED, EventKind.DEPARTED]))
    log.append(_events(2.0, [EventKind.ARRIVED]))
    assert log.count(EventKind.DEPARTED) == 2
    assert log.count(EventKind.ARRIVED) == 1
    assert log.count(EventKind.COLLISION) == 0


def test_log_writes_readable_parquet(tmp_path):
    log = EventLog()
    log.append(_events(1.0, [EventKind.DEPARTED]))
    log.append(_events(2.0, [EventKind.TELEPORT_STARTED]))
    output = tmp_path / "events.parquet"
    log.to_parquet(output)

    frame = pl.read_parquet(output)
    assert frame.columns == ["time_s", "kind", "vehicle_id"]
    assert frame.height == 2
    assert frame["kind"].to_list() == ["departed", "teleport_started"]


def test_empty_log_still_writes_a_valid_file(tmp_path):
    output = tmp_path / "events.parquet"
    EventLog().to_parquet(output)
    assert pl.read_parquet(output).height == 0
