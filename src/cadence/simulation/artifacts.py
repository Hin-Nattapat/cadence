"""Writes a run directory that describes itself.

CONTRACT: the layout partitions along the same line as the type space. `state/` holds what
a controller could see; `ground_truth/` holds what it may not. An import ban does not
constrain a file read, so an offline dataset loader is bounded by this directory split
rather than by discipline (ST-D08).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

import polars as pl

from cadence.simulation.ground_truth import LaneTurnVehicleCount, SimulationGroundTruth
from cadence.simulation.state import CanonicalTrafficState, TeleportEvent
from cadence.simulation.topology import NetworkTopology

TOPOLOGY_DIR = "topology"
STATE_DIR = "state"
GROUND_TRUTH_DIR = "ground_truth"
# ST-D18: post-hoc per-trip data is not privileged -- no controller could see a trip that
# has ended. Filing it under ground_truth/ would force every metrics module into the
# privileged allowlist, and a partition the whole metrics package must read means nothing.
EVALUATION_DIR = "evaluation"

_SCHEMAS: dict[str, dict[str, type[pl.DataType]]] = {
    "topology/lane": {
        "lane_id": pl.String,
        "edge_id": pl.String,
        "lane_index": pl.Int64,
        "length_m": pl.Float64,
        "max_speed_mps": pl.Float64,
    },
    "topology/connection": {
        "connection_id": pl.String,
        "intersection_id": pl.String,
        "link_index": pl.Int64,
        "from_lane_id": pl.String,
        "to_lane_id": pl.String,
        "via_lane_id": pl.String,
        "from_edge_id": pl.String,
        "to_edge_id": pl.String,
        "turn_direction": pl.String,
        "movement_id": pl.String,
    },
    "topology/vehicle_type": {
        "type_id": pl.String,
        "length_m": pl.Float64,
        "min_gap_m": pl.Float64,
        "max_speed_mps": pl.Float64,
    },
    "topology/tls_program": {
        "intersection_id": pl.String,
        "program_id": pl.String,
        "phase_index": pl.Int64,
        "duration_s": pl.Float64,
        "min_duration_s": pl.Float64,
        "max_duration_s": pl.Float64,
        "connection_id": pl.String,
        "signal": pl.String,
    },
    "state/lane": {
        "time_s": pl.Float64,
        "lane_id": pl.String,
        "vehicle_count_veh": pl.Int64,
        "halting_count_veh": pl.Int64,
        "mean_speed_mps": pl.Float64,
        "occupancy_ratio": pl.Float64,
        "waiting_total_now_s": pl.Float64,
    },
    "state/intersection": {
        "time_s": pl.Float64,
        "intersection_id": pl.String,
        "program_id": pl.String,
        "phase_index": pl.Int64,
        "phase_elapsed_s": pl.Float64,
    },
    "state/signal": {"time_s": pl.Float64, "connection_id": pl.String, "signal": pl.String},
    "state/network": {
        "time_s": pl.Float64,
        "active_veh": pl.Int64,
        "pending_insertion_veh": pl.Int64,
        "departed_total_veh": pl.Int64,
        "arrived_total_veh": pl.Int64,
        "teleport_total_veh": pl.Int64,
    },
    "state/movement": {
        "time_s": pl.Float64,
        "movement_id": pl.String,
        "connection_id": pl.String,
        "signal": pl.String,
    },
    "state/traversal": {
        "time_s": pl.Float64,
        "vehicle_id": pl.String,
        "from_lane_id": pl.String,
        "movement_id": pl.String,
        "connection_id": pl.String,
    },
    "state/teleport": {
        "time_s": pl.Float64,
        "vehicle_id": pl.String,
        "from_lane_id": pl.String,
        "kind": pl.String,
    },
    "ground_truth/lane_turn": {
        "time_s": pl.Float64,
        "lane_id": pl.String,
        "next_edge_id": pl.String,
        "count_veh": pl.Int64,
        "halting_count_veh": pl.Int64,
        "waiting_total_now_s": pl.Float64,
    },
    "ground_truth/lane_turn_vehicle": {
        "lane_id": pl.String,
        "next_edge_id": pl.String,
        "distinct_veh": pl.Int64,
    },
}

# A floor for the case where a run loads no vehicle, not a filter on one that does: the
# attribute set SUMO 1.27.1 emits per <tripinfo> for s0_turning/v1, measured from a run
# rather than guessed, so the empty table still declares the columns a populated one has.
_EMPTY_TRIPINFO_COLUMNS = (
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
)


def _as_value(value: object) -> object:
    # None passes through as None. str(None) would write the four characters "None", and a
    # null that reads as a string is worse than no column at all: it looks attributed.
    if value is None or isinstance(value, int | float):
        return value
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _as_row(record: object) -> dict[str, object]:
    # dataclasses.fields(), not __slots__: a slotted dataclass with a slotted base class
    # holds only that class's own fields in __slots__, silently dropping inherited ones.
    # fields() walks the MRO and returns every field regardless, and dataclasses.is_dataclass
    # is a TypeGuard, so this narrows object without a type: ignore.
    if not dataclasses.is_dataclass(record):
        raise TypeError(f"expected a dataclass instance, got {type(record).__name__}")
    return {
        field.name: _as_value(getattr(record, field.name)) for field in dataclasses.fields(record)
    }


class RunRecorder:
    def __init__(self, run_dir: Path, topology: NetworkTopology) -> None:
        self._run_dir = run_dir
        self._topology = topology
        self._rows: dict[str, list[dict[str, object]]] = {name: [] for name in _SCHEMAS}

    def record(
        self,
        state: CanonicalTrafficState,
        teleports: Iterable[TeleportEvent],
        truth: SimulationGroundTruth,
    ) -> None:
        for lane in state.lanes.values():
            self._rows["state/lane"].append({"time_s": state.time_s, **_as_row(lane)})
        for intersection in state.intersections.values():
            self._rows["state/intersection"].append(
                {
                    "time_s": state.time_s,
                    "intersection_id": str(intersection.intersection_id),
                    "program_id": intersection.program_id,
                    "phase_index": intersection.phase_index,
                    "phase_elapsed_s": intersection.phase_elapsed_s,
                }
            )
            for connection in intersection.connections:
                self._rows["state/signal"].append(
                    {
                        "time_s": state.time_s,
                        "connection_id": str(connection.connection_id),
                        "signal": connection.signal.value,
                    }
                )
        self._rows["state/network"].append({"time_s": state.time_s, **_as_row(state.network)})
        for movement in state.movements.values():
            definition = state.topology.movements[movement.movement_id]
            for connection_id, signal in zip(
                definition.connection_ids, movement.signals, strict=True
            ):
                self._rows["state/movement"].append(
                    {
                        "time_s": state.time_s,
                        "movement_id": str(movement.movement_id),
                        "connection_id": str(connection_id),
                        "signal": signal.value,
                    }
                )
        for traversal in state.traversals:
            self._rows["state/traversal"].append(_as_row(traversal))
        for teleport in teleports:
            self._rows["state/teleport"].append(_as_row(teleport))
        for row in truth.lane_turns:
            self._rows["ground_truth/lane_turn"].append({"time_s": truth.time_s, **_as_row(row)})

    def record_distinct_vehicle_totals(self, totals: Iterable[LaneTurnVehicleCount]) -> None:
        """The whole-run cross-tab (ST-D31). Called once, after the run ends, not per step."""
        rows = self._rows["ground_truth/lane_turn_vehicle"]
        if rows:
            # Assignment would have made a second call discard the first silently, and the
            # only thing stopping one was a docstring.
            raise RuntimeError("distinct-vehicle totals are recorded once per run")
        rows.extend(_as_row(row) for row in totals)

    def write_tripinfo(self, tripinfo_xml: Path) -> None:
        """Convert SUMO's tripinfo XML into evaluation/tripinfo.parquet.

        One row per trip, every attribute SUMO emits kept as it is. Renaming or selecting
        here would be a metric definition, and metric definitions are versioned at M1b.
        """
        root = ElementTree.parse(tripinfo_xml).getroot()
        rows = [dict(element.attrib) for element in root.iter("tripinfo")]
        # polars infers a list-of-dict schema from only the first `infer_schema_length`
        # rows, so an attribute first appearing later in a long run would be dropped with
        # no error. The schema is built here from every row's keys instead, in the order
        # each first appears, so pl.DataFrame is never left to guess.
        columns: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)
        schema = {column: pl.String for column in (columns or _EMPTY_TRIPINFO_COLUMNS)}
        path = self._run_dir / EVALUATION_DIR / "tripinfo.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(rows, schema=schema).write_parquet(path)

    def write(self) -> None:
        self._rows["topology/lane"] = [_as_row(lane) for lane in self._topology.lanes.values()]
        self._rows["topology/connection"] = [
            _as_row(item) for item in self._topology.connections.values()
        ]
        self._rows["topology/vehicle_type"] = [
            _as_row(item) for item in self._topology.vehicle_types.values()
        ]
        # One row per phase per controlled connection: a phase's signals are positional
        # against the TLS lamp string, and a reader should not have to re-derive which
        # connection each position belongs to.
        # link_index is scoped to one TLS (topology_reader.py enumerates
        # getControlledLinks(tls_id) per TLS), so index 0 exists once per TLS. Keying on
        # link_index alone collapses every intersection's index 0 into one dict entry.
        by_index = {
            (connection.intersection_id, connection.link_index): connection.connection_id
            for connection in self._topology.connections.values()
        }
        self._rows["topology/tls_program"] = [
            {
                "intersection_id": str(phase.intersection_id),
                "program_id": phase.program_id,
                "phase_index": phase.phase_index,
                "duration_s": phase.duration_s,
                "min_duration_s": phase.min_duration_s,
                "max_duration_s": phase.max_duration_s,
                "connection_id": str(by_index[(phase.intersection_id, position)]),
                "signal": signal.value,
            }
            for phase in self._topology.phases
            for position, signal in enumerate(phase.signals)
            if (phase.intersection_id, position) in by_index
        ]
        # Every other per-step table's row order follows a project-chosen key
        # (lane id, intersection id, ...); this one followed binding.vehicle.getIDList()'s
        # container order instead. That order is deterministic on both bindings today, but
        # nothing pins it to stay that way across a SUMO upgrade.
        self._rows["state/traversal"].sort(key=lambda row: (row["time_s"], row["vehicle_id"]))
        for name, schema in _SCHEMAS.items():
            path = self._run_dir / f"{name}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pl.DataFrame(self._rows[name], schema=schema).write_parquet(path)
