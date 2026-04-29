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
    runtime: dict[str, Any] | None,
    diagnostics: dict[str, list[dict[str, Any]]],
    *,
    language: str = "ja",
) -> dict[str, Any]:
    active_nodes = active_node_ids(runtime or {})
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
                "status": "active"
                if any(node["id"] in active_nodes for node in role_nodes)
                else "normal",
            }
        )
        for node in role_nodes:
            node_room_map[node["id"]] = room_id

    corridor_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    corridor_status: dict[tuple[str, str], str] = {}
    for edge in semantic_graph.get("edges", []):
        from_room = node_room_map.get(edge["from"])
        to_room = node_room_map.get(edge["to"])
        if not from_room or not to_room or from_room == to_room:
            continue
        key = (from_room, to_room)
        corridor_groups[key].append(edge["id"])
        if edge["from"] in active_nodes and edge["to"] in active_nodes:
            corridor_status[key] = "active"
        elif edge["kind"] == "error":
            corridor_status[key] = "error"
        elif edge["kind"] == "external":
            corridor_status.setdefault(key, "warning")
        else:
            corridor_status.setdefault(key, "normal")

    corridors = []
    for index, ((from_room, to_room), edge_ids) in enumerate(sorted(corridor_groups.items())):
        status = corridor_status.get((from_room, to_room), "normal")
        corridors.append(
            {
                "id": f"corridor_{index + 1}",
                "fromRoomId": from_room,
                "toRoomId": to_room,
                "edgeIds": sorted(edge_ids),
                "width": min(12, 2 + len(edge_ids)),
                "status": status,
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
