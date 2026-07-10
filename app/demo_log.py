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
    """Log a demo event. Must never raise — callers are often error paths."""
    ts = datetime.now(timezone.utc).isoformat()
    try:
        line = json.dumps({"ts": ts, "kind": kind, **fields}, default=str)
    except Exception:  # circular refs, non-str dict keys, ...
        line = json.dumps({"ts": ts, "kind": str(kind), "error": "unserializable fields"})
    try:
        print(f"[demo-log] {line}", flush=True)
    except Exception:
        pass  # e.g. non-UTF-8 console or closed stdout — still try the file
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # ephemeral/readonly filesystem (Railway) — stdout already has it
