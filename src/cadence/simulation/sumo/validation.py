"""Scenario network validation.

Covers defects that make a scenario unusable regardless of provenance. Checks specific to
OSM-derived networks arrive at M7, when there is a real imported network to fail against.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

# GOTCHA: importing sumo is what sets SUMO_HOME. sumolib tolerates it being unset, but
# `import sumo` first is the convention everywhere else in this codebase, for consistency.
import sumo  # noqa: F401
import sumolib

from cadence.simulation.scenario import ScenarioPaths


def _route_edge_ids(demand_path: str) -> set[str]:
    """Every edge the demand file names, however it names it.

    Declared routes cover S0, but generated demand often uses <trip> or <flow> with
    from/to/via instead, and a validator that only reads <route> would pass those blind.
    """
    root = ElementTree.parse(demand_path).getroot()
    edges: set[str] = set()
    for route in root.iter("route"):
        edges.update((route.get("edges") or "").split())
    for tag in ("flow", "trip"):
        for element in root.iter(tag):
            edges.update(value for value in (element.get("from"), element.get("to")) if value)
            edges.update((element.get("via") or "").split())
    return edges


def validate_network(paths: ScenarioPaths) -> list[str]:
    problems: list[str] = []
    net = sumolib.net.readNet(str(paths.network))

    signalised = [node for node in net.getNodes() if node.getType() == "traffic_light"]
    if not signalised:
        problems.append("network contains no signalised junction")

    for node in signalised:
        if not node.getIncoming():
            problems.append(f"signalised junction {node.getID()} has no incoming edge")
        if not node.getOutgoing():
            problems.append(f"signalised junction {node.getID()} has no outgoing edge")

    for edge in net.getEdges():
        # A stub ending at a dead end is the network boundary, not a defect. An edge that
        # arrives at a real junction with no permitted onward movement strands its traffic.
        if edge.getToNode().getType() != "dead_end" and not edge.getOutgoing():
            problems.append(
                f"edge {edge.getID()} arrives at junction "
                f"{edge.getToNode().getID()} with no onward movement"
            )

    known = {edge.getID() for edge in net.getEdges()}
    for edge_id in sorted(_route_edge_ids(str(paths.demand)) - known):
        problems.append(f"route references edge {edge_id}, which is not in the network")

    return problems
