#!/usr/bin/env python3
"""Today's free windows from the calendar desk's events.json.

usage:
  day_shape.py free-blocks <events.json> <out.json> --tz <IANA> [--now <ISO8601>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DAY_START = "08:00"
DAY_END = "19:00"
MIN_BLOCK_MINUTES = 45
EVENT_KEYS = ("start", "end", "title", "all_day")
HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
ERROR = {"status": "error", "free_blocks": []}


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _free_blocks(busy, now):
    now_min = now.hour * 60 + now.minute
    now_min = -(-now_min // 15) * 15
    cursor = max(_minutes(DAY_START), now_min)
    day_end = _minutes(DAY_END)
    blocks = []
    for start, end in sorted(busy):
        if end <= cursor:
            continue
        if start > cursor:
            blocks.append((cursor, min(start, day_end)))
        cursor = max(cursor, end)
        if cursor >= day_end:
            break
    if cursor < day_end:
        blocks.append((cursor, day_end))
    return [{"start": _hhmm(s), "end": _hhmm(e)} for s, e in blocks if e - s >= MIN_BLOCK_MINUTES]


def validate_events(payload):
    """Failures in run/desk-calendar/events.json; empty list means usable."""
    failures = []
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return ["events.json has no events list"]
    for i, ev in enumerate(payload["events"]):
        if not isinstance(ev, dict):
            failures.append(f"events[{i}] is not an object")
            continue
        if not str(ev.get("title", "")).strip():
            failures.append(f"events[{i}].title is blank")
        if not isinstance(ev.get("all_day"), bool):
            failures.append(f"events[{i}].all_day is not a boolean")
        if ev.get("all_day"):
            continue
        start_ok = isinstance(ev.get("start"), str) and bool(HHMM.fullmatch(ev["start"]))
        end_ok = isinstance(ev.get("end"), str) and bool(HHMM.fullmatch(ev["end"]))
        for key in ("start", "end"):
            ok = start_ok if key == "start" else end_ok
            if not ok:
                failures.append(f"events[{i}].{key} is not HH:MM")
        if start_ok and end_ok and ev["end"] <= ev["start"]:
            failures.append(f"events[{i}] ends before it starts")
    return failures


def free_blocks(payload, now):
    """Today's free windows from validated events (all-day never blocks)."""
    busy = [(_minutes(e["start"]), _minutes(e["end"]))
            for e in payload["events"]
            if not e.get("all_day") and not e.get("tomorrow")]
    return _free_blocks(busy, now)


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    fb = sub.add_parser("free-blocks")
    fb.add_argument("events")
    fb.add_argument("out")
    fb.add_argument("--tz", required=True)
    fb.add_argument("--now")
    args = parser.parse_args(argv)
    zone = ZoneInfo(args.tz)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    else:
        now = now.astimezone(zone)
    try:
        with open(args.events, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        payload = None
    failures = validate_events(payload) if payload is not None else ["events.json has no events list"]
    if failures:
        result = dict(ERROR)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        print("DAY:invalid")
        print("\n".join(failures))
        return 0
    blocks = free_blocks(payload, now)
    result = {"status": "ok", "free_blocks": blocks}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"DAY:ok BLOCKS:{len(blocks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
