from __future__ import annotations

from typing import Any

from system_house_renderer.diagnostics import add_warning


DEFAULT_LATENCY_WARNING_MS = 2000.0
DEFAULT_COST_WARNING = 0.05
DEFAULT_TOKEN_WARNING = 8000


def normalize_runtime_metrics(
    runtime: dict[str, Any] | None,
    semantic_graph: dict[str, Any],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    payload = runtime if isinstance(runtime, dict) else {}
    thresholds = normalize_thresholds(payload.get("thresholds") or payload.get("limits") or {})
    node_ids = {node["id"] for node in semantic_graph.get("nodes", [])}
    edge_lookup = build_edge_lookup(semantic_graph)

    node_metrics: dict[str, dict[str, Any]] = {
        node_id: empty_node_metrics() for node_id in sorted(node_ids)
    }
    edge_metrics: dict[str, dict[str, Any]] = {
        edge["id"]: empty_edge_metrics() for edge in semantic_graph.get("edges", [])
    }
    active_node_order: list[str] = []
    seen_active_nodes: set[str] = set()

    events = runtime_events(payload)
    previous_node_id: str | None = None
    for event in events:
        if not isinstance(event, dict):
            continue
        node_id = event_node_id(event)
        if node_id in node_metrics:
            merge_node_event(node_metrics[node_id], event)
            if node_id not in seen_active_nodes:
                active_node_order.append(node_id)
                seen_active_nodes.add(node_id)
            if previous_node_id and previous_node_id != node_id:
                edge = edge_lookup.get((previous_node_id, node_id))
                if edge is not None:
                    merge_edge_event(edge_metrics[edge["id"]], event)
            previous_node_id = node_id

        edge_id = event_edge_id(event)
        if edge_id in edge_metrics:
            merge_edge_event(edge_metrics[edge_id], event)
        else:
            source = optional_text(event.get("from") or event.get("source"))
            target = optional_text(event.get("to") or event.get("target"))
            edge = edge_lookup.get((source, target)) if source and target else None
            if edge is not None:
                merge_edge_event(edge_metrics[edge["id"]], event)

    for stat in list_payload(payload, "nodeStats") + list_payload(payload, "node_stats"):
        if not isinstance(stat, dict):
            continue
        node_id = event_node_id(stat)
        if node_id in node_metrics:
            merge_node_event(node_metrics[node_id], stat, count_visit=False)

    for stat in list_payload(payload, "edgeStats") + list_payload(payload, "flowStats"):
        if not isinstance(stat, dict):
            continue
        edge_id = event_edge_id(stat)
        if edge_id in edge_metrics:
            merge_edge_event(edge_metrics[edge_id], stat, count_visit=False)

    annotate_node_metrics(node_metrics, thresholds, diagnostics)
    annotate_edge_metrics(edge_metrics, thresholds, diagnostics)

    return {
        "activeNodeIds": active_node_order,
        "activeEdgeIds": [
            edge_id
            for edge_id, metrics in sorted(edge_metrics.items())
            if metrics["visitCount"] > 0
        ],
        "nodeMetrics": node_metrics,
        "edgeMetrics": edge_metrics,
        "thresholds": thresholds,
    }


def normalize_thresholds(value: Any) -> dict[str, float]:
    payload = value if isinstance(value, dict) else {}
    return {
        "latencyWarningMs": float_or_default(
            payload.get("latencyWarningMs")
            or payload.get("latency_warning_ms")
            or payload.get("latencyMs"),
            DEFAULT_LATENCY_WARNING_MS,
        ),
        "costWarning": float_or_default(
            payload.get("costWarning") or payload.get("cost_warning") or payload.get("cost"),
            DEFAULT_COST_WARNING,
        ),
        "tokenWarning": float_or_default(
            payload.get("tokenWarning") or payload.get("token_warning") or payload.get("tokens"),
            float(DEFAULT_TOKEN_WARNING),
        ),
    }


def runtime_events(runtime: dict[str, Any]) -> list[Any]:
    events: list[Any] = []
    for key in ("events", "traces", "steps"):
        if isinstance(runtime.get(key), list):
            events.extend(runtime[key])
    return events


def build_edge_lookup(semantic_graph: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in semantic_graph.get("edges", []):
        lookup.setdefault((edge["from"], edge["to"]), edge)
    return lookup


def empty_node_metrics() -> dict[str, Any]:
    return {
        "visitCount": 0,
        "latencyMs": None,
        "totalLatencyMs": 0.0,
        "cost": 0.0,
        "tokens": 0,
        "errorCount": 0,
        "signals": [],
    }


def empty_edge_metrics() -> dict[str, Any]:
    return {
        "visitCount": 0,
        "latencyMs": None,
        "totalLatencyMs": 0.0,
        "cost": 0.0,
        "tokens": 0,
        "errorCount": 0,
        "signals": [],
    }


def merge_node_event(
    metrics: dict[str, Any],
    event: dict[str, Any],
    *,
    count_visit: bool = True,
) -> None:
    if count_visit:
        metrics["visitCount"] += 1
    merge_common_metrics(metrics, event)


def merge_edge_event(
    metrics: dict[str, Any],
    event: dict[str, Any],
    *,
    count_visit: bool = True,
) -> None:
    if count_visit:
        metrics["visitCount"] += 1
    merge_common_metrics(metrics, event)


def merge_common_metrics(metrics: dict[str, Any], event: dict[str, Any]) -> None:
    latency_ms = metric_float(
        event,
        "latencyMs",
        "latency_ms",
        "elapsedMs",
        "elapsed_ms",
        "durationMs",
        "duration_ms",
    )
    latency_s = metric_float(event, "latencyS", "latency_s", "elapsedS", "elapsed_s", "durationS", "duration_s")
    if latency_ms is None and latency_s is not None:
        latency_ms = latency_s * 1000.0
    if latency_ms is not None:
        metrics["totalLatencyMs"] += latency_ms
        metrics["latencyMs"] = max(float(metrics["latencyMs"] or 0.0), latency_ms)

    cost = metric_float(event, "cost", "costUsd", "cost_usd", "totalCost", "total_cost")
    if cost is not None:
        metrics["cost"] += cost

    tokens = metric_int(event, "tokens", "totalTokens", "total_tokens", "tokenCount", "token_count")
    if tokens is not None:
        metrics["tokens"] += tokens

    if event_has_error(event):
        metrics["errorCount"] += 1


def annotate_node_metrics(
    node_metrics: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    for node_id, metrics in node_metrics.items():
        signals = set(metrics.get("signals") or [])
        if metrics["errorCount"] > 0:
            signals.add("runtime_error")
            add_warning(
                diagnostics,
                "runtime_node_error",
                f"Runtime error was reported for {node_id}.",
                related_id=node_id,
            )
        if metrics["latencyMs"] is not None and metrics["latencyMs"] >= thresholds["latencyWarningMs"]:
            signals.add("high_latency")
            add_warning(
                diagnostics,
                "runtime_high_latency",
                f"{node_id} latency reached {metrics['latencyMs']:.0f} ms.",
                related_id=node_id,
            )
        if metrics["cost"] >= thresholds["costWarning"]:
            signals.add("high_cost")
            add_warning(
                diagnostics,
                "runtime_high_cost",
                f"{node_id} cost reached {metrics['cost']:.4f}.",
                related_id=node_id,
            )
        if metrics["tokens"] >= thresholds["tokenWarning"]:
            signals.add("high_tokens")
        metrics["signals"] = sorted(signals)


def annotate_edge_metrics(
    edge_metrics: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
    diagnostics: dict[str, list[dict[str, Any]]],
) -> None:
    for edge_id, metrics in edge_metrics.items():
        signals = set(metrics.get("signals") or [])
        if metrics["errorCount"] > 0:
            signals.add("runtime_error")
            add_warning(
                diagnostics,
                "runtime_edge_error",
                f"Runtime error was reported for flow {edge_id}.",
                related_id=edge_id,
            )
        if metrics["latencyMs"] is not None and metrics["latencyMs"] >= thresholds["latencyWarningMs"]:
            signals.add("high_latency")
        metrics["signals"] = sorted(signals)


def event_node_id(event: dict[str, Any]) -> str | None:
    return optional_text(
        event.get("nodeId")
        or event.get("node_id")
        or event.get("componentId")
        or event.get("component_id")
        or event.get("node")
    )


def event_edge_id(event: dict[str, Any]) -> str | None:
    return optional_text(
        event.get("edgeId")
        or event.get("edge_id")
        or event.get("flowId")
        or event.get("flow_id")
    )


def event_has_error(event: dict[str, Any]) -> bool:
    if bool(event.get("error")):
        return True
    status = str(event.get("status") or event.get("state") or event.get("level") or "").lower()
    return status in {"error", "failed", "failure", "exception"}


def metric_float(event: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if name in event:
            return maybe_float(event.get(name))
    return None


def metric_int(event: dict[str, Any], *names: str) -> int | None:
    value = metric_float(event, *names)
    return int(value) if value is not None else None


def maybe_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def float_or_default(value: Any, default: float) -> float:
    parsed = maybe_float(value)
    return default if parsed is None else parsed


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def list_payload(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    return value if isinstance(value, list) else []
