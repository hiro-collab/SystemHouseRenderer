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
    contracts_html = build_contracts_html(semantic_graph)
    authority_html = build_authority_html(semantic_graph)
    states_html = build_states_html(semantic_graph)
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
    header {{ padding: 16px 24px 10px; border-bottom: 1px solid #d8dee9; background: #ffffff; }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    main {{ display: grid; grid-template-columns: minmax(0, 1fr) 480px; gap: 0; min-height: calc(100vh - 58px); }}
    .map {{ padding: 18px; overflow: auto; }}
    .side {{ border-left: 1px solid #d8dee9; background: #ffffff; padding: 16px; overflow: auto; }}
    h2 {{ font-size: 15px; margin: 0 0 10px; }}
    h3 {{ font-size: 13px; margin: 12px 0 6px; }}
    ol, ul {{ padding-left: 22px; }}
    li {{ margin: 7px 0; line-height: 1.45; }}
    details {{ border-top: 1px solid #e4e9f0; padding: 12px 0; }}
    details:first-child {{ border-top: 0; padding-top: 0; }}
    summary {{ cursor: pointer; font-weight: 700; font-size: 14px; }}
    .code {{ font-family: Consolas, monospace; font-size: 12px; color: #526071; }}
    .muted {{ color: #607085; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid #e4e9f0; border-radius: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; min-width: 560px; }}
    th, td {{ border-bottom: 1px solid #e9eef5; padding: 7px 8px; text-align: left; vertical-align: top; line-height: 1.35; }}
    th {{ background: #f5f7fb; color: #344256; font-size: 11px; text-transform: uppercase; letter-spacing: 0; }}
    tr:last-child td {{ border-bottom: 0; }}
    .badge {{ display: inline-block; margin: 0 4px 4px 0; padding: 2px 6px; border: 1px solid #c7d0dc; border-radius: 999px; background: #f8fafc; font-size: 11px; color: #344256; }}
    svg {{ background: #ffffff; border: 1px solid #d8dee9; border-radius: 8px; min-width: 1160px; }}
    .room-label {{ font-size: 16px; font-weight: 700; fill: #172033; }}
    .node-label {{ font-size: 13px; fill: #263445; }}
    .corridor-label {{ font-size: 11px; fill: #263445; font-weight: 650; }}
    .legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: #526071; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; margin-right: 4px; vertical-align: -2px; border: 1px solid #96a0af; }}
    @media (max-width: 1050px) {{ main {{ grid-template-columns: 1fr; }} .side {{ border-left: 0; border-top: 1px solid #d8dee9; }} }}
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
      <details open><summary>Communication Paths</summary>{contracts_html}</details>
      <details open><summary>Authority / Variables</summary>{authority_html}</details>
      <details open><summary>State Transitions</summary>{states_html}</details>
      <details><summary>Tour</summary>{tour_html}</details>
      <details><summary>Diagnostics</summary>{diagnostics_html}</details>
    </aside>
  </main>
</body>
</html>
"""


def build_svg(semantic_graph: dict[str, Any], spatial_map: dict[str, Any]) -> str:
    rooms_by_id = {room["id"]: room for room in spatial_map.get("rooms", [])}
    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    edge_lookup = {edge["id"]: edge for edge in semantic_graph.get("edges", [])}
    view_width, view_height = canvas_size(spatial_map)
    parts = [
        f'<svg viewBox="0 0 {view_width} {view_height}" width="100%" height="{view_height}" '
        f'style="min-width:{view_width}px" role="img" aria-label="system house map">',
        f'<rect x="22" y="26" width="{view_width - 44}" height="{view_height - 52}" '
        'rx="12" fill="#fbfcfe" stroke="#b6c0cf" stroke-width="3"/>',
        f'<rect x="40" y="44" width="{view_width - 80}" height="{view_height - 88}" '
        'fill="none" stroke="#d8dee9" stroke-width="1" stroke-dasharray="4 6"/>',
    ]
    door_parts: list[str] = []
    for corridor in spatial_map.get("corridors", []):
        from_room = rooms_by_id.get(corridor["fromRoomId"])
        to_room = rooms_by_id.get(corridor["toRoomId"])
        if not from_room or not to_room:
            continue
        x1, y1, x2, y2 = connection_points(from_room, to_room)
        color = STATUS_COLORS.get(corridor.get("status", "normal"), "#637083")
        width = int(corridor.get("width", 3))
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#e8edf5" stroke-width="{max(18, width + 12)}" '
            'stroke-linecap="round" opacity="0.96"/>'
        )
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" opacity="0.72"/>'
        )
        for door_x, door_y in ((x1, y1), (x2, y2)):
            door_parts.append(
                f'<circle cx="{door_x}" cy="{door_y}" r="6" fill="#ffffff" '
                'stroke="#526071" stroke-width="2"/>'
            )
        label = corridor_label(corridor, edge_lookup)
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            label_width = min(220, max(52, len(label) * 6 + 16))
            parts.append(
                f'<rect x="{mx - label_width / 2:.1f}" y="{my - 17:.1f}" width="{label_width}" '
                f'height="20" rx="5" fill="#ffffff" stroke="#d8dee9" opacity="0.94"/>'
            )
            parts.append(
                f'<text class="corridor-label" x="{mx:.1f}" y="{my - 3:.1f}" text-anchor="middle">'
                f'{escape(label)}</text>'
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
            f'height="{size["height"]}" rx="4" fill="{fill}" stroke="#3d4b5f" stroke-width="3"/>'
        )
        parts.append(
            f'<rect x="{position["x"] + 5}" y="{position["y"] + 5}" width="{size["width"] - 10}" '
            f'height="{size["height"] - 10}" rx="3" fill="none" stroke="{stroke}" '
            'stroke-width="2" opacity="0.8"/>'
        )
        parts.append(
            f'<text class="room-label" x="{position["x"] + 14}" y="{position["y"] + 27}">'
            f'{escape(truncate(str(room["name"]), 24))}</text>'
        )
        parts.append(
            f'<text x="{position["x"] + size["width"] - 14}" y="{position["y"] + 27}" '
            f'text-anchor="end" font-size="11" font-weight="700" fill="#526071">'
            f'{escape(str(room.get("roomNumber") or ""))}</text>'
        )
        parts.append(
            f'<text x="{position["x"] + 14}" y="{position["y"] + 48}" '
            f'font-size="11" fill="#526071">{escape(str(room.get("zoneName") or role))}</text>'
        )
        for index, node_id in enumerate(room.get("nodeIds", [])):
            node = node_lookup.get(node_id, {"label": node_id, "kind": "unknown"})
            if len(room.get("nodeIds", [])) == 1:
                label_text = str(node_id)
            else:
                label_text = str(node.get("label") or node_id)
            label = escape(truncate(label_text, 26))
            kind = escape(str(node.get("kind") or "unknown"))
            y = position["y"] + 76 + index * 22
            parts.append(
                f'<text class="node-label" x="{position["x"] + 18}" y="{y}">{label} '
                f'<tspan fill="#637083">({kind})</tspan></text>'
            )
    parts.extend(door_parts)
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


def build_contracts_html(semantic_graph: dict[str, Any]) -> str:
    nodes = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    rows = []
    for edge in semantic_graph.get("edges", []):
        source = node_label(nodes, edge.get("from"))
        target = node_label(nodes, edge.get("to"))
        channel = compact_join(
            edge.get("transport"),
            edge.get("protocol"),
            edge.get("channel"),
            edge.get("label"),
            edge.get("kind"),
        )
        rows.append(
            "<tr>"
            f"<td>{escape(source)}<br><span class=\"code\">{escape(str(edge.get('from') or ''))}</span></td>"
            f"<td>{escape(target)}<br><span class=\"code\">{escape(str(edge.get('to') or ''))}</span></td>"
            f"<td>{badge_list(channel)}</td>"
            f"<td>{metadata_cell(edge.get('endpoint'))}</td>"
            f"<td>{metadata_cell(edge.get('payload'))}</td>"
            f"<td>{metadata_cell(edge.get('auth'))}</td>"
            f"<td>{metadata_cell(edge.get('stateChanges'))}</td>"
            "</tr>"
        )
    if not rows:
        return '<p class="muted">No communication paths.</p>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>From</th><th>To</th><th>Channel</th><th>Endpoint</th>"
        "<th>Payload</th><th>Auth</th><th>State effect</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def build_authority_html(semantic_graph: dict[str, Any]) -> str:
    rows = []
    for variable in semantic_graph.get("variables", []):
        if not isinstance(variable, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{metadata_cell(variable.get('name') or variable.get('id'))}</td>"
            f"<td>{metadata_cell(variable.get('authority') or variable.get('sourceOfTruth') or variable.get('owner'))}</td>"
            f"<td>{metadata_cell(variable.get('writes') or variable.get('writer'))}</td>"
            f"<td>{metadata_cell(variable.get('reads') or variable.get('readers'))}</td>"
            f"<td>{metadata_cell(variable.get('storage') or variable.get('scope'))}</td>"
            "</tr>"
        )

    for node in semantic_graph.get("nodes", []):
        authority = node.get("authority")
        variables = node.get("variables")
        if is_blank(authority) and is_blank(variables):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(str(node.get('label') or node.get('id')))}<br><span class=\"code\">{escape(str(node.get('id') or ''))}</span></td>"
            f"<td>{metadata_cell(authority)}</td>"
            f"<td>{metadata_cell(metadata_pick(variables, 'writes'))}</td>"
            f"<td>{metadata_cell(metadata_pick(variables, 'reads'))}</td>"
            f"<td>{metadata_cell(metadata_pick(variables, 'scope') or metadata_pick(variables, 'storage'))}</td>"
            "</tr>"
        )

    if not rows:
        return '<p class="muted">No authority or variable metadata.</p>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Variable / Module</th><th>Authority</th><th>Writes</th><th>Reads</th><th>Storage</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def build_states_html(semantic_graph: dict[str, Any]) -> str:
    sections = []
    for machine in semantic_graph.get("stateMachines", []):
        if not isinstance(machine, dict):
            continue
        name = escape(str(machine.get("name") or machine.get("id") or "State machine"))
        transitions = machine.get("transitions") if isinstance(machine.get("transitions"), list) else []
        rows = []
        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{metadata_cell(transition.get('from'))}</td>"
                f"<td>{metadata_cell(transition.get('to'))}</td>"
                f"<td>{metadata_cell(transition.get('trigger') or transition.get('event'))}</td>"
                f"<td>{metadata_cell(transition.get('authority') or transition.get('guard'))}</td>"
                "</tr>"
            )
        if rows:
            sections.append(
                f"<h3>{name}</h3>"
                '<div class="table-wrap"><table><thead><tr>'
                "<th>From</th><th>To</th><th>Trigger</th><th>Authority / Guard</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></div>"
            )

    edge_rows = []
    nodes = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    for edge in semantic_graph.get("edges", []):
        changes = edge.get("stateChanges")
        if is_blank(changes):
            continue
        edge_rows.append(
            "<tr>"
            f"<td>{escape(node_label(nodes, edge.get('from')))} -> {escape(node_label(nodes, edge.get('to')))}</td>"
            f"<td>{metadata_cell(changes)}</td>"
            "</tr>"
        )
    if edge_rows:
        sections.append(
            "<h3>Flow state effects</h3>"
            '<div class="table-wrap"><table><thead><tr><th>Flow</th><th>Effect</th></tr></thead><tbody>'
            + "".join(edge_rows)
            + "</tbody></table></div>"
        )

    if not sections:
        return '<p class="muted">No state transition metadata.</p>'
    return "".join(sections)


def build_tour_html(tour: dict[str, Any]) -> str:
    items = []
    for step in tour.get("steps", []):
        narration = escape(str(step.get("narration") or ""))
        focus = escape(str(step.get("focusNodeId") or ""))
        items.append(f'<li>{narration}<br><span class="code">{focus}</span></li>')
    return f"<ol>{''.join(items)}</ol>"


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
    return f"<h3>Warnings</h3><ul>{warning_items}</ul><h3>Hidden Items</h3><ul>{hidden_items}</ul>"


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
    from_center = center(from_room)
    to_center = center(to_room)
    x1, y1 = boundary_point(from_room, to_center)
    x2, y2 = boundary_point(to_room, from_center)
    return (x1, y1, x2, y2)


def boundary_point(room: dict[str, Any], target: tuple[float, float]) -> tuple[float, float]:
    cx, cy = center(room)
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


def center(room: dict[str, Any]) -> tuple[float, float]:
    position = room["position"]
    size = room["size"]
    return (
        float(position["x"]) + float(size["width"]) / 2,
        float(position["y"]) + float(size["height"]) / 2,
    )


def corridor_label(corridor: dict[str, Any], edge_lookup: dict[str, dict[str, Any]]) -> str:
    labels: list[str] = []
    for edge_id in corridor.get("edgeIds", []):
        edge = edge_lookup.get(edge_id, {})
        label = compact_join(
            edge.get("transport"),
            edge.get("protocol"),
            edge.get("channel"),
            edge.get("label"),
            edge.get("kind"),
        )
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return ""
    if len(labels) == 1:
        return truncate(labels[0], 30)
    return truncate(f"{len(labels)} paths: {', '.join(labels[:2])}", 34)


def node_label(nodes: dict[str, dict[str, Any]], node_id: object) -> str:
    node = nodes.get(str(node_id or ""), {})
    return str(node.get("label") or node_id or "")


def compact_join(*values: object) -> str:
    parts = []
    for value in values:
        text = metadata_text(value)
        if text and text not in parts:
            parts.append(text)
    return " / ".join(parts)


def metadata_cell(value: Any) -> str:
    if is_blank(value):
        return '<span class="muted">-</span>'
    return escape(metadata_text(value))


def metadata_text(value: Any) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, dict):
        parts = []
        for key, nested in value.items():
            if is_blank(nested):
                continue
            parts.append(f"{key}: {metadata_text(nested)}")
        return "; ".join(parts)
    if isinstance(value, list):
        parts = [metadata_text(item) for item in value if not is_blank(item)]
        return ", ".join(part for part in parts if part)
    return str(value)


def badge_list(text: str) -> str:
    if not text:
        return '<span class="muted">-</span>'
    parts = [part.strip() for part in text.split("/") if part.strip()]
    return "".join(f'<span class="badge">{escape(part)}</span>' for part in parts)


def metadata_pick(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    if isinstance(value, list):
        matches = []
        for item in value:
            if isinstance(item, dict) and key in item:
                matches.append(item[key])
        return matches
    return None


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "..."
