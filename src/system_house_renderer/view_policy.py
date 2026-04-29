from __future__ import annotations

from typing import Any

from system_house_renderer.diagnostics import add_warning
from system_house_renderer.house import status_from_signals


VALID_MODES = {"overview", "tour", "debug", "cost", "security"}
VALID_DETAIL_LEVELS = {"simple", "normal", "deep"}


def normalize_view_options(view_options: dict[str, Any] | None) -> dict[str, Any]:
    options = {
        "mode": "overview",
        "metaphor": "house",
        "detailLevel": "normal",
        "language": "ja",
    }
    if view_options:
        options.update({key: value for key, value in view_options.items() if value is not None})
    if options["mode"] not in VALID_MODES:
        options["mode"] = "overview"
    if options["detailLevel"] not in VALID_DETAIL_LEVELS:
        options["detailLevel"] = "normal"
    if options["language"] not in {"ja", "en"}:
        options["language"] = "ja"
    return options


def apply_view_policy(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
    runtime_metrics: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
    options: dict[str, Any],
) -> None:
    mode = str(options.get("mode") or "overview")
    detail_level = str(options.get("detailLevel") or "normal")
    spatial_map["view"] = {
        "mode": mode,
        "detailLevel": detail_level,
        "appliedPolicies": [],
    }

    if mode == "security":
        apply_security_mode(semantic_graph, spatial_map, diagnostics)
    elif mode == "cost":
        apply_cost_mode(spatial_map)
    elif mode == "debug":
        apply_debug_mode(spatial_map, diagnostics)
    elif mode == "tour":
        apply_tour_mode(spatial_map)

    apply_detail_level(semantic_graph, spatial_map, runtime_metrics, detail_level)


def apply_security_mode(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    spatial_map["view"]["appliedPolicies"].append("security")
    for room in spatial_map.get("rooms", []):
        signals = set(room.get("signals") or [])
        for node_id in room.get("nodeIds", []):
            node = node_lookup.get(node_id, {})
            if node.get("secretPresent") or node.get("riskLevel") == "high":
                signals.add("security_focus")
                signals.add("high_risk")
            if node.get("kind") == "external":
                signals.add("security_focus")
                signals.add("external_api")
                add_warning(
                    diagnostics,
                    "security_external_component",
                    f"External component {node_id} is highlighted in security mode.",
                    related_id=node_id,
                )
            if node.get("kind") == "unknown":
                signals.add("security_focus")
                signals.add("unknown")
        room["signals"] = sorted(signals)
        room["status"] = status_from_signals(room["signals"])

    existing = {landmark["id"] for landmark in spatial_map.get("landmarks", [])}
    for room in spatial_map.get("rooms", []):
        if "security_focus" not in room.get("signals", []):
            continue
        landmark_id = f"landmark_{room['id']}_security"
        if landmark_id in existing:
            continue
        spatial_map["landmarks"].append(
            {
                "id": landmark_id,
                "type": "security_marker",
                "roomId": room["id"],
            }
        )
        existing.add(landmark_id)


def apply_cost_mode(spatial_map: dict[str, Any]) -> None:
    spatial_map["view"]["appliedPolicies"].append("cost")
    for room in spatial_map.get("rooms", []):
        metrics = room.get("metrics") or {}
        signals = set(room.get("signals") or [])
        if float(metrics.get("cost") or 0.0) > 0:
            signals.add("cost_visible")
        room["signals"] = sorted(signals)
        room["status"] = status_from_signals(room["signals"])


def apply_debug_mode(
    spatial_map: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    spatial_map["view"]["appliedPolicies"].append("debug")
    related_ids = {
        str(warning.get("relatedId"))
        for warning in diagnostics.get("warnings", [])
        if warning.get("relatedId")
    }
    for room in spatial_map.get("rooms", []):
        if not related_ids.intersection(set(room.get("nodeIds", []))):
            continue
        signals = set(room.get("signals") or [])
        signals.add("debug_focus")
        room["signals"] = sorted(signals)
        room["status"] = status_from_signals(room["signals"])


def apply_tour_mode(spatial_map: dict[str, Any]) -> None:
    spatial_map["view"]["appliedPolicies"].append("tour")
    for room in spatial_map.get("rooms", []):
        if room.get("status") != "active":
            continue
        signals = set(room.get("signals") or [])
        signals.add("tour_focus")
        room["signals"] = sorted(signals)


def apply_detail_level(
    semantic_graph: dict[str, Any],
    spatial_map: dict[str, Any],
    runtime_metrics: dict[str, Any],
    detail_level: str,
) -> None:
    node_lookup = {node["id"]: node for node in semantic_graph.get("nodes", [])}
    node_metrics = runtime_metrics.get("nodeMetrics") if isinstance(runtime_metrics.get("nodeMetrics"), dict) else {}
    spatial_map["view"]["appliedPolicies"].append(f"detail:{detail_level}")

    for room in spatial_map.get("rooms", []):
        room["detailLevel"] = detail_level
        if detail_level == "simple":
            room["summary"] = f"{len(room.get('nodeIds', []))} component(s)"
            room.pop("nodeDetails", None)
        elif detail_level == "deep":
            room["nodeDetails"] = [
                {
                    "id": node_id,
                    "label": node_lookup.get(node_id, {}).get("label", node_id),
                    "kind": node_lookup.get(node_id, {}).get("kind", "unknown"),
                    "riskLevel": node_lookup.get(node_id, {}).get("riskLevel", "low"),
                    "metrics": node_metrics.get(node_id, {}),
                }
                for node_id in room.get("nodeIds", [])
            ]
        else:
            room.pop("nodeDetails", None)
