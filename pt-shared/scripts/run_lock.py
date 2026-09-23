#!/usr/bin/env python3
"""run_lock.py -- one exclusive run per name, with stale takeover.

The daily paper's run is not idempotent and must not run twice at once.
A manual `hermes cron run` alongside the scheduled fire would start a
second session; the second finds every section already `running` (the
per-topic guard refuses to duplicate), compiles an empty edition, and
delivers it -- honest in form and misleading in effect, the one job this
agent must never do. `hermes cron` has no dedup, so the lock is a file
created with O_EXCL: the atomic primitive every process on the host agrees
on.

  acquire --name NAME [--stale-minutes N] [--wait-seconds N]
  release --name NAME

`acquire` prints exactly one word and always exits 0, so a cron-fired
session reads the decision instead of a status code:

  acquired        this process owns the run; release it when done
  stale-takeover  a lock was there but older than --stale-minutes, so it is
                  a dead run's leftover, not a live owner; this process now
                  owns it
  held            a fresh owner is running it; stop, do not start a second

`--wait-seconds` (default 0) is for a cron-fired run that must not skip the
day just because an on-demand copy took the lock a moment earlier (issue
#30): instead of reporting `held` on the first check, it polls once a second
until the lock frees, goes stale, or the budget runs out, whichever comes
first -- so `held` still means "give up," just after actually waiting.

`release` removes the lock; a missing lock is not an error (the run ended
without acquiring, or two releases raced). The lock directory is
`$PT_HOME/run` -- the same scratch space the notes live in, default
/var/lib/hermes/pt.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

DEFAULT_STALE_MINUTES = 120
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def home():
    return pathlib.Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt"))


def lock_path(name):
    return home() / "run" / f"{name}.lock"


def now():
    return datetime.now(timezone.utc).astimezone()


def age_minutes(text):
    """Minutes since the lock was written; None when it cannot be trusted."""
    try:
        stamp = datetime.fromisoformat(text.strip())
    except (ValueError, AttributeError):
        return None
    if stamp.tzinfo is None:
        return None
    return (now() - stamp).total_seconds() / 60.0


def _claim(path, content):
    """Publish path atomically, pre-filled with content -- never an empty file
    a concurrent acquirer could read mid-creation. Written to a temp inode in
    the same directory, then claimed with an exclusive link: link fails if
    path already exists, so exactly one caller among racing claimants wins.
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
        try:
            os.link(tmp_name, path)
            return True
        except FileExistsError:
            return False
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def acquire(name, stale_minutes, wait_seconds=0):
    """Take the lock, waiting out a fresh holder for up to wait_seconds.

    A one-shot on-demand run can win the race against the same day's cron
    fire by a few seconds; without a wait, the scheduled run saw a fresh
    lock and skipped the whole day (issue #30). wait_seconds=0 keeps the
    original one-check behavior.
    """
    path = lock_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = now().isoformat(timespec="seconds") + "\n"
    waited = 0
    while True:
        if _claim(path, content):
            print("acquired")
            return 0
        try:
            text = path.read_text()
        except OSError:
            text = ""
        age = age_minutes(text)
        if age is None or age > stale_minutes:
            # A lock we cannot parse, or one older than the whole run
            # budget, is a dead run's leftover -- taking it over beats
            # blocking the paper forever. A parsed-and-fresh lock is a
            # live owner: held, unless there is still time to wait it out.
            try:
                path.unlink()
            except FileNotFoundError:
                continue  # another process already took it over
            if _claim(path, content):
                print("stale-takeover")
                return 0
            continue  # a fresh claim beat us right after our unlink
        if waited < wait_seconds:
            time.sleep(1)
            waited += 1
            continue
        print("held")
        return 0


def release(name):
    path = lock_path(name)
    try:
        path.unlink()
        print("released")
    except FileNotFoundError:
        print("nothing-to-release")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    acq = sub.add_parser("acquire", help="take the run lock if free")
    acq.add_argument("--name", required=True)
    acq.add_argument("--stale-minutes", type=int, default=DEFAULT_STALE_MINUTES)
    acq.add_argument("--wait-seconds", type=int, default=0)
    acq.set_defaults(func=lambda a: acquire(a.name, a.stale_minutes, a.wait_seconds))

    rel = sub.add_parser("release", help="drop the run lock")
    rel.add_argument("--name", required=True)
    rel.set_defaults(func=lambda a: release(a.name))

    args = parser.parse_args(argv)
    if not NAME_RE.fullmatch(args.name):
        sys.exit(f"error: --name {args.name!r} has characters not allowed in a lock name")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
