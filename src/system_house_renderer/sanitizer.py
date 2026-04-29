from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from system_house_renderer.diagnostics import add_hidden_item, add_warning


SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|authorization|bearer|private[_-]?key)",
    re.IGNORECASE,
)


def is_secret_key(key: object) -> bool:
    return bool(SECRET_KEY_RE.search(str(key)))


def find_secret_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if is_secret_key(key) and _has_present_value(nested):
                paths.append(child_path)
            paths.extend(find_secret_paths(nested, prefix=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            child_path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(find_secret_paths(nested, prefix=child_path))
    return paths


def register_secret_findings(
    diagnostics: dict[str, list[dict[str, Any]]],
    value: Any,
    *,
    owner_id: str,
) -> bool:
    paths = find_secret_paths(value)
    for index, _path in enumerate(paths):
        suffix = "" if index == 0 else f":{index + 1}"
        add_hidden_item(diagnostics, f"{owner_id}:secret{suffix}", "secret")
    if paths:
        add_warning(
            diagnostics,
            "secret_detected",
            f"Sensitive configuration exists on {owner_id}; value was hidden.",
            related_id=owner_id,
        )
    return bool(paths)


def sanitize_summary(value: object, *, max_chars: int = 180) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if SECRET_KEY_RE.search(text):
        return "[redacted]"
    return text[:max_chars]


def _has_present_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True
