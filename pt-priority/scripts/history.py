#!/usr/bin/env python3
"""The owner's recent priorities and whether they got done.

usage:
  history.py today  --date YYYY-MM-DD
  history.py record --date YYYY-MM-DD --priority-json <priority.json>
  history.py set    --date YYYY-MM-DD --status done|skipped
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import date as Date, timedelta

sys.path.insert(0, "/var/lib/hermes/skills/pt-shared/scripts")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "pt-shared", "scripts"))
import textnorm  # noqa: E402

KEEP_DAYS = 30
STATUSES = ("open", "done", "skipped")


def home():
    return pathlib.Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt"))


def history_path():
    return home() / "history.json"


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


def _valid_entry(entry):
    return (isinstance(entry, dict) and isinstance(entry.get("date"), str)
            and isinstance(entry.get("priority"), str) and entry.get("status") in STATUSES)


def load():
    """History is a convenience, not a record: an unreadable file is set aside, never fatal."""
    path = history_path()
    try:
        data = _load_json(path)
    except ValueError:
        data = "corrupt"
    if data is None:
        return []
    if not isinstance(data, list) or not all(_valid_entry(e) for e in data):
        os.replace(path, path.with_name(path.name + ".corrupt"))
        return []
    return sorted(data, key=lambda e: e["date"])


def _save(entries, ref_date):
    cutoff = (Date.fromisoformat(ref_date) - timedelta(days=KEEP_DAYS)).isoformat()
    _write_json(history_path(), [e for e in entries if e["date"] >= cutoff])


def recent(date, days=7):
    start = (Date.fromisoformat(date) - timedelta(days=days)).isoformat()
    return [e for e in load() if start <= e["date"] < date]


def today(date):
    return next((e for e in load() if e["date"] == date), None)


def record(date, priority):
    entries = [e for e in load() if e["date"] != date]
    entries.append({"date": date, "priority": priority, "status": "open"})
    _save(sorted(entries, key=lambda e: e["date"]), date)


def set_status(date, status):
    entries = load()
    for e in entries:
        if e["date"] == date:
            e["status"] = status
            _save(entries, date)
            return True
    return False


def streak(date, priority):
    by_date = {e["date"]: e for e in load()}
    count, day = 0, Date.fromisoformat(date)
    while True:
        day -= timedelta(days=1)
        entry = by_date.get(day.isoformat())
        if not entry or not textnorm.similar(entry["priority"], priority):
            return count
        count += 1


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("today")
    t.add_argument("--date", required=True)
    r = sub.add_parser("record")
    r.add_argument("--date", required=True)
    r.add_argument("--priority-json", required=True)
    s = sub.add_parser("set")
    s.add_argument("--date", required=True)
    s.add_argument("--status", choices=["done", "skipped"], required=True)
    args = parser.parse_args(argv)
    if args.cmd == "today":
        e = today(args.date)
        print("TODAY:none" if e is None else f"TODAY:{e['status']} {e['priority']}")
    elif args.cmd == "record":
        with open(args.priority_json, encoding="utf-8") as fh:
            record(args.date, json.load(fh)["priority"])
        print("RECORDED")
    else:
        print(f"STATUS:{args.status}" if set_status(args.date, args.status) else "STATUS:no-priority-today")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
