from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


class RuntimeStatusWriter:
    def __init__(
        self,
        path: str | Path | None,
        *,
        module: str,
        host: str | None = None,
        port: int | None = None,
        health_url: str | None = None,
        shutdown_url: str | None = None,
        shutdown_command: str | None = None,
        command_line: list[str] | None = None,
    ) -> None:
        self.path = Path(path) if path else None
        self.module = module
        self.host = host
        self.port = port
        self.health_url = health_url
        self.shutdown_url = shutdown_url
        self.shutdown_command = shutdown_command
        self.command_line = command_line or list(sys.argv)
        self.started_monotonic = time.monotonic()
        self.started_at = utc_now()

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def write_running(self) -> None:
        self.write_state("running")

    def write_stopped(self) -> None:
        self.write_state("stopped", stopped_at=utc_now())

    def write_failed(self, message: str) -> None:
        self.write_state(
            "failed",
            stopped_at=utc_now(),
            error=message[:500],
        )

    def write_state(self, state: str, **extra: Any) -> None:
        if self.path is None:
            return
        payload: dict[str, Any] = {
            "module": self.module,
            "pid": os.getpid(),
            "parent_pid": os.getppid() if hasattr(os, "getppid") else None,
            "started_at": self.started_at,
            "host": self.host,
            "port": self.port,
            "health_url": self.health_url,
            "shutdown_url": self.shutdown_url,
            "shutdown_command": self.shutdown_command,
            "command_line": list(self.command_line),
            "state": state,
            "uptime_s": round(time.monotonic() - self.started_monotonic, 3),
        }
        payload.update(extra)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
