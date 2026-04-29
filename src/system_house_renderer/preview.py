from __future__ import annotations

from html import escape
from typing import Any


STATUS_COLORS = {
    "normal": "#637083",
    "active": "#2f9e44",
    "warning": "#b7791f",
    "error": "#c92a2a",
}

ROLE_COLORS = {
    "entrance": "#d8f3dc",
    "control_room": "#ffe8cc",
    "thinking_room": "#e7f5ff",
    "library": "#f3f0ff",
    "workshop": "#fff3bf",
    "memory_room": "#e6fcf5",
    "exit": "#d0ebff",
    "utility": "#f1f3f5",
}

LANDMARK_SYMBOLS = {
    "door": "D",
    "window": "W",
    "terminal": ">",
    "bookshelf": "B",
    "locked_box": "L",
    "model_console": "M",
    "api_port": "A",
    "cost_marker": "$",
    "security_marker": "S",
}


def build_preview_html(output: dict[str, Any]) -> str:
    semantic_graph = output["semanticGraph"]
    spatial_map = output["spatialMap"]
    tour = output["tour"]
    diagnostics = output["diagnostics"]
    svg = build_svg(semantic_graph, spatial_map)
    diagnostics_html = build_diagnostics_html(diagnostics)
    tour_html = build_tour_html(tour)
    system_name = escape(str(semantic_graph.get("system", {}).get("name") or "System"))
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{system_name} - SystemHouseRenderer</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, sans-serif; color: #172033; background: #f8fafc; }}
    header {{ padding: 18px 24px 10px; border-bottom: 1px solid #d8dee9; background: #ffffff; }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    main {{ display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 0; min-height: calc(100vh - 62px); }}
    .map {{ padding: 18px; overflow: auto; }}
    .side {{ border-left: 1px solid #d8dee9; background: #ffffff; padding: 18px; overflow: auto; }}
    h2 {{ font-size: 15px; margin: 0 0 10px; }}
    ol, ul {{ padding-left: 22px; }}
    li {{ margin: 8px 0; line-height: 1.45; }}
    .code {{ font-family: Consolas, monospace; font-size: 12px; color: #526071; }}
    svg {{ background: #ffffff; border: 1px solid #d8dee9; border-radius: 8px; min-width: 1160px; }}
    .room-label {{ font-size: 16px; font-weight: 700; fill: #172033; }}
    .node-label {{ font-size: 13px; fill: #263445; }}
    .legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: #526071; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; margin-right: 4px; vertical-align: -2px; border: 1px solid #96a0af; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns: 1fr; }} .side {{ border-left: 0; border-top: 1px solid #d8dee9; }} }}
  </style>
</head>
<body>
  <header><h1>{system_name}</h1></header>
  <main>
    <section class="map">
      {svg}
      <div class="legend">
        <span><span class="swatch" style="background:#2f9e44"></span>active</span>
        <span><span class="swatch" style="background:#b7791f"></span>warning</span>
        <span><span class="swatch" style="background:#c92a2a"></span>error</span>
        <span class="code">D door / B bookshelf / M model / A API / L locked / $ cost / S security</span>
      </div>
    </section>
    <aside class="side">
      {tour_html}
      {diagnostics_html}
    </aside>
  </main>
</body>
</html>
"""


def build_svg(semantic_graph: dict[str, Any], spatial_map: dict[str, Any]) -> str:
    rooms_by_id = {room["id"]: room for room in spatial_map.get("rooms", [])}
    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    parts = [
        '<svg viewBox="0 0 1580 620" width="100%" height="620" role="img" aria-label="system house map">',
        '<rect x="20" y="30" width="1540" height="560" fill="#fbfcfe" stroke="#ccd4df"/>',
    ]
    for corridor in spatial_map.get("corridors", []):
        from_room = rooms_by_id.get(corridor["fromRoomId"])
        to_room = rooms_by_id.get(corridor["toRoomId"])
        if not from_room or not to_room:
            continue
        x1, y1 = center(from_room)
        x2, y2 = center(to_room)
        color = STATUS_COLORS.get(corridor.get("status", "normal"), "#637083")
        width = int(corridor.get("width", 3))
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" opacity="0.72"/>'
        )
    for room in spatial_map.get("rooms", []):
        position = room["position"]
        size = room["size"]
        role = room.get("role", "utility")
        status = room.get("status", "normal")
        fill = ROLE_COLORS.get(role, "#f1f3f5")
        stroke = STATUS_COLORS.get(status, "#637083")
        parts.append(
            f'<rect x="{position["x"]}" y="{position["y"]}" width="{size["width"]}" '
            f'height="{size["height"]}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        parts.append(
            f'<text class="room-label" x="{position["x"] + 14}" y="{position["y"] + 26}">'
            f'{escape(str(room["name"]))}</text>'
        )
        for index, node_id in enumerate(room.get("nodeIds", [])):
            node = node_lookup.get(node_id, {"label": node_id, "kind": "unknown"})
            label = escape(str(node.get("label") or node_id))
            kind = escape(str(node.get("kind") or "unknown"))
            y = position["y"] + 58 + index * 24
            parts.append(
                f'<text class="node-label" x="{position["x"] + 18}" y="{y}">{label} '
                f'<tspan fill="#637083">({kind})</tspan></text>'
            )
    landmark_counts: dict[str, int] = {}
    for landmark in spatial_map.get("landmarks", []):
        room = rooms_by_id.get(landmark.get("roomId"))
        if not room:
            continue
        landmark_counts[room["id"]] = landmark_counts.get(room["id"], 0) + 1
        count = landmark_counts[room["id"]]
        position = room["position"]
        size = room["size"]
        x = position["x"] + size["width"] - 26
        y = position["y"] + 26 + (count - 1) * 24
        symbol = escape(LANDMARK_SYMBOLS.get(landmark.get("type"), "?"))
        parts.append(f'<circle cx="{x}" cy="{y}" r="9" fill="#ffffff" stroke="#526071"/>')
        parts.append(
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="11" '
            f'font-weight="700" fill="#263445">{symbol}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def build_tour_html(tour: dict[str, Any]) -> str:
    items = []
    for step in tour.get("steps", []):
        narration = escape(str(step.get("narration") or ""))
        focus = escape(str(step.get("focusNodeId") or ""))
        items.append(f'<li>{narration}<br><span class="code">{focus}</span></li>')
    return f"<h2>Tour</h2><ol>{''.join(items)}</ol>"


def build_diagnostics_html(diagnostics: dict[str, Any]) -> str:
    warnings = diagnostics.get("warnings", [])
    hidden = diagnostics.get("hiddenItems", [])
    warning_items = "".join(
        f'<li><span class="code">{escape(str(item.get("code")))}</span>: '
        f'{escape(str(item.get("message")))}</li>'
        for item in warnings
    )
    hidden_items = "".join(
        f'<li><span class="code">{escape(str(item.get("id")))}</span>: '
        f'{escape(str(item.get("reason")))}</li>'
        for item in hidden
    )
    if not warning_items:
        warning_items = "<li>No warnings.</li>"
    if not hidden_items:
        hidden_items = "<li>No hidden sensitive items.</li>"
    return f"<h2>Diagnostics</h2><ul>{warning_items}</ul><h2>Hidden Items</h2><ul>{hidden_items}</ul>"


def center(room: dict[str, Any]) -> tuple[float, float]:
    position = room["position"]
    size = room["size"]
    return (
        float(position["x"]) + float(size["width"]) / 2,
        float(position["y"]) + float(size["height"]) / 2,
    )
