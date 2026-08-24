import dataclasses

import polars as pl
import pytest

from cadence.simulation.artifacts import (
    EVALUATION_DIR,
    GROUND_TRUTH_DIR,
    STATE_DIR,
    TOPOLOGY_DIR,
    RunRecorder,
    _as_row,
)
from cadence.simulation.ground_truth import LaneTurnCount, SimulationGroundTruth
from cadence.simulation.state import (
    CanonicalTrafficState,
    ConnectionState,
    IntersectionState,
    LaneState,
    MovementState,
    NetworkState,
    SignalState,
    TeleportEvent,
    TeleportKind,
    Traversal,
)
from cadence.simulation.topology import (
    ConnectionInfo,
    LaneInfo,
    NetworkTopology,
    PhaseInfo,
    TurnDirection,
    build_movements,
    movement_id,
)
from cadence.types import ConnectionId, EdgeId, IntersectionId, LaneId, VehicleId

_TRIPINFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<tripinfos>
    <tripinfo id="v0" depart="0.00" arrival="42.00" duration="42.00" waitingTime="7.00"/>
</tripinfos>
"""


def _topology() -> NetworkTopology:
    lane = LaneInfo(LaneId("a_0"), EdgeId("a"), 0, 100.0, 13.89)
    out = LaneInfo(LaneId("b_0"), EdgeId("b"), 0, 100.0, 13.89)
    connection = ConnectionInfo(
        connection_id=ConnectionId("a_0|b_0"),
        intersection_id=IntersectionId("A0"),
        link_index=0,
        from_lane_id=LaneId("a_0"),
        to_lane_id=LaneId("b_0"),
        via_lane_id=LaneId(":A0_0_0"),
        from_edge_id=EdgeId("a"),
        to_edge_id=EdgeId("b"),
        turn_direction=TurnDirection.STRAIGHT,
        movement_id=movement_id(EdgeId("a"), EdgeId("b")),
    )
    return NetworkTopology(
        lanes={lane.lane_id: lane, out.lane_id: out},
        connections={connection.connection_id: connection},
        movements=build_movements([connection]),
        phases=(
            PhaseInfo(
                intersection_id=IntersectionId("A0"),
                program_id="0",
                phase_index=0,
                duration_s=42.0,
                min_duration_s=42.0,
                max_duration_s=42.0,
                signals=(SignalState.GREEN_PROTECTED,),
            ),
        ),
    )


def _state(time_s: float, topology: NetworkTopology) -> CanonicalTrafficState:
    lane = LaneState(LaneId("a_0"), 2, 1, 3.0, 0.1, 4.0)
    identifier = next(iter(topology.movements))
    return CanonicalTrafficState(
        time_s=time_s,
        topology=topology,
        lanes={lane.lane_id: lane},
        movements={
            identifier: MovementState(
                movement_id=identifier,
                signals=(SignalState.GREEN_PROTECTED,),
            )
        },
        intersections={
            IntersectionId("A0"): IntersectionState(
                IntersectionId("A0"),
                "0",
                0,
                5.0,
                (ConnectionState(ConnectionId("a_0|b_0"), SignalState.GREEN_PROTECTED),),
            )
        },
        traversals=(Traversal(time_s, VehicleId("v0"), identifier, ConnectionId("a_0|b_0")),),
        network=NetworkState(2, 0, 3, 1, 0),
    )


@pytest.fixture
def recorder(tmp_path):
    topology = _topology()
    return RunRecorder(tmp_path, topology), topology


def test_the_run_directory_has_the_specified_shape(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(
        state=_state(1.0, topology),
        teleports=(),
        truth=SimulationGroundTruth(1.0, (LaneTurnCount(LaneId("a_0"), EdgeId("b"), 2, 1, 4.0),)),
    )
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(_TRIPINFO_XML)
    run_recorder.write_tripinfo(tripinfo)
    run_recorder.write()

    for relative in (
        f"{TOPOLOGY_DIR}/lane.parquet",
        f"{TOPOLOGY_DIR}/connection.parquet",
        f"{TOPOLOGY_DIR}/tls_program.parquet",
        f"{STATE_DIR}/lane.parquet",
        f"{STATE_DIR}/intersection.parquet",
        f"{STATE_DIR}/signal.parquet",
        f"{STATE_DIR}/network.parquet",
        f"{STATE_DIR}/movement.parquet",
        f"{STATE_DIR}/traversal.parquet",
        f"{STATE_DIR}/teleport.parquet",
        f"{GROUND_TRUTH_DIR}/lane_turn.parquet",
        f"{EVALUATION_DIR}/tripinfo.parquet",
    ):
        assert (tmp_path / relative).is_file(), relative


def test_state_tables_carry_the_specified_columns(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    lane = pl.read_parquet(tmp_path / STATE_DIR / "lane.parquet")
    assert lane.columns == [
        "time_s",
        "lane_id",
        "vehicle_count_veh",
        "halting_count_veh",
        "mean_speed_mps",
        "occupancy_ratio",
        "waiting_total_now_s",
    ]
    signal = pl.read_parquet(tmp_path / STATE_DIR / "signal.parquet")
    assert signal.columns == ["time_s", "connection_id", "signal"]


def test_no_lamp_string_reaches_an_artifact(tmp_path, recorder):
    # ST-D04: decoding at extraction extends the rule to the artifacts, not just the code.
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    signal = pl.read_parquet(tmp_path / STATE_DIR / "signal.parquet")
    assert signal["signal"].to_list() == ["green_protected"]


def test_two_steps_append_rather_than_overwrite(tmp_path, recorder):
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.record(_state(2.0, topology), (), SimulationGroundTruth(2.0, ()))
    run_recorder.write()

    network = pl.read_parquet(tmp_path / STATE_DIR / "network.parquet")
    assert network["time_s"].to_list() == [1.0, 2.0]


def test_traversal_rows_are_sorted_by_time_then_vehicle(tmp_path, recorder):
    # Every other per-step table's row order comes from a project-chosen key; this one
    # came from binding.vehicle.getIDList()'s container order instead. Deterministic on
    # both bindings today, but nothing pinned it to stay that way across a SUMO upgrade.
    run_recorder, topology = recorder
    identifier = next(iter(topology.movements))
    unsorted = dataclasses.replace(
        _state(1.0, topology),
        traversals=(
            Traversal(1.0, VehicleId("v9"), identifier, ConnectionId("a_0|b_0")),
            Traversal(1.0, VehicleId("v1"), identifier, ConnectionId("a_0|b_0")),
            Traversal(0.5, VehicleId("v5"), identifier, ConnectionId("a_0|b_0")),
        ),
    )
    run_recorder.record(unsorted, (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    traversal = pl.read_parquet(tmp_path / STATE_DIR / "traversal.parquet")
    assert traversal.select("time_s", "vehicle_id").rows() == [
        (0.5, "v5"),
        (1.0, "v1"),
        (1.0, "v9"),
    ]


def test_an_empty_table_still_declares_its_columns_and_types(tmp_path, recorder):
    # A run with no teleports must be readable by the same code as a run with some. Without
    # a declared schema polars writes a nought-column frame, and every downstream select
    # crashes on exactly the quiet runs.
    run_recorder, topology = recorder
    run_recorder.record(_state(1.0, topology), (), SimulationGroundTruth(1.0, ()))
    run_recorder.write()

    teleport = pl.read_parquet(tmp_path / STATE_DIR / "teleport.parquet")
    assert teleport.height == 0
    assert teleport.columns == ["time_s", "vehicle_id", "from_lane_id", "kind"]
    assert teleport.schema["time_s"] == pl.Float64
    assert teleport.schema["vehicle_id"] == pl.String


def test_as_row_keeps_fields_inherited_from_a_base_dataclass():
    # ST-D08 follow-up: a slotted dataclass's __slots__ holds only its own fields, so a
    # shared base class one layer up would have its fields silently missing from the
    # dict -- and from there, from the Parquet row -- if _as_row ever read __slots__ again.
    @dataclasses.dataclass(frozen=True, slots=True)
    class _Base:
        a: int

    @dataclasses.dataclass(frozen=True, slots=True)
    class _Child(_Base):
        b: str

    assert _as_row(_Child(1, "x")) == {"a": 1, "b": "x"}


def test_as_row_rejects_a_non_dataclass():
    with pytest.raises(TypeError, match="int"):
        _as_row(3)


def test_the_residual_row_keeps_a_null_rather_than_the_string_none(tmp_path, recorder):
    # ST-D19: the unattributed residual is a row whose next_edge_id is null. Rendering it as
    # "None" would make it indistinguishable from an edge literally named None, and every
    # conservation check would silently count it as attributed.
    run_recorder, topology = recorder
    run_recorder.record(
        _state(1.0, topology),
        (TeleportEvent(1.0, VehicleId("v9"), None, TeleportKind.STARTED),),
        SimulationGroundTruth(
            1.0,
            (
                LaneTurnCount(LaneId("a_0"), EdgeId("b"), 2, 1, 4.0),
                LaneTurnCount(LaneId("a_0"), None, 1, 0, 0.0),
            ),
        ),
    )
    run_recorder.write()

    lane_turn = pl.read_parquet(tmp_path / GROUND_TRUTH_DIR / "lane_turn.parquet")
    assert lane_turn["next_edge_id"].to_list() == ["b", None]
    teleport = pl.read_parquet(tmp_path / STATE_DIR / "teleport.parquet")
    assert teleport["from_lane_id"].to_list() == [None]


def _two_tls_topology() -> NetworkTopology:
    # ST-D?? follow-up: link_index is scoped to one TLS, so a fixture with a single
    # intersection cannot catch a dict keyed on link_index alone colliding across TLSes.
    lanes = {}
    connections = {}
    phases = []
    for intersection, in_edge, out_edge in (("A0", "a", "b"), ("B0", "c", "d")):
        from_lane = LaneInfo(LaneId(f"{in_edge}_0"), EdgeId(in_edge), 0, 100.0, 13.89)
        to_lane = LaneInfo(LaneId(f"{out_edge}_0"), EdgeId(out_edge), 0, 100.0, 13.89)
        lanes[from_lane.lane_id] = from_lane
        lanes[to_lane.lane_id] = to_lane
        connection = ConnectionInfo(
            connection_id=ConnectionId(f"{in_edge}_0|{out_edge}_0"),
            intersection_id=IntersectionId(intersection),
            link_index=0,
            from_lane_id=from_lane.lane_id,
            to_lane_id=to_lane.lane_id,
            via_lane_id=LaneId(f":{intersection}_0_0"),
            from_edge_id=EdgeId(in_edge),
            to_edge_id=EdgeId(out_edge),
            turn_direction=TurnDirection.STRAIGHT,
            movement_id=movement_id(EdgeId(in_edge), EdgeId(out_edge)),
        )
        connections[connection.connection_id] = connection
        phases.append(
            PhaseInfo(
                intersection_id=IntersectionId(intersection),
                program_id="0",
                phase_index=0,
                duration_s=42.0,
                min_duration_s=42.0,
                max_duration_s=42.0,
                signals=(SignalState.GREEN_PROTECTED,),
            )
        )
    return NetworkTopology(
        lanes=lanes,
        connections=connections,
        movements=build_movements(connections.values()),
        phases=tuple(phases),
    )


def test_tls_program_attributes_each_phase_to_its_own_intersection(tmp_path):
    topology = _two_tls_topology()
    run_recorder = RunRecorder(tmp_path, topology)
    run_recorder.write()

    program = pl.read_parquet(tmp_path / TOPOLOGY_DIR / "tls_program.parquet")
    assert program.height == 2
    by_intersection = dict(program.select("intersection_id", "connection_id").rows())
    assert by_intersection == {"A0": "a_0|b_0", "B0": "c_0|d_0"}
    assert set(program["intersection_id"]) == {"A0", "B0"}


def test_tripinfo_keeps_sumo_attribute_names_verbatim(tmp_path, recorder):
    run_recorder, _topology = recorder
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(_TRIPINFO_XML)
    run_recorder.write_tripinfo(tripinfo)

    table = pl.read_parquet(tmp_path / EVALUATION_DIR / "tripinfo.parquet")
    assert table.columns == ["id", "depart", "arrival", "duration", "waitingTime"]
    assert table["waitingTime"].to_list() == ["7.00"]


def test_an_empty_tripinfos_file_still_declares_its_columns(tmp_path, recorder):
    # A run that loads no vehicle must be readable by the same code as one that does,
    # the same failure test_an_empty_table_still_declares_its_columns_and_types exists
    # to prevent for every other table.
    run_recorder, _topology = recorder
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<tripinfos/>\n')
    run_recorder.write_tripinfo(tripinfo)

    table = pl.read_parquet(tmp_path / EVALUATION_DIR / "tripinfo.parquet")
    assert table.height == 0
    assert table.columns == [
        "id",
        "depart",
        "departLane",
        "departPos",
        "departSpeed",
        "departDelay",
        "arrival",
        "arrivalLane",
        "arrivalPos",
        "arrivalSpeed",
        "duration",
        "routeLength",
        "waitingTime",
        "waitingCount",
        "stopTime",
        "timeLoss",
        "rerouteNo",
        "devices",
        "vType",
        "speedFactor",
        "vaporized",
    ]


def test_an_attribute_appearing_only_in_the_last_row_is_kept(tmp_path, recorder):
    # polars infers a list-of-dict schema from the first infer_schema_length rows only;
    # an attribute that first shows up late in a long run must not be silently dropped.
    run_recorder, _topology = recorder
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tripinfos>\n"
        '    <tripinfo id="v0" depart="0.00" arrival="10.00"/>\n'
        '    <tripinfo id="v1" depart="1.00" arrival="11.00" rerouteNo="2"/>\n'
        "</tripinfos>\n"
    )
    run_recorder.write_tripinfo(tripinfo)

    table = pl.read_parquet(tmp_path / EVALUATION_DIR / "tripinfo.parquet")
    assert table.columns == ["id", "depart", "arrival", "rerouteNo"]
    assert table["rerouteNo"].to_list() == [None, "2"]
