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
  release --name NAME --token TOKEN

`acquire` prints one word, then -- when it now owns the lock -- a second
`token:<token>` line, and always exits 0, so a cron-fired session reads the
decision instead of a status code:

  acquired        this process owns the run; release it (with the printed
                  token) when done
  stale-takeover  a lock was there but older than --stale-minutes, so it is
                  a dead run's leftover, not a live owner; this process now
                  owns it (with a fresh token)
  held            a fresh owner is running it; stop, do not start a second
                  -- no token line, there is nothing to release

`--wait-seconds` (default 0) is for a cron-fired run that must not skip the
day just because an on-demand copy took the lock a moment earlier (issue
#30): instead of reporting `held` on the first check, it polls once a second
until the lock frees, goes stale, or the budget runs out, whichever comes
first -- so `held` still means "give up," just after actually waiting.

`release --token TOKEN` removes the lock only when TOKEN matches the token
the lock currently holds -- a run whose own stale-takeover cutoff has
passed can still be alive and call release after a successor's
stale-takeover already claimed the name; without an owner check that call
deletes the successor's lock by name alone, and a third run can then start
while the successor is still working (srosro-review on ee74125). A missing
lock or a token mismatch is not an error (the run ended without acquiring,
two releases raced, or this is exactly that stale caller); either way
nothing is deleted out from under a current owner. The lock directory is
`$PT_HOME/run` -- the same scratch space the notes live in, default
/var/lib/hermes/pt.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import os
import pathlib
import re
import secrets
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
    """Minutes since the lock was written; None when it cannot be trusted.

    The timestamp is always the lock content's first line -- a claim token
    may follow on a second line, but staleness never depends on it.
    """
    try:
        stamp = datetime.fromisoformat(text.splitlines()[0].strip())
    except (ValueError, AttributeError, IndexError):
        return None
    if stamp.tzinfo is None:
        return None
    return (now() - stamp).total_seconds() / 60.0


def _read_token(text):
    """The claim token on a lock's second line, or None (malformed or
    missing -- a caller with no token to prove is never treated as owner)."""
    lines = text.splitlines()
    return lines[1].strip() if len(lines) > 1 and lines[1].strip() else None


def _mutex_path(name):
    return home() / "run" / f".{name}.mutex"


@contextlib.contextmanager
def _serialized(name):
    """Serialize one name's claim/read/unlink/reclaim transition, and its
    release, across concurrent processes with an advisory flock on a
    per-name mutex file.

    ``_claim()`` alone makes publishing a lock atomic, but not the decision
    that leads to it: two processes can each read the same stale lock, each
    ``unlink()`` it (the second's unlink racing the first's already-published
    replacement, deleting it instead of a stale leftover), and each reclaim
    the now-free path, both returning ``stale-takeover`` (srosro-review on
    b51e064). Held only around that decision, never around the wait-seconds
    sleep between attempts, so concurrent waiters still poll independently.
    """
    path = _mutex_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


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


def _attempt(path, content, stale_minutes):
    """One serialized claim/read/unlink/reclaim transition. Returns
    ``"acquired"``, ``"stale-takeover"``, ``"fresh"`` (a live owner holds
    it), or ``"retry"`` (the state moved under us -- another process already
    took the stale lock over or reclaimed the path we just freed; loop
    again immediately, no wait budget spent).
    """
    if _claim(path, content):
        return "acquired"
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
            return "retry"
        if _claim(path, content):
            return "stale-takeover"
        return "retry"
    return "fresh"


def acquire(name, stale_minutes, wait_seconds=0):
    """Take the lock, waiting out a fresh holder for up to wait_seconds.

    A one-shot on-demand run can win the race against the same day's cron
    fire by a few seconds; without a wait, the scheduled run saw a fresh
    lock and skipped the whole day (issue #30). wait_seconds=0 keeps the
    original one-check behavior.
    """
    path = lock_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    waited = 0
    while True:
        # Built fresh on every attempt, not once before the wait loop: a
        # waiter that sleeps up to wait_seconds before finally claiming
        # would otherwise stamp the lock with when it started waiting, not
        # when it actually claimed it -- understating its own age against
        # --stale-minutes and letting a concurrent acquirer take it over
        # before this run's real lifetime is up (srosro-review on a6508a0).
        token = secrets.token_hex(8)
        content = now().isoformat(timespec="seconds") + "\n" + token + "\n"
        with _serialized(name):
            result = _attempt(path, content, stale_minutes)
        if result in ("acquired", "stale-takeover"):
            print(result)
            print(f"token:{token}")
            return 0
        if result == "retry":
            continue
        if waited < wait_seconds:
            time.sleep(1)
            waited += 1
            continue
        print("held")
        return 0


def release(name, token):
    """Drop the lock, but only when token matches its current claim.

    Without this check, a run past its own stale-takeover cutoff can still
    call release after a successor already reclaimed the name -- unlinking
    by name alone would delete the successor's lock, not this run's own
    (srosro-review on ee74125).
    """
    path = lock_path(name)
    with _serialized(name):
        try:
            text = path.read_text()
        except FileNotFoundError:
            print("nothing-to-release")
            return 0
        if _read_token(text) != token:
            print("not-owner")
            return 0
        path.unlink()
        print("released")
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
    rel.add_argument("--token", required=True)
    rel.set_defaults(func=lambda a: release(a.name, a.token))

    args = parser.parse_args(argv)
    if not NAME_RE.fullmatch(args.name):
        sys.exit(f"error: --name {args.name!r} has characters not allowed in a lock name")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
