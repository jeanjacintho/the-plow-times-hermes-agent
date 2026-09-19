#!/usr/bin/env python3
"""The paper's own record of the owner's company, so the advisor's desk can place it.

usage:
  company.py show
  company.py set --request <path to {"key", "value", "source", "as_of"} JSON>

Facts come from mail and messages anyone can send, so `set` reads them from a file, never
argv. as_of is a past ISO-8601 time with offset (2026-09-19T07:12-07:00). Only newer
evidence changes a fact: the same value just advances as_of and source, and an older one
or another value at the same instant is refused. Unlike history.json this is a record, so
a corrupt file fails loudly by name and is never replaced.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

KEYS = ("product", "revenue", "paying_customers", "referenceable_customers",
        "team_size", "raise", "stage")
FIELDS = {"value", "source", "as_of"}


def company_path():
    return pathlib.Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt")) / "company.json"


def load():
    """The stored facts; ValueError when the file is not the record's shape."""
    try:
        data = json.loads(company_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, dict) or not all(
            isinstance(f, dict) and FIELDS <= f.keys() for f in facts.values()):
        raise ValueError('expected {"facts": {"<key>": {"value", "source", "as_of"}}}')
    return facts


def read_request(path):
    """(key, value, source, as_of) from the agent's request file; raises when it is not one."""
    req = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(req, dict) or req.get("key") not in KEYS or not FIELDS <= req.keys():
        raise ValueError(f'expected {{"key": one of {KEYS}, "value", "source", "as_of"}}')
    when = datetime.fromisoformat(req["as_of"])
    if when.tzinfo is None or when > datetime.now(timezone.utc):
        raise ValueError(f"as_of {req['as_of']!r} must be a past time with an offset")
    return req["key"], req["value"], req["source"], req["as_of"]


def set_fact(facts, key, value, source, as_of):
    old = facts.get(key)
    # A request's as_of carries an offset; a date-only one in an older record is local midnight.
    if old and datetime.fromisoformat(as_of) <= datetime.fromisoformat(old["as_of"]).astimezone():
        if value == old["value"]:
            return f"UNCHANGED: {key}"
        return f"REFUSED: {key} is already recorded as of {old['as_of']}"
    facts[key] = {"value": value, "source": source, "as_of": as_of}
    path = company_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"facts": facts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return f"SET: {key}"


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("set").add_argument("--request", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        request = args.cmd == "set" and read_request(args.request)
    except ValueError as exc:
        print(f"BAD REQUEST: {args.request}: {exc}", file=sys.stderr)
        return 1
    path = company_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # One writer at a time, DM or cron, under a lock the kernel drops if the process dies.
    with open(path.with_suffix(".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            facts = load()
        except ValueError as exc:
            print(f"CORRUPT: {path}: {exc}. Fix or remove it by hand.", file=sys.stderr)
            return 1
        if request:
            print(set_fact(facts, *request))
            return 0
    if not facts:
        print("EMPTY")
    else:
        for key, fact in sorted(facts.items()):
            print(f"{key}: {fact['value']} (as of {fact['as_of']}; source: {fact['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
