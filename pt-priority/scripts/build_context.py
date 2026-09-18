#!/usr/bin/env python3
"""Assemble run/desk-priority/context.json from the file, the calendar and recent history.

usage: build_context.py --run-dir <dir> --tz <IANA> [--now <ISO8601>]
Prints "CONTEXT:ok NOTES:<list|none>" or "CONTEXT:nothing" (neither source usable).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import date as Date, datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, "/var/lib/hermes/skills/pt-shared/scripts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "pt-shared", "scripts"))
sys.path.insert(0, HERE)
import day_shape  # noqa: E402
import history  # noqa: E402

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FILE_MISSING = {"status": "missing", "truncated": False, "sections": []}
CALENDAR_ERROR = {"status": "error", "events": [], "free_blocks": []}


def _load_json(path):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return json.loads(text)


def _write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_calendar(run_dir):
    payload = None
    try:
        payload = _load_json(pathlib.Path(run_dir) / "desk-calendar" / "events.json")
    except ValueError:
        payload = None
    day = None
    try:
        day = _load_json(pathlib.Path(run_dir) / "desk-priority" / "day.json")
    except ValueError:
        day = None
    failures = day_shape.validate_events(payload) if payload is not None else ["events.json has no events list"]
    day_ok = isinstance(day, dict) and day.get("status") == "ok" and isinstance(day.get("free_blocks"), list)
    if failures or not day_ok:
        return dict(CALENDAR_ERROR)
    return {
        "status": "ok",
        "events": payload["events"],
        "free_blocks": day["free_blocks"],
    }


def build(date, tz, file_result, calendar_result, recent):
    file_result = file_result or dict(FILE_MISSING)
    calendar_result = calendar_result or dict(CALENDAR_ERROR)
    notes = []
    if file_result["status"] == "missing":
        notes.append("file_missing")
    elif file_result["status"] == "empty":
        notes.append("file_empty")
    if calendar_result["status"] != "ok":
        notes.append("calendar_unavailable")
    return {
        "today": date,
        "weekday": WEEKDAYS[Date.fromisoformat(date).weekday()],
        "tz": tz,
        "file": file_result,
        "calendar": calendar_result,
        "history": recent,
        "notes": notes,
    }


def has_input(context):
    return context["file"]["status"] == "ok" or context["calendar"]["status"] == "ok"


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--tz", required=True)
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    zone = ZoneInfo(args.tz)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    else:
        now = now.astimezone(zone)
    date = now.date().isoformat()
    run = pathlib.Path(args.run_dir)

    def safe(rel):
        try:
            return _load_json(run / rel)
        except ValueError:
            return None

    context = build(date, args.tz, safe("desk-priority/file.json"), load_calendar(run),
                    history.recent(date, 7))
    out = run / "desk-priority" / "context.json"
    _write_json(out, context)
    if has_input(context):
        print(f"CONTEXT:ok NOTES:{','.join(context['notes']) or 'none'}")
    else:
        print("CONTEXT:nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
