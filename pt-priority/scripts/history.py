#!/usr/bin/env python3
"""history.py -- what the advisor's desk printed on recent days, from the wiki.

usage: history.py recent

Prints JSON [{"date", "desk"}], oldest first: the `priority` card each of the
last 7 days' edition pages carries (projects/theplowtimes/editions/<date>.md).
record_edition.py writes those pages only once a paper was delivered, so a card
the owner never received is never history. A day with no page, or no card, is
left out. When the Mac does not answer: `error: history unavailable — <why>`,
non-zero; the desk then runs as if history were empty.

"Today" is the owner's own day, from `owner.timezone` in pt/config.json, not
the container's: register_crons.py no longer requires the two to agree (see
its module docstring), so a page named for the owner's day can be a day off
the container's own date. The container's date is the fallback only when the
config or the key is missing; a config that exists but can't be trusted (bad
JSON, an unreadable file, an unknown zone name) is the same `error: history
unavailable — <why>` above, never a guessed window.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pt-shared" / "scripts"))
from latch_mcp import LatchError
from wiki import EDITIONS, connect, split_page

DAYS = 7


def config_path():
    return Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt")) / "config.json"


def owner_today():
    """The owner's own date -- see the module docstring for why.

    The container's date is the fallback only when the config or the key is
    genuinely absent; a config that exists but can't be trusted (bad JSON,
    an unreadable file, an unknown zone name) refuses instead of guessing --
    a silently wrong seven-day window would read as valid history.
    """
    try:
        config = json.loads(config_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return date.today()
    try:
        tz = config["owner"]["timezone"]
    except (KeyError, TypeError):
        return date.today()
    return datetime.now(ZoneInfo(tz)).date()


def recent(wiki, today):
    out = []
    for back in range(DAYS - 1, -1, -1):
        day = (today - timedelta(days=back)).isoformat()
        text = wiki.read(f"{EDITIONS}/{day}.md")
        card = split_page(text)[0].get("priority") if text else None
        if card:
            out.append({"date": day, "desk": card})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="What the advisor's desk printed lately.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("recent")
    parser.parse_args(argv)
    try:
        print(json.dumps(recent(connect(), owner_today()), ensure_ascii=False))
    except (LatchError, OSError, ValueError, KeyError, TypeError) as exc:
        sys.exit(f"error: history unavailable — {exc}")


if __name__ == "__main__":
    main()
