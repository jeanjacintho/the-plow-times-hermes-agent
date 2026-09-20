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
  add      --text TEXT --kind {one_off,subscription,section,assignment}
           --depth {quick,deep} [--run-on YYYY-MM-DD] [--deliver-at HH:MM]
           [--scheduled-for ISO8601]
  cancel   <id>            any topic the owner says stop on
  mark     <id> --status {pending,running,delivered} [--at ISO8601]
  list     [--kind K]      prints the topics array as JSON
  reopen-sections          every section/subscription that is delivered or
                           running becomes pending (a paper about to run;
                           measured live, delivered sections were skipped
                           and the next edition had desks only)

`--run-on` is the date a `section`/`assignment` belongs to the paper:
required for `assignment` (the one day its result appears) and refused for
every other kind. Strict `YYYY-MM-DD`, never a parsed guess.

`--deliver-at` is the container-local `HH:MM` a `section` belongs to a
different paper than the main daily edition. Required for nothing: absent
means the section rides the main paper at `delivery.hour`. Refused for
every kind except `section`. Same `HH:MM` shape as `delivery.hour`.

Every mutating subcommand prints a JSON envelope with the affected topic.
Exit status is non-zero on any refusal, and the refusal names the reason.

Status transitions (design doc §3.3):
  pending  -> running                  every kind (a run started)
  running  -> delivered                every kind (an edition shipped)
  running  -> pending                  subscription/section only (awaiting
                                       the next run; a one-off/assignment that
                                       fails stays running so the failure is
                                       visible, not silent)
  delivered -> pending                 subscription/section only (the nightly
                                       cycle)
  anything non-terminal -> cancelled   the owner said stop; a delivered
                                       one-off OR assignment is terminal and
                                       cannot be cancelled

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
from datetime import date, datetime, timezone

TOPICS_FILE = "topics.json"
KINDS = ("one_off", "subscription", "section", "assignment")
DEPTHS = ("quick", "deep")
STATUSES = ("pending", "running", "delivered", "cancelled")
ID_RE = re.compile(r"^t_[0-9a-f]{4}$")
RUN_ON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DELIVER_AT_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


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


def checked_run_on(args):
    """The strict YYYY-MM-DD date, or a refusal naming why.

    An assignment without `run_on` has no day to appear -- an edition
    promise with no date. A non-assignment with one is a date nothing
    reads. Both refuses, rather than storing a date that means nothing.
    """
    raw = (args.run_on or "").strip()
    if args.kind == "assignment":
        if not raw:
            sys.exit("error: --run-on YYYY-MM-DD is required for an assignment")
        if not RUN_ON_RE.fullmatch(raw):
            sys.exit(f"error: --run-on {raw!r} is not a strict YYYY-MM-DD date")
        try:
            date.fromisoformat(raw)
        except ValueError:
            sys.exit(f"error: --run-on {raw!r} is not a real calendar date")
        return raw
    if raw:
        sys.exit(f"error: --run-on is only meaningful for an assignment, not a {args.kind}")
    return None


def checked_deliver_at(args):
    """The strict HH:MM paper hour, or a refusal naming why.

    A section without one rides the main daily paper. Any other kind with
    one is an hour nothing reads -- refuse rather than store a slot that
    would never fire.
    """
    raw = (getattr(args, "deliver_at", None) or "").strip()
    if args.kind != "section":
        if raw:
            sys.exit(
                f"error: --deliver-at is only meaningful for a section, not a {args.kind}"
            )
        return None
    if not raw:
        return None
    if not DELIVER_AT_RE.fullmatch(raw):
        sys.exit(f"error: --deliver-at {raw!r} is not a strict HH:MM hour")
    return raw


def cmd_add(args):
    topics = load_topics()
    run_on = checked_run_on(args)
    deliver_at = checked_deliver_at(args)
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
    # Assignments carry the day their edition belongs to; sections don't
    # (they are evergreen) and the key is omitted so a section never looks
    # like a dated one-day item.
    if run_on is not None:
        topic["run_on"] = run_on
    # Timed papers: omit the key when the section rides the main edition,
    # so a main-paper section never looks like it owns a second slot.
    if deliver_at is not None:
        topic["deliver_at"] = deliver_at
    if not topic["text"]:
        sys.exit("error: --text is required and may not be blank")
    # A section is evergreen: the same one twice is not a second beat, it is
    # the same standing interest recorded again. Measured live: an owner
    # re-ran setup a few times and topics.json reached 48 sections covering
    # five actual interests (technology 10x, AI 9x, Formula 1 9x, NFL 8x,
    # Lakers 5x). Every daily run researches every pending section, so each
    # duplicate is a redundant block in the paper, paid for in tokens. One-offs
    # and assignments are NOT collapsed: "research X again" is a real second
    # request.
    if topic["kind"] == "section":
        wanted = topic["text"].casefold()
        existing = next(
            (t for t in topics
             if t.get("kind") == "section"
             and t.get("status") == "pending"
             and (t.get("text") or "").strip().casefold() == wanted),
            None,
        )
        if existing is not None:
            print(json.dumps({"duplicate_of": existing["id"], "kind": "section",
                              "text": existing.get("text"),
                              "status": existing.get("status")}))
            return 0
    topics.append(topic)
    save_topics(topics)
    print(json.dumps({"added": topic["id"], "kind": topic["kind"],
                      "depth": topic["depth"], "status": topic["status"],
                      "run_on": topic.get("run_on"),
                      "deliver_at": topic.get("deliver_at")}))
    return 0


def cmd_cancel(args):
    topics = load_topics()
    topic = find_topic(topics, args.id)
    # A delivered one-off or assignment has already run its one day/life:
    # there is nothing left to cancel, and marking it cancelled would be a
    # second terminal state for the same finished thing.
    if topic["kind"] in ("one_off", "assignment") and topic["status"] == "delivered":
        sys.exit(f"error: {topic['id']} is a delivered {topic['kind']} -- nothing to cancel")
    topic["status"] = "cancelled"
    save_topics(topics)
    print(json.dumps({"cancelled": topic["id"], "text": topic["text"]}))
    return 0


# The transition table from the docstring, as data: {(from, to): kinds-allowed}.
TRANSITIONS = {
    ("pending", "running"): KINDS,
    ("running", "delivered"): KINDS,
    ("running", "pending"): ("subscription", "section"),
    ("delivered", "pending"): ("subscription", "section"),
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


EVERGREEN = ("section", "subscription")
REOPEN_FROM = ("delivered", "running")


def reopen_evergreen(topic_list=None):
    """Put evergreen topics back on the next paper's research list.

    One-offs and assignments stay delivered. Cancelled stays cancelled.
    This is the moment a section ships, so it is also the one writer of
    last_edition_at for these kinds; a topic already marked delivered
    keeps the stamp that mark wrote.
    """
    owned = topic_list is None
    topics = load_topics() if owned else topic_list
    reopened = []
    for topic in topics:
        if topic.get("kind") not in EVERGREEN:
            continue
        if topic.get("status") not in REOPEN_FROM:
            continue
        if topic["status"] == "running":
            topic["last_edition_at"] = now_iso()
        topic["status"] = "pending"
        topic["scheduled_for"] = None
        reopened.append(topic["id"])
    if owned:
        save_topics(topics)
    return reopened


def cmd_reopen_sections(args):
    reopened = reopen_evergreen()
    print(json.dumps({"reopened": reopened}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="record a new topic")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--kind", required=True, choices=KINDS)
    p_add.add_argument("--depth", required=True, choices=DEPTHS)
    p_add.add_argument("--run-on", default=None,
                       help="YYYY-MM-DD; assignment only (the day it appears)")
    p_add.add_argument("--scheduled-for", default=None,
                       help="ISO8601 moment the one-off is scheduled to run")
    p_add.add_argument(
        "--deliver-at", default=None,
        help="HH:MM; section only (a paper other than the main daily edition)",
    )
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

    p_reopen = sub.add_parser(
        "reopen-sections",
        help="pending every delivered/running section and subscription",
    )
    p_reopen.set_defaults(func=cmd_reopen_sections)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())