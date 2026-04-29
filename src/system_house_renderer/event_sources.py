from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlparse

from system_house_renderer.loader import load_document


SWORD_TRACE_COMPONENTS = [
    {
        "id": "gesture",
        "label": "Gesture",
        "kind": "input",
        "summary": "Gesture detector or receiver event.",
    },
    {
        "id": "stt",
        "label": "STT",
        "kind": "tool",
        "summary": "Speech recording and transcription stage.",
    },
    {
        "id": "handoff",
        "label": "Handoff",
        "kind": "tool",
        "summary": "Prompt or command handoff stage.",
    },
    {
        "id": "dify",
        "label": "Dify",
        "kind": "external",
        "summary": "Dify request and response stage.",
    },
    {
        "id": "tts",
        "label": "TTS",
        "kind": "tool",
        "summary": "Text-to-speech state stage.",
    },
    {
        "id": "avatar",
        "label": "Avatar",
        "kind": "output",
        "summary": "Avatar expression and rendering stage.",
    },
]

SWORD_TRACE_FLOWS = [
    {"id": "gesture_to_stt", "from": "gesture", "to": "stt", "kind": "control"},
    {"id": "stt_to_handoff", "from": "stt", "to": "handoff", "kind": "data"},
    {"id": "handoff_to_dify", "from": "handoff", "to": "dify", "kind": "external"},
    {"id": "dify_to_tts", "from": "dify", "to": "tts", "kind": "data"},
    {"id": "tts_to_avatar", "from": "tts", "to": "avatar", "kind": "data"},
]

TEXT_KEYS = (
    "text",
    "transcript",
    "command",
    "answer",
    "response_text",
    "request_text",
    "delta",
)


def load_runtime_source(
    source: str | Path,
    *,
    adapter: str = "auto",
    turn_id: str | None = None,
) -> dict[str, Any]:
    raw = load_raw_event_source(source)
    selected_adapter = choose_runtime_adapter(raw, str(source), adapter)
    if selected_adapter == "sword-events":
        return sword_events_to_topology(raw_events(raw), turn_id=turn_id)
    return normalize_generic_runtime(raw, turn_id=turn_id)


def load_raw_event_source(source: str | Path) -> Any:
    source_text = str(source)
    if is_url(source_text):
        return load_url_event_source(source_text)
    path = Path(source)
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    return load_document(path)


def load_url_event_source(url: str) -> Any:
    with request.urlopen(url, timeout=5.0) as response:
        body = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "")
    if "text/event-stream" in content_type or body.lstrip().startswith(("event:", "id:", "data:", ":")):
        return parse_sse_events(body)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return parse_sse_events(body)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if isinstance(payload, dict):
            events.append(payload)
    return events


def parse_sse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    data_lines: list[str] = []
    event_type = ""
    event_id = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line == "":
            append_sse_event(events, data_lines, event_type=event_type, event_id=event_id)
            data_lines = []
            event_type = ""
            event_id = ""
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    append_sse_event(events, data_lines, event_type=event_type, event_id=event_id)
    return events


def append_sse_event(
    events: list[dict[str, Any]],
    data_lines: list[str],
    *,
    event_type: str,
    event_id: str,
) -> None:
    if not data_lines:
        return
    data = "\n".join(data_lines).strip()
    if not data or data == "[DONE]":
        return
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        payload = {"payload": {"data_length": len(data), "data_hash": short_hash(data)}}
    if not isinstance(payload, dict):
        payload = {"payload": {"data_length": len(data), "data_hash": short_hash(data)}}
    if event_type and "type" not in payload:
        payload["type"] = event_type
    if event_id and "event_id" not in payload:
        payload["event_id"] = event_id
    events.append(payload)


def choose_runtime_adapter(raw: Any, source: str, adapter: str) -> str:
    if adapter != "auto":
        return adapter
    if "/api/events" in source or source.lower().endswith(".jsonl"):
        return "sword-events"
    events = raw_events(raw)
    if events and any(looks_like_sword_event(event) for event in events[:10]):
        return "sword-events"
    return "generic"


def normalize_generic_runtime(raw: Any, *, turn_id: str | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        runtime = dict(raw)
    else:
        runtime = {"events": raw_events(raw)}
    if turn_id:
        runtime["events"] = [
            event for event in raw_events(runtime) if event_turn_id(event) == turn_id
        ]
        runtime["selectedTurnId"] = turn_id
    return {"runtime": runtime}


def sword_events_to_topology(
    events: list[dict[str, Any]],
    *,
    turn_id: str | None = None,
) -> dict[str, Any]:
    selected_events = [
        event for event in events if turn_id is None or event_turn_id(event) == turn_id
    ]
    runtime_events = [
        normalized_sword_runtime_event(event, index)
        for index, event in enumerate(selected_events)
    ]
    runtime_events = [event for event in runtime_events if event is not None]
    turn_ids = sorted({event["turnId"] for event in runtime_events if event.get("turnId")})
    return {
        "system": {
            "id": "sword-runtime-trace",
            "name": "Sword Runtime Trace",
        },
        "components": list(SWORD_TRACE_COMPONENTS),
        "flows": list(SWORD_TRACE_FLOWS),
        "runtime": {
            "events": runtime_events,
            "selectedTurnId": turn_id or "",
            "turnIds": turn_ids,
            "sourceAdapter": "sword-events",
        },
    }


def normalized_sword_runtime_event(
    event: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    node_id = classify_sword_event(event)
    if node_id is None:
        return None
    payload = event_payload(event)
    normalized: dict[str, Any] = {
        "nodeId": node_id,
        "eventType": str(event.get("type") or event.get("event") or ""),
        "source": str(event.get("source") or ""),
        "sequence": index,
    }
    turn_id = event_turn_id(event)
    if turn_id:
        normalized["turnId"] = turn_id
    timestamp_wall = event.get("timestamp_wall") or event.get("timestampWall") or event.get("timestamp")
    if timestamp_wall is not None:
        normalized["timestampWall"] = timestamp_wall
    timestamp_monotonic = event.get("timestamp_monotonic") or event.get("timestampMonotonic")
    if timestamp_monotonic is not None:
        normalized["timestampMonotonic"] = timestamp_monotonic
    latency_ms = event_latency_ms(event, payload)
    if latency_ms is not None:
        normalized["latencyMs"] = latency_ms
    if event_has_error(event, payload):
        normalized["error"] = True
    add_text_fingerprints(normalized, payload)
    return normalized


def classify_sword_event(event: dict[str, Any]) -> str | None:
    payload = event_payload(event)
    text = " ".join(
        str(part)
        for part in (
            event.get("type"),
            event.get("event"),
            event.get("source"),
            payload.get("event"),
            payload.get("state"),
            payload.get("status"),
        )
        if part is not None
    ).lower()
    if "avatar" in text or "vrm" in text:
        return "avatar"
    if "tts" in text:
        return "tts"
    if "dify" in text:
        return "dify"
    if "handoff" in text:
        return "handoff"
    if "stt" in text or "transcript" in text or "recording" in text or "voice" in text:
        return "stt"
    if "gesture" in text or "sword" in text:
        return "gesture"
    return None


def add_text_fingerprints(target: dict[str, Any], payload: dict[str, Any]) -> None:
    for key in TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            target[f"{key}Length"] = len(value)
            target[f"{key}Hash"] = short_hash(value)


def event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def raw_events(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [event for event in raw if isinstance(event, dict)]
    if isinstance(raw, dict):
        for key in ("events", "data", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                return [event for event in value if isinstance(event, dict)]
        return [raw]
    return []


def looks_like_sword_event(event: dict[str, Any]) -> bool:
    return bool(
        event.get("event_id")
        or event.get("turn_id")
        or event.get("payload")
        or str(event.get("type") or "").startswith(("gesture.", "dify.", "tts.", "avatar."))
    )


def event_turn_id(event: dict[str, Any]) -> str | None:
    payload = event_payload(event)
    value = event.get("turn_id") or event.get("turnId") or payload.get("turn_id") or payload.get("turnId")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def event_latency_ms(event: dict[str, Any], payload: dict[str, Any]) -> float | None:
    for container in (payload, event):
        for key in ("latencyMs", "latency_ms", "elapsedMs", "elapsed_ms", "durationMs", "duration_ms"):
            if key in container:
                return maybe_float(container.get(key))
        for key in ("latencyS", "latency_s", "elapsedS", "elapsed_s", "durationS", "duration_s"):
            if key in container:
                value = maybe_float(container.get(key))
                return value * 1000.0 if value is not None else None
    return None


def event_has_error(event: dict[str, Any], payload: dict[str, Any]) -> bool:
    if bool(event.get("error") or payload.get("error")):
        return True
    text = " ".join(
        str(value)
        for value in (
            event.get("type"),
            event.get("status"),
            payload.get("event"),
            payload.get("status"),
            payload.get("state"),
        )
        if value is not None
    ).lower()
    return any(token in text for token in ("error", "failed", "failure", "exception"))


def maybe_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}
