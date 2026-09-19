#!/usr/bin/env python3
"""wiki_setup.py -- make the owner's wiki ready for The Founder Times.

usage: wiki_setup.py [--desk]

Idempotent and cheap when there is nothing to do (a few page reads), so every
caller runs it: pt-setup when the advisor's desk is turned on, the desk before
each daily pass (--desk), and record_edition.py before it writes.

  - no ~/Plow/wiki          -> `wiki init ~/Plow/wiki` through Latch's plugin
  - the paper's schema and page, when absent, from pt-shared/assets/wiki/
  - with --desk: entities/owner/goals.md and projects/theplowtimes/advisor.md,
    when absent. An install from before the wiki carries over once: the body
    of ~/Plow/prioritization.md (the old file stays; it is the owner's) and of
    /var/lib/hermes/pt/advisor.md (deleted once carried).
  - projects/theplowtimes declared in wiki.toml, appended last so a run that
    failed halfway runs again; no other line of the file is touched.

Prints WIKI:ready or `WIKI:set up <what>`. Any failure exits non-zero with
`error: wiki not ready — <why>`.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

from bearer_http import require
from latch_mcp import LatchError
from wiki import ADVISOR_PAGE, GOALS, OVERVIEW, ROOT, SCHEMA, WIKI, WRITER, connect, join_page, split_page

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "wiki"
PT_HOME = Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt"))
LEGACY_NOTES = "~/Plow/prioritization.md"


def _seed(wiki, rel, asset, chat, old=lambda: None):
    """Write `rel` from its seed when the wiki lacks it; `old()` is a body to carry over."""
    if wiki.read(rel) is not None:
        return []
    text = (ASSETS / asset).read_text(encoding="utf-8")
    text = text.replace("{today}", datetime.date.today().isoformat()).replace("{chat}", chat)
    body = old()
    if body is not None:
        text = join_page(split_page(text)[0], body)
    wiki.write(rel, text)
    return [rel]


def ensure(wiki, chat, desk=False, pt_home=PT_HOME):
    did = []
    toml = wiki.read("wiki.toml")
    if toml is None:
        code, out = wiki.run("init", WIKI, write=True)
        if code != 0:
            raise LatchError(f"wiki init: {out.strip()}")
        toml = wiki.read("wiki.toml")
        did.append(WIKI)
    did += _seed(wiki, SCHEMA, "schema.md", chat)
    did += _seed(wiki, OVERVIEW, "overview.md", chat)
    if desk:
        did += _seed(wiki, GOALS, "goals.md", chat, lambda: wiki.read_path(LEGACY_NOTES))
        local = pt_home / "advisor.md"
        old = local.read_text(encoding="utf-8") if local.exists() else None
        carried = _seed(wiki, ADVISOR_PAGE, "advisor.md", chat, lambda: old)
        if carried:
            local.unlink(missing_ok=True)
        did += carried
    if f'[roots."{ROOT}"]' not in toml:
        wiki.write("wiki.toml", f'{toml.rstrip()}\n\n[roots."{ROOT}"]\nwriter = "{WRITER}"\n')
        did.append(f"{ROOT} in wiki.toml")
    return did


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make the owner's wiki ready for the paper.")
    parser.add_argument("--desk", action="store_true",
                        help="also the advisor's desk's pages (goals, the desk's page)")
    args = parser.parse_args(argv)
    try:
        did = ensure(connect(), require("PLOW_HOME_CHANNEL"), desk=args.desk)
    except LatchError as exc:
        sys.exit(f"error: wiki not ready — {exc}")
    print("WIKI:" + ("ready" if not did else "set up " + ", ".join(did)))


if __name__ == "__main__":
    main()
