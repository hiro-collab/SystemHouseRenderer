from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from system_house_renderer.diagnostics import add_hidden_item, add_warning


SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|authorization|bearer|private[_-]?key)",
    re.IGNORECASE,
)

PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: re.Pattern[str]


VALUE_REDACTION_RULES = [
    RedactionRule(
        "private_key_block",
        PRIVATE_KEY_BLOCK_RE,
    ),
    RedactionRule(
        "authorization_header",
        re.compile(
            r"\bAuthorization\s*:\s*(?:Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]{8,}",
            re.IGNORECASE,
        ),
    ),
    RedactionRule(
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    ),
    RedactionRule(
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    RedactionRule(
        "openai_style_key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    ),
    RedactionRule(
        "secret_assignment",
        re.compile(
            r"\b(?:api[_-]?key|token|secret|password|credential)\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}",
            re.IGNORECASE,
        ),
    ),
    RedactionRule(
        "long_api_key",
        re.compile(
            r"(?<![A-Za-z0-9_-])(?=[A-Za-z0-9_-]{32,})(?=[A-Za-z0-9_-]*[A-Z])(?=[A-Za-z0-9_-]*[a-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])"
        ),
    ),
    RedactionRule(
        "windows_path",
        re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*"),
    ),
    RedactionRule(
        "home_or_absolute_path",
        re.compile(r"(?<!\w)(?:~|/Users|/home|/var|/tmp|/opt|/etc)/[^\s\"'<>]+"),
    ),
]


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
    elif isinstance(value, str):
        if contains_secret_value(value):
            paths.append(prefix or "<value>")
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
    paths = unique_paths(find_secret_paths(value))
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


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def sanitize_summary(value: object, *, max_chars: int = 180) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return redact_secret_values(text)[:max_chars]


def contains_secret_value(text: object) -> bool:
    value = str(text or "")
    return any(rule.pattern.search(value) for rule in VALUE_REDACTION_RULES)


def redact_secret_values(text: object) -> str:
    redacted = str(text or "")
    for rule in VALUE_REDACTION_RULES:
        redacted = rule.pattern.sub("[redacted]", redacted)
    return redacted


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
