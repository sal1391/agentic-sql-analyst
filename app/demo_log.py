"""Demo-mode event log: stdout (shows in Railway logs) + local JSONL file.

Shared by the email gate, guardrails, and demo analysis-error logging.
Logging must never break the user flow, so filesystem errors are swallowed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("demo_logs")
LOG_FILE = LOG_DIR / "entries.jsonl"


def log_event(kind: str, **fields) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
    line = json.dumps(record, default=str)
    print(f"[demo-log] {line}", flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # ephemeral/readonly filesystem (Railway) — stdout already has it
