#!/usr/bin/env python3
"""record_edition.py -- put a delivered edition into the owner's wiki.

usage: record_edition.py <run/<id>/edition.json>

Run once the chat leg is out (pt-edition), never before: the wiki records what
the owner received. The day's page is projects/theplowtimes/editions/<date>.md;
each edition that day appends one `## HH:MM edition` block: the advisor's card,
then every section the owner chose (anything with a topic_id) with its body,
the evidence its research notes hold (run/<topic_id>/notes.json) and what could
not be sourced. Weather, calendar, mail and sports stay out: they are the day's
reads of the owner's own accounts, and the wiki is every agent's recall.

The page's `priority` frontmatter is the last card printed that day; history.py
reads it back as the desk's history. After the write, `wiki validate` and
`wiki index`, so the paper's page lists the day.

The renderer already refused a malformed edition.json before delivery, so the
fields it requires are read directly.

Prints `RECORDED <page>` or `SKIPPED: <why>`. A failure exits non-zero with
`error: edition not recorded — <why>`; the delivery it follows still stands.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pt-shared" / "scripts"))
from bearer_http import require
from latch_mcp import LatchError
from wiki import EDITIONS, PAPER_LINK, connect, join_page, split_page
from wiki_setup import ensure

MARK = "<!-- edition {} -->"
CARD_LINES = (("First step", "first_step"), ("Stage", "stage_label"), ("Why this stage", "stage_why"),
              ("Yesterday", "yesterday"), ("This week", "week"), ("Draft", "draft"))


def _card(card):
    lines = ["### The advisor's desk", "", f"**{card['headline']}**", ""]
    lines += [f"- {label}: {card[key]}" for label, key in CARD_LINES if card.get(key)]
    lines += [f"- Who: {who}" for who in card.get("who") or []]
    lines += [f"- Not today: {item}" for item in card.get("not_today") or []]
    for why in card.get("why") or []:
        quote = f' "{why["quote"]}"' if why.get("quote") else ""
        lines.append(f"- Why: {why['text']}{quote} ({why['source_label']})")
    return lines + [""]


def _section(section, notes):
    lines = [f"### {section['title']}", ""]
    if section.get("headline"):
        lines += [f"**{section['headline']}**", ""]
    lines += [section["body"], ""]
    lines += [f"- {note['claim']} ({note['url']})" for note in notes.get("notes") or []]
    lines += [f"- Could not source: {gap}" for gap in notes.get("could_not_source") or []]
    return lines + [""]


def record(wiki, edition_json, chat, now):
    run_dir = Path(edition_json).parent
    edition = json.loads(Path(edition_json).read_text(encoding="utf-8"))
    sections = edition.get("sections") or []
    printed = next((s for s in sections if s.get("desk") == "priority"), None)
    news = [s for s in sections if s.get("topic_id")]
    if printed is None and not news:
        return "SKIPPED: no advisor's card and no section of the owner's"
    rel = f"{EDITIONS}/{edition['date']}.md"
    mark = MARK.format(run_dir.name)
    ensure(wiki, chat)
    existing = wiki.read(rel)
    if existing is not None and mark in existing:
        return f"SKIPPED: {rel} already has this edition"

    lines, urls = [f"## {now:%H:%M} edition", mark, ""], []
    card = {**printed["priority"], "headline": printed["headline"]} if printed else None
    if card:
        lines += _card(card)
        urls += [why["url"] for why in card.get("why") or [] if why.get("url")]
    for section in news:
        path = run_dir.parent / section["topic_id"] / "notes.json"
        notes = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        lines += _section(section, notes)
        urls += [note["url"] for note in notes.get("notes") or []]
        urls += [u for u in section.get("sources") or [] if u.startswith("http")]

    if existing is None:
        meta = {"type": "Edition", "title": f"The Founder Times, {edition['date']}",
                "description": "", "category": "projects", "tags": ["edition"],
                "paper": PAPER_LINK, "date": edition["date"], "sources": [],
                "created": now.isoformat(timespec="seconds")}
        body = f"# The Founder Times, {edition['date']}\n"
    else:
        meta, body = split_page(existing)
    cited = {s["resource"] for s in meta["sources"]}
    meta["sources"] += [{"resource": u} for u in dict.fromkeys(urls) if u not in cited]
    meta["sources"] = meta["sources"] or [{"resource": f"plow-chat:{chat}"}]
    meta["description"] = card["headline"] if card else (news[0].get("headline") or news[0]["title"])
    if card:
        meta["priority"] = card
    meta["updated"] = now.isoformat(timespec="seconds")
    wiki.write(rel, join_page(meta, body.rstrip("\n") + "\n\n" + "\n".join(lines)))
    wiki.check()
    return f"RECORDED {rel}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Put a delivered edition into the owner's wiki.")
    parser.add_argument("edition_json")
    args = parser.parse_args(argv)
    try:
        print(record(connect(), args.edition_json, require("PLOW_HOME_CHANNEL"),
                     datetime.now().astimezone()))
    except LatchError as exc:
        sys.exit(f"error: edition not recorded — {exc}")


if __name__ == "__main__":
    main()
