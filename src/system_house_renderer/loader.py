from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_document(path: str | Path) -> Any:
    resolved = Path(path)
    text = resolved.read_text(encoding="utf-8")
    suffix = resolved.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        return load_yaml(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return load_yaml(text)


def load_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError(
            "YAML input requires PyYAML. Install the optional dependency with "
            "`pip install system-house-renderer[yaml]`, or provide JSON input."
        ) from exc
    return yaml.safe_load(text)


def write_json(path: str | Path, payload: Any) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
