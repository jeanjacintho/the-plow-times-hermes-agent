#!/usr/bin/env python3
"""What the priority desk printed on recent days, so the next morning can follow up.

usage:
  history.py record --date YYYY-MM-DD --edition-json <run/<id>/edition.json>

Records the priority section the delivered edition carried, never desk notes:
run/desk-priority/notes.json outlives the run, so on a day the desk was
skipped it is yesterday's advice, which the owner never received today.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import date as Date, timedelta

KEEP_DAYS = 30


def history_path():
    return pathlib.Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt")) / "history.json"


def _valid_entry(entry):
    return (isinstance(entry, dict) and isinstance(entry.get("date"), str)
            and isinstance(entry.get("desk"), dict)
            and str(entry["desk"].get("headline") or "").strip() != "")


def load():
    """History is a convenience, not a record: an unreadable file is set aside, never fatal."""
    path = history_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except ValueError:
        data = None
    if not isinstance(data, list) or not all(_valid_entry(e) for e in data):
        os.replace(path, path.with_name(path.name + ".corrupt"))
        return []
    return data


def record(date, desk):
    """Upsert the day's printed desk and drop entries older than KEEP_DAYS."""
    cutoff = (Date.fromisoformat(date) - timedelta(days=KEEP_DAYS)).isoformat()
    entries = [e for e in load() if e["date"] != date and e["date"] >= cutoff]
    entries.append({"date": date, "desk": desk})
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sorted(entries, key=lambda e: e["date"]), ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--date", required=True)
    r.add_argument("--edition-json", required=True)
    args = parser.parse_args(argv)
    with open(args.edition_json, encoding="utf-8") as fh:
        sections = json.load(fh).get("sections") or []
    printed = next((s for s in sections if isinstance(s, dict) and s.get("desk") == "priority"
                    and isinstance(s.get("priority"), dict)), None)
    if printed is None:
        print("SKIPPED: this edition carried no priority desk")
        return 0
    record(args.date, {**printed["priority"], "headline": printed["headline"]})
    print("RECORDED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
