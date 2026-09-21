#!/usr/bin/env python3
"""history.py -- what this paper printed on recent days, from the wiki.

usage: history.py recent [--topic <topic_id>]

Prints JSON, oldest first, for the 7 days before today, reading the edition
pages record_edition.py writes (projects/theplowtimes/editions/<date>.md).
Bare, it is the advisor's desk's own history: [{"date", "desk"}], the
`priority` card each day carries. With `--topic`, it is one news section's:
[{"date", "headline", "printed": [{"claim", "url"}]}], every block that
section's topic id marks on the page, so the next pass knows which sources
it has already spent and which claims it has already made -- a section with
no memory reprints the same story every morning (issue #69).
Today's own page is never history: a second edition for the same date would
otherwise read the first back as "yesterday".
record_edition.py writes those pages only once a paper was delivered, so a card
the owner never received is never history. A day with no page, or no card, is
left out. When the Mac does not answer: `error: history unavailable — <why>`,
non-zero; the desk then runs as if history were empty.

"Today" is the owner's own day (`owner_time.owner_today()`), not the
container's -- see that module's docstring for why, and for the same
`error: history unavailable — <why>` refusal on a config that can't be
trusted rather than a guessed window.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pt-shared" / "scripts"))
from latch_mcp import LatchError
from owner_time import owner_today
from wiki import EDITIONS, SECTION_MARK, connect, split_page

DAYS = 7
HEADING_RE = re.compile(r"^#{2,3} ", re.M)
HEADLINE_RE = re.compile(r"^\*\*(.+)\*\*$", re.M)
CLAIM_RE = re.compile(r"^- (.+?) \((https?://\S+)\)$", re.M)


def _desk(text):
    """The advisor's card the page carries, or None."""
    card = split_page(text)[0].get("priority")
    return {"desk": card} if card else None


def _section(text, topic):
    """What this section printed on the page: its last headline and every
    sourced claim, both editions of the day included, or None if it is absent."""
    blocks = [HEADING_RE.split(chunk, maxsplit=1)[0]
              for chunk in split_page(text)[1].split(SECTION_MARK.format(topic))[1:]]
    if not blocks:
        return None
    headlines = [m.group(1).strip() for block in blocks
                 for m in [HEADLINE_RE.search(block)] if m]
    return {"headline": headlines[-1] if headlines else "",
            "printed": [{"claim": claim.strip(), "url": url}
                        for block in blocks for claim, url in CLAIM_RE.findall(block)]}


def recent(wiki, today, topic=None):
    out = []
    for back in range(DAYS, 0, -1):
        day = (today - timedelta(days=back)).isoformat()
        text = wiki.read(f"{EDITIONS}/{day}.md")
        entry = (_section(text, topic) if topic else _desk(text)) if text else None
        if entry:
            out.append({"date": day, **entry})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="What this paper printed lately: the advisor desk's cards, or one news section's blocks.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    recent_parser = sub.add_parser("recent")
    recent_parser.add_argument("--topic", help="a news section's topic id, instead of the desk's cards")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(recent(connect(), owner_today(), args.topic), ensure_ascii=False))
    except (LatchError, OSError, ValueError, KeyError, TypeError) as exc:
        sys.exit(f"error: history unavailable — {exc}")


if __name__ == "__main__":
    main()
