#!/usr/bin/env python3
"""The paper's own record of the owner's company, so the advisor's desk can place it.

usage:
  company.py show
  company.py set --request <path to {"key", "value", "source", "as_of"} JSON>

Facts come from mail and messages anyone can send, so `set` takes them from a file the
agent writes, never from argv: no fact is ever shell syntax. as_of is an ISO-8601 time
with offset (2026-09-19T07:12-07:00). A fact changes only on newer evidence: a newer as_of
wins (the same value just advances as_of and source), an older one or a different value
at the same instant is refused. Unlike history.json this is a record, not a convenience,
so a corrupt file fails loudly by name and is never replaced.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import sys
from datetime import datetime

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


def moment(as_of):
    """as_of as an aware datetime; a date-only as_of from an older record is local midnight."""
    return datetime.fromisoformat(as_of).astimezone()


def read_request(path):
    """(key, value, source, as_of) from the agent's request file; raises when it is not one."""
    req = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(req, dict) or req.get("key") not in KEYS or not FIELDS <= req.keys():
        raise ValueError(f'expected {{"key": one of {KEYS}, "value", "source", "as_of"}}')
    moment(req["as_of"])  # not an ISO-8601 time: fail here, before it is stored
    return req["key"], req["value"], req["source"], req["as_of"]


def set_fact(facts, key, value, source, as_of):
    old = facts.get(key)
    if old and moment(as_of) <= moment(old["as_of"]):
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
    path = company_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # One writer at a time across the DM and cron sessions: the whole load-compare-write
    # runs under an OS lock the kernel drops if the process dies.
    with open(path.with_suffix(".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            facts = load()
        except ValueError as exc:
            print(f"CORRUPT: {path}: {exc}. Fix or remove it by hand.", file=sys.stderr)
            return 1
        if args.cmd == "set":
            print(set_fact(facts, *read_request(args.request)))
            return 0
    if not facts:
        print("EMPTY")
    else:
        for key, fact in sorted(facts.items()):
            print(f"{key}: {fact['value']} (as of {fact['as_of']}; source: {fact['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
