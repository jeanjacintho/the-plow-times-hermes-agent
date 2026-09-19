#!/usr/bin/env python3
"""history.py -- what the advisor's desk printed on recent days, from the wiki.

usage: history.py recent [--days 7]

Prints JSON [{"date", "desk"}], oldest first: the `priority` card each of the
last N days' edition pages carries (projects/theplowtimes/editions/<date>.md).
record_edition.py writes those pages only once a paper was delivered, so a card
the owner never received is never history. A day with no page, or no card, is
left out. When the Mac does not answer: `error: history unavailable — <why>`,
non-zero; the desk then runs as if history were empty.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pt-shared" / "scripts"))
from latch_mcp import LatchError
from wiki import EDITIONS, connect, split_page


def recent(wiki, today, days=7):
    out = []
    for back in range(days - 1, -1, -1):
        day = (today - timedelta(days=back)).isoformat()
        text = wiki.read(f"{EDITIONS}/{day}.md")
        card = split_page(text)[0].get("priority") if text else None
        if card:
            out.append({"date": day, "desk": card})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="What the advisor's desk printed lately.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("recent").add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(recent(connect(), date.today(), args.days), ensure_ascii=False))
    except LatchError as exc:
        sys.exit(f"error: history unavailable — {exc}")


if __name__ == "__main__":
    main()
