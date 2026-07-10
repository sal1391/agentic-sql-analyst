"""demo_log: stdout JSON line + JSONL file append, never raises."""
import json

from app import demo_log


def test_log_event_prints_and_appends(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(demo_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(demo_log, "LOG_FILE", tmp_path / "entries.jsonl")

    demo_log.log_event("email_entry", email="a@b.com")

    out = capsys.readouterr().out
    assert "[demo-log]" in out
    printed = json.loads(out.split("[demo-log]", 1)[1].strip())
    assert printed["kind"] == "email_entry"
    assert printed["email"] == "a@b.com"
    assert "ts" in printed

    lines = (tmp_path / "entries.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0])["email"] == "a@b.com"


def test_log_event_survives_unwritable_dir(tmp_path, capsys, monkeypatch):
    blocked = tmp_path / "nope" / "deeper"
    monkeypatch.setattr(demo_log, "LOG_DIR", blocked)
    monkeypatch.setattr(demo_log, "LOG_FILE", blocked / "entries.jsonl")
    monkeypatch.setattr(demo_log.Path, "mkdir", _raise_oserror)

    demo_log.log_event("guardrail_violation", layer="classifier")  # must not raise
    assert "[demo-log]" in capsys.readouterr().out


def test_log_event_survives_unserializable_fields(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(demo_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(demo_log, "LOG_FILE", tmp_path / "entries.jsonl")
    circular = {}
    circular["self"] = circular
    demo_log.log_event("weird", data={(1, 2): "tuple-key"}, loop=circular)  # must not raise
    out = capsys.readouterr().out
    assert "[demo-log]" in out


def _raise_oserror(*args, **kwargs):
    raise OSError("read-only fs")
