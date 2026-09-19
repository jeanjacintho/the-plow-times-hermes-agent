#!/usr/bin/env python3
"""The paper's own record of the owner's company, so the advisor's desk can place it.

usage:
  company.py show
  company.py set <key> --value V --source S --as-of YYYY-MM-DD

A fact changes only on newer evidence: an older --as-of is refused and the same
value is a no-op. Unlike history.json this is a record, not a convenience, so a
corrupt file fails loudly by name and is never replaced.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import date as Date

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


def set_fact(facts, key, value, source, as_of):
    old = facts.get(key)
    if old and as_of < old["as_of"]:
        return f"REFUSED: {key} is already recorded as of {old['as_of']}"
    if old and value == old["value"]:
        return f"UNCHANGED: {key}"
    facts[key] = {"value": value, "source": source, "as_of": as_of}
    path = company_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"facts": facts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return f"SET: {key}"


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("key", choices=KEYS)
    s.add_argument("--value", required=True)
    s.add_argument("--source", required=True)
    s.add_argument("--as-of", required=True, type=lambda d: Date.fromisoformat(d).isoformat())
    args = parser.parse_args(argv)
    try:
        facts = load()
    except ValueError as exc:
        print(f"CORRUPT: {company_path()}: {exc}. Fix or remove it by hand.", file=sys.stderr)
        return 1
    if args.cmd == "set":
        print(set_fact(facts, args.key, args.value, args.source, args.as_of))
    elif not facts:
        print("EMPTY")
    else:
        for key, fact in sorted(facts.items()):
            print(f"{key}: {fact['value']} (as of {fact['as_of']}; source: {fact['source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
