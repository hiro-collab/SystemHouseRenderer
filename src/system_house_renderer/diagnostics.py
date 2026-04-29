from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def new_diagnostics() -> dict[str, list[dict[str, Any]]]:
    return {"warnings": [], "hiddenItems": []}


def add_warning(
    diagnostics: dict[str, list[dict[str, Any]]],
    code: str,
    message: str,
    *,
    related_id: str | None = None,
) -> None:
    warning: dict[str, Any] = {"code": code, "message": message}
    if related_id:
        warning["relatedId"] = related_id
    diagnostics["warnings"].append(warning)


def add_hidden_item(
    diagnostics: dict[str, list[dict[str, Any]]],
    item_id: str,
    reason: str,
) -> None:
    item = {"id": item_id, "reason": reason}
    if item not in diagnostics["hiddenItems"]:
        diagnostics["hiddenItems"].append(item)


def warning_exists(
    diagnostics: Mapping[str, list[dict[str, Any]]],
    code: str,
) -> bool:
    return any(item.get("code") == code for item in diagnostics.get("warnings", []))
