#!/usr/bin/env python3
"""topics.py -- the single writer for /var/lib/hermes/pt/topics.json.

The topic list is this agent's ENTIRE durable model of what it has been
asked to do (design doc §3.3): every subscription's nightly cron, every
one-off's scheduled run and every status question in chat reads it. That
makes it the one file nothing may improvise writes against -- a hand-edited
JSON blob in a turn is exactly how a subscription silently stops firing --
so all mutation goes through this script's subcommands, which validate the
kind, depth and status transitions and write atomically.

Reads are equally guarded: an unreadable or unexpected topics.json must stop
the run rather than read as "no topics", which is the invariant that keeps a
malformed file from dropping every subscription on the floor (the same rule
ld-dashboard's register_crons.py holds for jobs.json).

Subcommands:
  add      --text TEXT --kind {one_off,subscription} --depth {quick,deep}
  cancel   <id>            any topic the owner says stop on
  mark     <id> --status {pending,running,delivered} [--at ISO8601]
  list     [--kind K]      prints the topics array as JSON

Every mutating subcommand prints a JSON envelope with the affected topic.
Exit status is non-zero on any refusal, and the refusal names the reason.

Status transitions (design doc §3.3):
  pending  -> running                  both kinds (a run started)
  running  -> delivered                both kinds (an edition shipped)
  running  -> pending                  subscription only (awaiting next run;
                                       a one-off that fails stays running so
                                       the failure is visible, not silent)
  delivered -> pending                 subscription only (the nightly cycle)
  anything non-terminal -> cancelled   the owner said stop; a delivered
                                       one-off is terminal and cannot be

`PT_HOME` overrides the state directory (tests use it); it defaults to
/var/lib/hermes/pt. Timestamps are ISO 8601 with the container's offset.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

TOPICS_FILE = "topics.json"
KINDS = ("one_off", "subscription")
DEPTHS = ("quick", "deep")
STATUSES = ("pending", "running", "delivered", "cancelled")
ID_RE = re.compile(r"^t_[0-9a-f]{4}$")


def home():
    return pathlib.Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt"))


def topics_path():
    return home() / TOPICS_FILE


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_topics():
    """Read the topic list, refusing to pretend a broken file is empty.

    FileNotFoundError alone means no state yet -- the one absence that is a
    fresh instance. Every other failure (unreadable, bad JSON, wrong shape)
    propagates as SystemExit: writing a new topic into a file we could not
    trust would orphan every subscription already in it.
    """
    path = topics_path()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {path} exists but cannot be read ({exc!r}) -- refusing "
                 "to treat a broken topic store as an empty one")
    if not (isinstance(data, dict) and isinstance(data.get("topics"), list)):
        sys.exit(f"error: {path} is not a {{\"topics\": [...]}} object -- refusing "
                 "to guess at its shape")
    for topic in data["topics"]:
        if not (isinstance(topic, dict) and isinstance(topic.get("id"), str)):
            sys.exit(f"error: {path} holds a topic with no id -- refusing to "
                     "mutate a store this shape")
    return data["topics"]


def save_topics(topics):
    """Atomic write: tmp file in the same directory, then replace."""
    path = topics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"topics": topics}, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def find_topic(topics, ref):
    """Resolve a short id prefix; it must match exactly one topic."""
    matches = [t for t in topics if t["id"].startswith(ref)]
    if not matches:
        sys.exit(f"error: no topic matches {ref!r} -- use `list` to see ids")
    if len(matches) > 1:
        sys.exit(f"error: {ref!r} matches {len(matches)} topics -- be more specific")
    return matches[0]


def new_id(topics):
    while True:
        candidate = "t_" + os.urandom(2).hex()
        if ID_RE.fullmatch(candidate) and all(t["id"] != candidate for t in topics):
            return candidate


def cmd_add(args):
    topics = load_topics()
    topic = {
        "id": new_id(topics),
        "text": args.text.strip(),
        "kind": args.kind,
        "depth": args.depth,
        "status": "pending",
        "created_at": now_iso(),
        "last_edition_at": None,
        # One-off runs remember when their job is scheduled for, so SOUL.md
        # can answer "when will it land" from the file, not from memory.
        "scheduled_for": args.scheduled_for.strip() if args.scheduled_for else None,
    }
    if not topic["text"]:
        sys.exit("error: --text is required and may not be blank")
    topics.append(topic)
    save_topics(topics)
    print(json.dumps({"added": topic["id"], "kind": topic["kind"],
                      "depth": topic["depth"], "status": topic["status"]}))
    return 0


def cmd_cancel(args):
    topics = load_topics()
    topic = find_topic(topics, args.id)
    if topic["kind"] == "one_off" and topic["status"] == "delivered":
        sys.exit(f"error: {topic['id']} is a delivered one-off -- nothing to cancel")
    topic["status"] = "cancelled"
    save_topics(topics)
    print(json.dumps({"cancelled": topic["id"], "text": topic["text"]}))
    return 0


# The transition table from the docstring, as data: {(from, to): kinds-allowed}.
TRANSITIONS = {
    ("pending", "running"): KINDS,
    ("running", "delivered"): KINDS,
    ("running", "pending"): ("subscription",),
    ("delivered", "pending"): ("subscription",),
    ("pending", "cancelled"): KINDS,
    ("running", "cancelled"): KINDS,
}


def cmd_mark(args):
    topics = load_topics()
    topic = find_topic(topics, args.id)
    key = (topic["status"], args.status)
    if key not in TRANSITIONS or topic["kind"] not in TRANSITIONS[key]:
        sys.exit(f"error: {topic['id']} cannot go {topic['status']} -> {args.status} "
                 f"while it is a {topic['kind']} topic")
    if args.status == "delivered":
        topic["last_edition_at"] = args.at or now_iso()
    # A subscription delivered and sent back to pending keeps its edition
    # timestamp: last_edition_at is when its last edition shipped, however
    # many cycles ago.
    if args.status == "pending":
        topic["scheduled_for"] = None
    topic["status"] = args.status
    save_topics(topics)
    print(json.dumps({"marked": topic["id"], "status": topic["status"],
                      "last_edition_at": topic["last_edition_at"]}))
    return 0


def cmd_list(args):
    topics = load_topics()
    if args.kind:
        topics = [t for t in topics if t["kind"] == args.kind]
    print(json.dumps({"topics": topics}, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="record a new topic")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--kind", required=True, choices=KINDS)
    p_add.add_argument("--depth", required=True, choices=DEPTHS)
    p_add.add_argument("--scheduled-for", default=None,
                       help="ISO8601 moment the one-off is scheduled to run")
    p_add.set_defaults(func=cmd_add)

    p_cancel = sub.add_parser("cancel", help="stop watching a topic")
    p_cancel.add_argument("id")
    p_cancel.set_defaults(func=cmd_cancel)

    p_mark = sub.add_parser("mark", help="move a topic's status")
    p_mark.add_argument("id")
    p_mark.add_argument("--status", required=True, choices=STATUSES)
    p_mark.add_argument("--at", default=None, help="ISO8601 edition timestamp")
    p_mark.set_defaults(func=cmd_mark)

    p_list = sub.add_parser("list", help="print topics as JSON")
    p_list.add_argument("--kind", choices=KINDS, default=None)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())