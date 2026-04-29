from __future__ import annotations

from typing import Any


def build_render_scene(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
) -> dict[str, Any]:
    rooms_by_id = {room["id"]: room for room in spatial_map.get("rooms", [])}
    layers = [
        {"id": "floor", "type": "floor", "items": [{"id": "floor", "type": "rect", "x": 20, "y": 30, "width": 1540, "height": 560}]},
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
        x1, y1 = room_center(from_room)
        x2, y2 = room_center(to_room)
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
    return {"format": "svg-scene", "layers": layers, "interactions": interactions}


def room_center(room: dict[str, Any]) -> tuple[float, float]:
    position = room["position"]
    size = room["size"]
    return (
        float(position["x"]) + float(size["width"]) / 2,
        float(position["y"]) + float(size["height"]) / 2,
    )
