from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from system_house_renderer.diagnostics import add_warning


def build_semantic_graph(
    topology: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    seen_node_ids: set[str] = set()
    nodes: list[dict[str, Any]] = []
    for component in topology.get("components", []):
        node_id = str(component.get("id") or "").strip()
        if not node_id:
            add_warning(diagnostics, "missing_component_id", "A component has no id.")
            continue
        if node_id in seen_node_ids:
            add_warning(
                diagnostics,
                "duplicate_component_id",
                f"Duplicate component id {node_id}; later entry was ignored.",
                related_id=node_id,
            )
            continue
        seen_node_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": str(component.get("label") or node_id),
                "kind": str(component.get("kind") or "unknown"),
                "summary": str(component.get("summary") or ""),
                "riskLevel": str(component.get("riskLevel") or "low"),
                "secretPresent": bool(component.get("secretPresent", False)),
                "authority": component.get("authority") or {},
                "variables": component.get("variables") or [],
                "state": component.get("state") or {},
            }
        )

    valid_ids = {node["id"] for node in nodes}
    seen_edge_ids: set[str] = set()
    pair_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    edges: list[dict[str, Any]] = []
    for index, flow in enumerate(topology.get("flows", [])):
        edge_id = str(flow.get("id") or f"edge_{index + 1}")
        if edge_id in seen_edge_ids:
            edge_id = f"{edge_id}_{index + 1}"
        seen_edge_ids.add(edge_id)
        source = str(flow.get("from") or "").strip()
        target = str(flow.get("to") or "").strip()
        if source not in valid_ids or target not in valid_ids:
            add_warning(
                diagnostics,
                "missing_flow_endpoint",
                f"Flow {edge_id} references a missing component.",
                related_id=edge_id,
            )
            continue
        if source == target:
            add_warning(
                diagnostics,
                "self_loop",
                f"Flow {edge_id} loops back to {source}.",
                related_id=edge_id,
            )
        edge_kind = str(flow.get("kind") or "control")
        pair_counts[(source, target, edge_kind)] += 1
        edges.append(
            {
                "id": edge_id,
                "from": source,
                "to": target,
                "kind": edge_kind,
                "label": str(flow.get("label") or ""),
                "transport": str(flow.get("transport") or ""),
                "protocol": str(flow.get("protocol") or ""),
                "channel": str(flow.get("channel") or ""),
                "endpoint": str(flow.get("endpoint") or ""),
                "payload": flow.get("payload") or {},
                "auth": flow.get("auth") or {},
                "authority": flow.get("authority") or {},
                "stateChanges": flow.get("stateChanges") or [],
                "secretPresent": bool(flow.get("secretPresent", False)),
            }
        )

    for (source, target, edge_kind), count in sorted(pair_counts.items()):
        if count > 1:
            add_warning(
                diagnostics,
                "duplicate_flow",
                f"{count} flows connect {source} to {target} as {edge_kind}.",
                related_id=source,
            )

    run_graph_checks(nodes, edges, topology.get("requirements") or {}, diagnostics)
    return {
        "system": dict(topology.get("system") or {}),
        "nodes": nodes,
        "edges": edges,
        "variables": topology.get("variables") or [],
        "stateMachines": topology.get("stateMachines") or [],
    }


def run_graph_checks(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    requirements: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    node_ids = {node["id"] for node in nodes}
    kinds = {node["kind"] for node in nodes}
    if nodes and "input" not in kinds:
        add_warning(diagnostics, "missing_input", "No input or entrance component was found.")
    if nodes and "output" not in kinds:
        add_warning(diagnostics, "missing_output", "No output or exit component was found.")

    degree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        degree[source] += 1
        degree[target] += 1
        outgoing[source].append(target)
        incoming[target].append(source)

    for node in nodes:
        node_id = node["id"]
        if degree[node_id] == 0 and node["kind"] not in {"input", "output"}:
            add_warning(
                diagnostics,
                "orphan_component",
                f"Component {node_id} is not connected to any flow.",
                related_id=node_id,
            )

    entrance_ids = sorted(node["id"] for node in nodes if node["kind"] == "input")
    if entrance_ids:
        reachable = reachable_from(entrance_ids, outgoing)
        for node in nodes:
            if node["id"] not in reachable:
                add_warning(
                    diagnostics,
                    "unreachable_component",
                    f"Component {node['id']} cannot be reached from an input.",
                    related_id=node["id"],
                )

    if has_cycle(node_ids, outgoing):
        add_warning(
            diagnostics,
            "cycle_detected",
            "The flow graph contains a cycle; tour order falls back to deterministic traversal.",
        )

    check_requirements(nodes, edges, requirements, diagnostics)


def reachable_from(start_ids: list[str], outgoing: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque(start_ids)
    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        for target in sorted(outgoing.get(node_id, [])):
            if target not in seen:
                queue.append(target)
    return seen


def has_cycle(node_ids: set[str], outgoing: dict[str, list[str]]) -> bool:
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in permanent:
            return False
        if node_id in temporary:
            return True
        temporary.add(node_id)
        for target in sorted(outgoing.get(node_id, [])):
            if visit(target):
                return True
        temporary.remove(node_id)
        permanent.add(node_id)
        return False

    return any(visit(node_id) for node_id in sorted(node_ids))


def check_requirements(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    requirements: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    if not isinstance(requirements, dict):
        return
    ids = {node["id"] for node in nodes}
    kinds = {node["kind"] for node in nodes}
    for kind in requirements.get("requiredComponentKinds", []) or []:
        if kind not in kinds:
            add_warning(
                diagnostics,
                "requirement_missing_kind",
                f"Required component kind {kind!r} was not found.",
            )
    for component in requirements.get("requiredComponents", []) or []:
        if isinstance(component, dict):
            component_id = str(component.get("id") or "").strip()
            if component_id and component_id not in ids:
                add_warning(
                    diagnostics,
                    "requirement_missing_component",
                    f"Required component {component_id} was not found.",
                    related_id=component_id,
                )
    edge_pairs = {(edge["from"], edge["to"]) for edge in edges}
    for flow in requirements.get("requiredFlows", []) or []:
        if not isinstance(flow, dict):
            continue
        source = str(flow.get("from") or "").strip()
        target = str(flow.get("to") or "").strip()
        if source and target and (source, target) not in edge_pairs:
            add_warning(
                diagnostics,
                "requirement_missing_flow",
                f"Required flow {source} -> {target} was not found.",
                related_id=source,
            )
    for kind in requirements.get("forbiddenKinds", []) or []:
        if kind in kinds:
            add_warning(
                diagnostics,
                "requirement_forbidden_kind",
                f"Forbidden component kind {kind!r} is present.",
            )
