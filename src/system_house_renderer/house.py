from __future__ import annotations

from collections import defaultdict
from typing import Any


ROLE_ORDER = [
    "entrance",
    "control_room",
    "thinking_room",
    "library",
    "workshop",
    "memory_room",
    "exit",
    "utility",
]

ROLE_POSITIONS = {
    "entrance": (60, 220),
    "control_room": (360, 80),
    "thinking_room": (660, 80),
    "library": (660, 340),
    "workshop": (960, 80),
    "memory_room": (960, 340),
    "exit": (1260, 220),
    "utility": (360, 340),
}

ROLE_NAMES_JA = {
    "entrance": "玄関",
    "control_room": "制御室",
    "thinking_room": "思考室",
    "library": "図書室",
    "workshop": "作業場",
    "memory_room": "記憶室",
    "exit": "出口",
    "utility": "設備室",
}

ROLE_NAMES_EN = {
    "entrance": "Entrance",
    "control_room": "Control Room",
    "thinking_room": "Thinking Room",
    "library": "Library",
    "workshop": "Workshop",
    "memory_room": "Memory Room",
    "exit": "Exit",
    "utility": "Utility Room",
}


def build_spatial_map(
    semantic_graph: dict[str, Any],
    runtime_metrics: dict[str, Any] | None,
    diagnostics: dict[str, list[dict[str, Any]]],
    *,
    language: str = "ja",
) -> dict[str, Any]:
    metrics = runtime_metrics if isinstance(runtime_metrics, dict) else {}
    active_nodes = set(metrics.get("activeNodeIds") or [])
    active_edges = set(metrics.get("activeEdgeIds") or [])
    node_metrics = metrics.get("nodeMetrics") if isinstance(metrics.get("nodeMetrics"), dict) else {}
    edge_metrics = metrics.get("edgeMetrics") if isinstance(metrics.get("edgeMetrics"), dict) else {}
    nodes_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in semantic_graph.get("nodes", []):
        role = role_for_kind(str(node.get("kind") or "unknown"))
        nodes_by_role[role].append(node)

    rooms: list[dict[str, Any]] = []
    node_room_map: dict[str, str] = {}
    for role in ROLE_ORDER:
        role_nodes = sorted(nodes_by_role.get(role, []), key=lambda item: item["id"])
        if not role_nodes:
            continue
        x, y = ROLE_POSITIONS[role]
        node_count = len(role_nodes)
        room_id = f"room_{role}"
        room_metrics = aggregate_node_metrics(role_nodes, node_metrics)
        signals = room_signals(role_nodes, room_metrics, active_nodes)
        rooms.append(
            {
                "id": room_id,
                "name": role_name(role, language),
                "role": role,
                "nodeIds": [node["id"] for node in role_nodes],
                "position": {"x": x, "y": y},
                "size": {
                    "width": max(220, min(360, 180 + node_count * 42)),
                    "height": max(150, min(300, 110 + node_count * 32)),
                },
                "status": status_from_signals(signals),
                "signals": signals,
                "metrics": room_metrics,
            }
        )
        for node in role_nodes:
            node_room_map[node["id"]] = room_id

    corridor_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in semantic_graph.get("edges", []):
        from_room = node_room_map.get(edge["from"])
        to_room = node_room_map.get(edge["to"])
        if not from_room or not to_room or from_room == to_room:
            continue
        key = (from_room, to_room)
        corridor_groups[key].append(edge["id"])

    corridors = []
    for index, ((from_room, to_room), edge_ids) in enumerate(sorted(corridor_groups.items())):
        corridor_metrics = aggregate_edge_metrics(edge_ids, edge_metrics)
        signals = corridor_signals(
            edge_ids,
            edge_metrics,
            active_edges,
            semantic_graph.get("edges", []),
        )
        status = status_from_signals(signals)
        visit_bonus = min(8, corridor_metrics.get("visitCount", 0))
        corridors.append(
            {
                "id": f"corridor_{index + 1}",
                "fromRoomId": from_room,
                "toRoomId": to_room,
                "edgeIds": sorted(edge_ids),
                "width": min(14, 2 + len(edge_ids) + visit_bonus),
                "status": status,
                "signals": signals,
                "metrics": corridor_metrics,
            }
        )

    landmarks = []
    for node in sorted(semantic_graph.get("nodes", []), key=lambda item: item["id"]):
        kind = str(node.get("kind") or "unknown")
        landmark_type = landmark_for_kind(kind)
        if landmark_type:
            landmarks.append(
                {
                    "id": f"landmark_{node['id']}",
                    "type": landmark_type,
                    "relatedNodeId": node["id"],
                    "roomId": node_room_map.get(node["id"]),
                }
            )
        if node.get("secretPresent"):
            landmarks.append(
                {
                    "id": f"landmark_{node['id']}_secret",
                    "type": "locked_box",
                    "relatedNodeId": node["id"],
                    "roomId": node_room_map.get(node["id"]),
                }
            )
        metrics_for_node = node_metrics.get(node["id"], {})
        if "high_cost" in metrics_for_node.get("signals", []):
            landmarks.append(
                {
                    "id": f"landmark_{node['id']}_cost",
                    "type": "cost_marker",
                    "relatedNodeId": node["id"],
                    "roomId": node_room_map.get(node["id"]),
                }
            )

    return {
        "rooms": rooms,
        "corridors": corridors,
        "landmarks": landmarks,
        "nodeRoomMap": node_room_map,
    }


def role_for_kind(kind: str) -> str:
    if kind == "input":
        return "entrance"
    if kind == "llm":
        return "thinking_room"
    if kind == "knowledge":
        return "library"
    if kind in {"tool", "external"}:
        return "workshop"
    if kind == "condition":
        return "control_room"
    if kind in {"memory", "variable"}:
        return "memory_room"
    if kind == "output":
        return "exit"
    return "utility"


def landmark_for_kind(kind: str) -> str | None:
    if kind in {"input", "output"}:
        return "door"
    if kind == "knowledge":
        return "bookshelf"
    if kind == "llm":
        return "model_console"
    if kind == "external":
        return "api_port"
    if kind == "tool":
        return "terminal"
    if kind in {"memory", "variable"}:
        return "locked_box"
    return None


def role_name(role: str, language: str) -> str:
    if language == "en":
        return ROLE_NAMES_EN.get(role, role)
    return ROLE_NAMES_JA.get(role, role)


def aggregate_node_metrics(
    nodes: list[dict[str, Any]],
    node_metrics: dict[str, Any],
) -> dict[str, Any]:
    aggregate = {
        "visitCount": 0,
        "latencyMs": None,
        "totalLatencyMs": 0.0,
        "cost": 0.0,
        "tokens": 0,
        "errorCount": 0,
        "signals": [],
    }
    signals: set[str] = set()
    for node in nodes:
        metrics = node_metrics.get(node["id"], {})
        aggregate["visitCount"] += int(metrics.get("visitCount") or 0)
        aggregate["totalLatencyMs"] += float(metrics.get("totalLatencyMs") or 0.0)
        aggregate["cost"] += float(metrics.get("cost") or 0.0)
        aggregate["tokens"] += int(metrics.get("tokens") or 0)
        aggregate["errorCount"] += int(metrics.get("errorCount") or 0)
        latency = metrics.get("latencyMs")
        if latency is not None:
            aggregate["latencyMs"] = max(float(aggregate["latencyMs"] or 0.0), float(latency))
        for signal in metrics.get("signals", []):
            signals.add(str(signal))
    aggregate["signals"] = sorted(signals)
    return aggregate


def aggregate_edge_metrics(
    edge_ids: list[str],
    edge_metrics: dict[str, Any],
) -> dict[str, Any]:
    aggregate = {
        "visitCount": 0,
        "latencyMs": None,
        "totalLatencyMs": 0.0,
        "cost": 0.0,
        "tokens": 0,
        "errorCount": 0,
        "signals": [],
    }
    signals: set[str] = set()
    for edge_id in edge_ids:
        metrics = edge_metrics.get(edge_id, {})
        aggregate["visitCount"] += int(metrics.get("visitCount") or 0)
        aggregate["totalLatencyMs"] += float(metrics.get("totalLatencyMs") or 0.0)
        aggregate["cost"] += float(metrics.get("cost") or 0.0)
        aggregate["tokens"] += int(metrics.get("tokens") or 0)
        aggregate["errorCount"] += int(metrics.get("errorCount") or 0)
        latency = metrics.get("latencyMs")
        if latency is not None:
            aggregate["latencyMs"] = max(float(aggregate["latencyMs"] or 0.0), float(latency))
        for signal in metrics.get("signals", []):
            signals.add(str(signal))
    aggregate["signals"] = sorted(signals)
    return aggregate


def room_signals(
    nodes: list[dict[str, Any]],
    room_metrics: dict[str, Any],
    active_nodes: set[str],
) -> list[str]:
    signals: set[str] = set()
    if any(node["id"] in active_nodes for node in nodes):
        signals.add("active")
    for node in nodes:
        if node.get("secretPresent"):
            signals.add("secret_present")
        if node.get("riskLevel") == "high":
            signals.add("high_risk")
        if node.get("kind") == "unknown":
            signals.add("unknown")
        if node.get("kind") == "external":
            signals.add("external_api")
    if room_metrics.get("errorCount", 0) > 0:
        signals.add("runtime_error")
    if room_metrics.get("latencyMs") is not None and room_metrics.get("latencyMs", 0) > 0:
        signals.add("has_latency")
    for signal in room_metrics.get("signals", []):
        signals.add(str(signal))
    return sorted(signals)


def corridor_signals(
    edge_ids: list[str],
    edge_metrics: dict[str, Any],
    active_edges: set[str],
    edges: list[dict[str, Any]],
) -> list[str]:
    edge_lookup = {edge["id"]: edge for edge in edges}
    signals: set[str] = set()
    if any(edge_id in active_edges for edge_id in edge_ids):
        signals.add("active")
    for edge_id in edge_ids:
        edge = edge_lookup.get(edge_id, {})
        metrics = edge_metrics.get(edge_id, {})
        if edge.get("kind") == "error" or metrics.get("errorCount", 0) > 0:
            signals.add("runtime_error")
        if edge.get("kind") == "external":
            signals.add("external_api")
        for signal in metrics.get("signals", []):
            signals.add(str(signal))
    return sorted(signals)


def status_from_signals(signals: list[str]) -> str:
    signal_set = set(signals)
    if "runtime_error" in signal_set:
        return "error"
    if signal_set.intersection(
        {"high_latency", "high_cost", "high_tokens", "secret_present", "high_risk", "unknown", "external_api"}
    ):
        return "warning"
    if "active" in signal_set:
        return "active"
    return "normal"


def active_node_ids(runtime: dict[str, Any]) -> set[str]:
    active: set[str] = set()
    events = []
    if isinstance(runtime.get("events"), list):
        events.extend(runtime["events"])
    if isinstance(runtime.get("traces"), list):
        events.extend(runtime["traces"])
    for event in events:
        if not isinstance(event, dict):
            continue
        node_id = (
            event.get("nodeId")
            or event.get("node_id")
            or event.get("componentId")
            or event.get("component_id")
            or event.get("id")
        )
        if node_id is not None:
            active.add(str(node_id))
    return active
