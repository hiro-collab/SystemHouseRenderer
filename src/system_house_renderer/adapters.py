from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from system_house_renderer.diagnostics import add_warning
from system_house_renderer.sanitizer import (
    is_secret_key,
    register_secret_findings,
    sanitize_summary,
)


SEMANTIC_KINDS = {
    "input",
    "llm",
    "knowledge",
    "tool",
    "condition",
    "memory",
    "output",
    "variable",
    "external",
    "unknown",
}


def normalize_payload_to_topology(
    payload: Any,
    diagnostics: dict[str, list[dict[str, Any]]],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON/YAML object")

    if "components" in payload or "flows" in payload:
        return normalize_generic_topology(payload, diagnostics, source_path=source_path)

    graph = find_graph_payload(payload)
    if graph is not None:
        return normalize_dify_export(payload, graph, diagnostics, source_path=source_path)

    raise ValueError(
        "input does not look like a generic topology or Dify workflow export"
    )


def normalize_generic_topology(
    payload: Mapping[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    system = _system_payload(payload, source_path=source_path, source_type="generic")
    components = []
    for index, item in enumerate(_list(payload.get("components"))):
        if not isinstance(item, Mapping):
            add_warning(
                diagnostics,
                "invalid_component",
                f"Component at index {index} is not an object.",
            )
            continue
        component_id = _component_id(item, fallback=f"component_{index + 1}")
        raw_kind = item.get("kind") or item.get("type") or item.get("componentType")
        kind = normalize_kind(raw_kind, label=_label(item, component_id))
        if kind == "unknown":
            add_warning(
                diagnostics,
                "unknown_component_kind",
                f"Component {component_id} has unknown kind {raw_kind!r}.",
                related_id=component_id,
            )
        secret_present = register_secret_findings(
            diagnostics,
            item,
            owner_id=component_id,
        )
        components.append(
            {
                "id": component_id,
                "label": _label(item, component_id),
                "kind": kind,
                "summary": sanitize_summary(
                    item.get("summary")
                    or item.get("description")
                    or item.get("detail")
                    or ""
                ),
                "riskLevel": infer_risk_level(kind, secret_present),
                "secretPresent": secret_present,
                "authority": sanitize_metadata(item.get("authority") or {}),
                "variables": sanitize_metadata(item.get("variables") or []),
                "state": sanitize_metadata(item.get("state") or {}),
            }
        )

    flows = []
    for index, item in enumerate(_list(payload.get("flows") or payload.get("edges"))):
        if not isinstance(item, Mapping):
            add_warning(
                diagnostics,
                "invalid_flow",
                f"Flow at index {index} is not an object.",
            )
            continue
        source = str(item.get("from") or item.get("source") or "").strip()
        target = str(item.get("to") or item.get("target") or "").strip()
        flow_id = str(item.get("id") or f"flow_{index + 1}").strip()
        secret_present = register_secret_findings(
            diagnostics,
            item,
            owner_id=flow_id,
        )
        flows.append(
            {
                "id": flow_id,
                "from": source,
                "to": target,
                "kind": normalize_edge_kind(item.get("kind") or item.get("type")),
                "label": sanitize_summary(item.get("label") or item.get("name") or ""),
                "transport": sanitize_summary(item.get("transport") or ""),
                "protocol": sanitize_summary(item.get("protocol") or ""),
                "channel": sanitize_summary(item.get("channel") or ""),
                "endpoint": sanitize_summary(item.get("endpoint") or "", max_chars=240),
                "payload": sanitize_metadata(item.get("payload") or {}),
                "auth": sanitize_metadata(item.get("auth") or {}),
                "authority": sanitize_metadata(item.get("authority") or {}),
                "stateChanges": sanitize_metadata(item.get("stateChanges") or []),
                "secretPresent": secret_present,
            }
        )

    return {
        "system": system,
        "components": components,
        "flows": flows,
        "resources": _list(payload.get("resources")),
        "variables": sanitize_metadata(payload.get("variables") or []),
        "stateMachines": sanitize_metadata(payload.get("stateMachines") or []),
        "runtime": payload.get("runtime") if isinstance(payload.get("runtime"), Mapping) else {},
        "requirements": (
            payload.get("requirements")
            if isinstance(payload.get("requirements"), Mapping)
            else {}
        ),
    }


def normalize_dify_export(
    root_payload: Mapping[str, Any],
    graph: Mapping[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    system = _system_payload(root_payload, source_path=source_path, source_type="dify")
    components = []
    for index, node in enumerate(_list(graph.get("nodes"))):
        if not isinstance(node, Mapping):
            add_warning(
                diagnostics,
                "invalid_dify_node",
                f"Dify node at index {index} is not an object.",
            )
            continue
        node_data = node.get("data") if isinstance(node.get("data"), Mapping) else {}
        node_id = _component_id(node, fallback=f"node_{index + 1}")
        label = _label(node_data, "") or _label(node, node_id)
        raw_kind = (
            node_data.get("type")
            or node.get("type")
            or node_data.get("node_type")
            or node_data.get("provider_type")
        )
        kind = normalize_kind(raw_kind, label=label)
        if kind == "unknown":
            add_warning(
                diagnostics,
                "unknown_component_kind",
                f"Dify node {node_id} has unknown type {raw_kind!r}.",
                related_id=node_id,
            )
        secret_present = register_secret_findings(
            diagnostics,
            node,
            owner_id=node_id,
        )
        metadata = dify_component_metadata(node_data)
        components.append(
            {
                "id": node_id,
                "label": label,
                "kind": kind,
                "summary": dify_node_summary(node, node_data),
                "riskLevel": infer_risk_level(kind, secret_present),
                "secretPresent": secret_present,
                "authority": metadata.get("authority", {}),
                "variables": metadata.get("variables", []),
                "state": metadata.get("state", {}),
            }
        )

    flows = []
    for index, edge in enumerate(_list(graph.get("edges"))):
        if not isinstance(edge, Mapping):
            add_warning(
                diagnostics,
                "invalid_dify_edge",
                f"Dify edge at index {index} is not an object.",
            )
            continue
        source = str(edge.get("source") or edge.get("from") or "").strip()
        target = str(edge.get("target") or edge.get("to") or "").strip()
        edge_id = str(edge.get("id") or f"edge_{index + 1}").strip()
        edge_data = edge.get("data") if isinstance(edge.get("data"), Mapping) else {}
        edge_kind = normalize_edge_kind(
            edge.get("kind")
            or edge.get("type")
            or edge.get("sourceHandle")
            or edge.get("source_handle")
        )
        flows.append(
            {
                "id": edge_id,
                "from": source,
                "to": target,
                "kind": edge_kind,
                "label": sanitize_summary(
                    edge.get("label")
                    or edge.get("sourceHandle")
                    or edge.get("source_handle")
                    or ""
                ),
                "transport": "",
                "protocol": "",
                "channel": sanitize_summary(edge.get("sourceHandle") or ""),
                "endpoint": "",
                "payload": sanitize_metadata(
                    {
                        "sourceType": edge_data.get("sourceType"),
                        "targetType": edge_data.get("targetType"),
                    }
                ),
                "auth": {},
                "authority": {},
                "stateChanges": [],
                "secretPresent": False,
            }
        )

    runtime = {}
    for key in ("runtime", "execution", "trace", "traces"):
        if key in root_payload:
            runtime = normalize_runtime(root_payload.get(key))
            break

    requirements = (
        root_payload.get("requirements")
        if isinstance(root_payload.get("requirements"), Mapping)
        else {}
    )
    return {
        "system": system,
        "components": components,
        "flows": flows,
        "resources": [],
        "variables": [],
        "stateMachines": [],
        "runtime": runtime,
        "requirements": requirements,
    }


def find_graph_payload(payload: Any) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    for path in (
        ("graph",),
        ("workflow", "graph"),
        ("app", "workflow", "graph"),
        ("workflow",),
    ):
        current: Any = payload
        for key in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(key)
        if isinstance(current, Mapping) and _looks_like_graph(current):
            return current
    return find_nested_graph(payload)


def find_nested_graph(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        if _looks_like_graph(value):
            return value
        for nested in value.values():
            result = find_nested_graph(nested)
            if result is not None:
                return result
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            result = find_nested_graph(nested)
            if result is not None:
                return result
    return None


def _looks_like_graph(value: Mapping[str, Any]) -> bool:
    return isinstance(value.get("nodes"), list) and isinstance(value.get("edges"), list)


def normalize_kind(raw_kind: object, *, label: str = "") -> str:
    raw_text = str(raw_kind or "").strip().lower().replace("_", "-")
    if raw_text in {"start", "input", "webhook", "trigger"}:
        return "input"
    if raw_text in {"end", "answer", "output", "response"}:
        return "output"
    if raw_text in {"llm", "model", "agent", "chat"}:
        return "llm"
    if raw_text in {"knowledge", "knowledge-retrieval", "retrieval", "dataset", "rag", "document"}:
        return "knowledge"
    if raw_text in {"if-else", "condition", "router", "branch", "classifier", "question-classifier"}:
        return "condition"
    if raw_text in {"memory", "conversation"}:
        return "memory"
    if raw_text in {"variable", "assign", "assigner", "parameter", "template"}:
        return "variable"
    if raw_text in {"http", "http-request", "api", "external", "integration", "web-api"}:
        return "external"
    if raw_text in {"tool", "code", "function", "worker", "service", "tts"}:
        return "tool"
    if raw_text in SEMANTIC_KINDS:
        return raw_text

    text = f"{raw_text} {label}".lower().replace("_", "-")
    if any(token in text for token in ("start", "input", "webhook", "trigger")):
        return "input"
    if any(token in text for token in ("end", "answer", "output", "response")):
        return "output"
    if any(token in text for token in ("llm", "model", "agent", "chat")):
        return "llm"
    if any(token in text for token in ("knowledge", "retrieval", "dataset", "rag", "document")):
        return "knowledge"
    if any(token in text for token in ("if-else", "condition", "router", "branch", "classifier")):
        return "condition"
    if any(token in text for token in ("memory", "conversation")):
        return "memory"
    if any(token in text for token in ("variable", "assign", "parameter", "template")):
        return "variable"
    if any(token in text for token in ("http", "api", "external", "integration", "web-api")):
        return "external"
    if any(token in text for token in ("tool", "code", "function", "worker", "service", "tts")):
        return "tool"
    return "unknown"


def normalize_edge_kind(raw_kind: object) -> str:
    text = str(raw_kind or "").lower().replace("_", "-")
    if "error" in text or "fail" in text:
        return "error"
    if "external" in text or "api" in text or "http" in text:
        return "external"
    if "data" in text or "value" in text or "source" in text:
        return "data"
    return "control"


def infer_risk_level(kind: str, secret_present: bool) -> str:
    if secret_present:
        return "high"
    if kind in {"external", "tool"}:
        return "medium"
    if kind == "unknown":
        return "medium"
    return "low"


def dify_node_summary(node: Mapping[str, Any], node_data: Mapping[str, Any]) -> str:
    for key in ("desc", "description", "summary", "prompt_template", "query"):
        if node_data.get(key):
            return sanitize_summary(node_data.get(key))
    if node.get("type"):
        return sanitize_summary(f"Dify node type: {node.get('type')}")
    return ""


def dify_component_metadata(node_data: Mapping[str, Any]) -> dict[str, Any]:
    node_type = str(node_data.get("type") or "").strip().lower()
    metadata: dict[str, Any] = {}
    if node_type == "http-request":
        authorization = (
            node_data.get("authorization")
            if isinstance(node_data.get("authorization"), Mapping)
            else {}
        )
        metadata["authority"] = {
            "owner": "Dify workflow node",
            "method": node_data.get("method"),
            "endpoint": node_data.get("url"),
            "auth": authorization.get("type") or "headers",
        }
    if node_data.get("outputs") is not None:
        metadata["variables"] = {
            "writes": node_data.get("outputs"),
        }
    if node_data.get("variables") is not None:
        metadata.setdefault("variables", {})
        if isinstance(metadata["variables"], Mapping):
            metadata["variables"] = dict(metadata["variables"])
            metadata["variables"]["reads"] = node_data.get("variables")
    return sanitize_metadata(metadata)


def normalize_runtime(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return {"events": value}
    return {}


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = sanitize_summary(key, max_chars=80)
            if not key_text:
                continue
            if is_secret_key(key):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_metadata(nested)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return sanitize_summary(value, max_chars=240)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_summary(value, max_chars=240)


def _system_payload(
    payload: Mapping[str, Any],
    *,
    source_path: str | Path | None,
    source_type: str,
) -> dict[str, Any]:
    raw_system = payload.get("system") if isinstance(payload.get("system"), Mapping) else {}
    app = payload.get("app") if isinstance(payload.get("app"), Mapping) else {}
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), Mapping) else {}
    source_name = Path(source_path).stem if source_path else "system"
    name = (
        raw_system.get("name")
        or app.get("name")
        or workflow.get("name")
        or payload.get("name")
        or source_name
    )
    system_id = raw_system.get("id") or app.get("id") or workflow.get("id") or slug_id(name)
    return {
        "id": str(system_id),
        "name": str(name),
        "sourceType": source_type,
    }


def slug_id(value: object) -> str:
    text = "".join(character.lower() if character.isalnum() else "-" for character in str(value))
    text = "-".join(part for part in text.split("-") if part)
    return text or "system"


def _component_id(item: Mapping[str, Any], *, fallback: str) -> str:
    value = item.get("id") or item.get("node_id") or item.get("name") or fallback
    return str(value).strip() or fallback


def _label(item: Mapping[str, Any], fallback: str) -> str:
    value = item.get("label") or item.get("title") or item.get("name") or fallback
    return sanitize_summary(value, max_chars=80) or fallback


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []
