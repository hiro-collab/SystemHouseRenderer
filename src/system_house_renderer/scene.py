from __future__ import annotations

from typing import Any


def build_render_scene(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
) -> dict[str, Any]:
    rooms_by_id = {room["id"]: room for room in spatial_map.get("rooms", [])}
    canvas_width, canvas_height = canvas_size(spatial_map)
    layers = [
        {
            "id": "floor",
            "type": "floor",
            "items": [
                {
                    "id": "floor",
                    "type": "rect",
                    "x": 22,
                    "y": 26,
                    "width": canvas_width - 44,
                    "height": canvas_height - 52,
                }
            ],
        },
        {"id": "corridors", "type": "corridor", "items": []},
        {"id": "rooms", "type": "room", "items": []},
        {"id": "icons", "type": "icon", "items": []},
        {"id": "labels", "type": "label", "items": []},
        {"id": "overlays", "type": "overlay", "items": []},
    ]
    layer_map = {layer["id"]: layer for layer in layers}

    for corridor in spatial_map.get("corridors", []):
        from_room = rooms_by_id.get(corridor["fromRoomId"])
        to_room = rooms_by_id.get(corridor["toRoomId"])
        if not from_room or not to_room:
            continue
        x1, y1, x2, y2 = connection_points(from_room, to_room)
        layer_map["corridors"]["items"].append(
            {
                "id": corridor["id"],
                "type": "line",
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": corridor.get("width", 2),
                "status": corridor.get("status", "normal"),
                "signals": list(corridor.get("signals", [])),
                "metrics": dict(corridor.get("metrics", {})),
            }
        )

    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    for room in spatial_map.get("rooms", []):
        position = room["position"]
        size = room["size"]
        layer_map["rooms"]["items"].append(
            {
                "id": room["id"],
                "type": "rect",
                "x": position["x"],
                "y": position["y"],
                "width": size["width"],
                "height": size["height"],
                "role": room["role"],
                "status": room.get("status", "normal"),
                "signals": list(room.get("signals", [])),
                "metrics": dict(room.get("metrics", {})),
                "roomNumber": room.get("roomNumber", ""),
                "zoneName": room.get("zoneName", ""),
            }
        )
        layer_map["labels"]["items"].append(
            {
                "id": f"{room['id']}_label",
                "type": "text",
                "x": position["x"] + 14,
                "y": position["y"] + 24,
                "text": room["name"],
                "targetId": room["id"],
            }
        )
        for index, node_id in enumerate(room.get("nodeIds", [])):
            node = node_lookup.get(node_id, {"label": node_id})
            layer_map["labels"]["items"].append(
                {
                    "id": f"label_{node_id}",
                    "type": "text",
                    "x": position["x"] + 18,
                    "y": position["y"] + 56 + index * 24,
                    "text": str(node.get("label") or node_id),
                    "targetId": node_id,
                }
            )

    for index, landmark in enumerate(spatial_map.get("landmarks", [])):
        room = rooms_by_id.get(landmark.get("roomId"))
        if not room:
            continue
        position = room["position"]
        size = room["size"]
        layer_map["icons"]["items"].append(
            {
                "id": landmark["id"],
                "type": "landmark",
                "landmarkType": landmark["type"],
                "x": position["x"] + size["width"] - 26,
                "y": position["y"] + 28 + (index % 4) * 24,
                "targetId": landmark.get("relatedNodeId"),
            }
        )

    interactions = []
    for node in semantic_graph.get("nodes", []):
        interactions.append(
            {
                "targetId": node["id"],
                "onClick": "openDetail",
                "tooltip": f"{node['label']} ({node['kind']})",
            }
        )
    for room in spatial_map.get("rooms", []):
        interactions.append(
            {
                "targetId": room["id"],
                "onClick": "focusNode",
                "tooltip": room["name"],
            }
        )
    return {
        "format": "svg-scene",
        "canvas": {"width": canvas_width, "height": canvas_height},
        "layers": layers,
        "interactions": interactions,
    }


def canvas_size(spatial_map: dict[str, Any]) -> tuple[int, int]:
    rooms = spatial_map.get("rooms", [])
    if not rooms:
        return (1580, 620)
    max_x = max(
        int(room["position"]["x"]) + int(room["size"]["width"])
        for room in rooms
    )
    max_y = max(
        int(room["position"]["y"]) + int(room["size"]["height"])
        for room in rooms
    )
    return (max(1160, max_x + 80), max(620, max_y + 80))


def connection_points(
    from_room: dict[str, Any],
    to_room: dict[str, Any],
) -> tuple[float, float, float, float]:
    from_center = room_center(from_room)
    to_center = room_center(to_room)
    x1, y1 = boundary_point(from_room, to_center)
    x2, y2 = boundary_point(to_room, from_center)
    return (x1, y1, x2, y2)


def boundary_point(room: dict[str, Any], target: tuple[float, float]) -> tuple[float, float]:
    cx, cy = room_center(room)
    tx, ty = target
    dx = tx - cx
    dy = ty - cy
    position = room["position"]
    size = room["size"]
    half_width = float(size["width"]) / 2
    half_height = float(size["height"]) / 2
    if dx == 0 and dy == 0:
        return (cx, cy)
    scale_x = half_width / abs(dx) if dx else float("inf")
    scale_y = half_height / abs(dy) if dy else float("inf")
    scale = min(scale_x, scale_y)
    x = cx + dx * scale
    y = cy + dy * scale
    return (
        max(float(position["x"]), min(float(position["x"]) + float(size["width"]), x)),
        max(float(position["y"]), min(float(position["y"]) + float(size["height"]), y)),
    )


def room_center(room: dict[str, Any]) -> tuple[float, float]:
    position = room["position"]
    size = room["size"]
    return (
        float(position["x"]) + float(size["width"]) / 2,
        float(position["y"]) + float(size["height"]) / 2,
    )
