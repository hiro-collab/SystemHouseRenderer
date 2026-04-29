from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def build_tour(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
    runtime_metrics: dict[str, Any] | None,
    *,
    language: str = "ja",
) -> dict[str, Any]:
    metrics = runtime_metrics if isinstance(runtime_metrics, dict) else {}
    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    node_room_map = spatial_map.get("nodeRoomMap", {})
    order = [node_id for node_id in metrics.get("activeNodeIds", []) if node_id in node_lookup]
    if not order:
        order = topological_or_stable_order(semantic_graph)
    node_metrics = metrics.get("nodeMetrics") if isinstance(metrics.get("nodeMetrics"), dict) else {}

    system_name = semantic_graph.get("system", {}).get("name") or "System"
    steps = []
    for index, node_id in enumerate(order):
        node = node_lookup.get(node_id)
        if node is None:
            continue
        room_id = node_room_map.get(node_id)
        camera = camera_for_room(spatial_map, room_id)
        steps.append(
            {
                "id": f"step_{index + 1}",
                "focusRoomId": room_id,
                "focusNodeId": node_id,
                "camera": camera,
                "narration": narration_for_node(
                    node,
                    language,
                    metrics=node_metrics.get(node_id, {}),
                ),
                "highlightIds": [item for item in (room_id, node_id) if item],
            }
        )

    return {
        "title": f"{system_name} house tour" if language == "en" else f"{system_name} 館内ツアー",
        "steps": steps,
    }


def runtime_node_order(runtime: dict[str, Any], node_lookup: dict[str, dict[str, Any]]) -> list[str]:
    events = []
    for key in ("events", "traces", "steps"):
        if isinstance(runtime.get(key), list):
            events.extend(runtime[key])
    order: list[str] = []
    seen: set[str] = set()
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
        if node_id is None:
            continue
        text = str(node_id)
        if text in node_lookup and text not in seen:
            seen.add(text)
            order.append(text)
    return order


def topological_or_stable_order(semantic_graph: dict[str, Any]) -> list[str]:
    node_ids = sorted(node["id"] for node in semantic_graph.get("nodes", []))
    incoming_count = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in semantic_graph.get("edges", []):
        source = edge["from"]
        target = edge["to"]
        outgoing[source].append(target)
        incoming_count[target] = incoming_count.get(target, 0) + 1
    queue = deque(sorted(node_id for node_id, count in incoming_count.items() if count == 0))
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in sorted(outgoing.get(node_id, [])):
            incoming_count[target] -= 1
            if incoming_count[target] == 0:
                queue.append(target)
    remaining = [node_id for node_id in node_ids if node_id not in set(order)]
    return order + remaining


def narration_for_node(
    node: dict[str, Any],
    language: str,
    *,
    metrics: dict[str, Any] | None = None,
) -> str:
    label = node.get("label") or node.get("id")
    kind = node.get("kind") or "unknown"
    metrics_text = runtime_metrics_text(metrics or {}, language)
    if language == "en":
        role = {
            "input": "receives input",
            "llm": "performs model reasoning",
            "knowledge": "retrieves knowledge",
            "tool": "runs a tool or local service",
            "external": "connects to an external API",
            "condition": "routes the flow",
            "memory": "stores or reads state",
            "variable": "prepares variables",
            "output": "returns the result",
        }.get(kind, "needs manual review")
        return f"{label} {role}.{metrics_text}"
    role = {
        "input": "入力を受け取ります",
        "llm": "モデルによる推論を行います",
        "knowledge": "知識ベースを参照します",
        "tool": "ツールやローカル処理を実行します",
        "external": "外部APIや外部サービスへ接続します",
        "condition": "条件分岐や経路選択を行います",
        "memory": "状態や会話履歴を扱います",
        "variable": "変数や中間値を整えます",
        "output": "結果を返します",
    }.get(kind, "手動確認が必要な要素です")
    return f"「{label}」で{role}。{metrics_text}"


def runtime_metrics_text(metrics: dict[str, Any], language: str) -> str:
    if not metrics:
        return ""
    parts: list[str] = []
    if metrics.get("errorCount", 0):
        parts.append(f"errors={metrics['errorCount']}" if language == "en" else f"エラー{metrics['errorCount']}件")
    if metrics.get("latencyMs") is not None:
        parts.append(f"{float(metrics['latencyMs']):.0f}ms")
    if metrics.get("cost", 0):
        parts.append(f"cost={float(metrics['cost']):.4f}")
    if metrics.get("tokens", 0):
        parts.append(f"tokens={int(metrics['tokens'])}")
    if not parts:
        return ""
    joined = ", ".join(parts)
    return f" Runtime: {joined}." if language == "en" else f" 実行情報: {joined}。"


def camera_for_room(spatial_map: dict[str, Any], room_id: str | None) -> dict[str, float]:
    for room in spatial_map.get("rooms", []):
        if room.get("id") == room_id:
            position = room["position"]
            size = room["size"]
            return {
                "x": float(position["x"]) + float(size["width"]) / 2,
                "y": float(position["y"]) + float(size["height"]) / 2,
                "zoom": 1.2,
            }
    return {"x": 800, "y": 320, "zoom": 1}
