#!/usr/bin/env python3
"""Refuse a priority the owner could not trace back to their file or calendar.

usage: validate_priority.py --run-dir <dir>
Prints VALID (and stamps notes into priority.json) or INVALID followed by one error per line.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, "/var/lib/hermes/skills/pt-shared/scripts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "pt-shared", "scripts"))
sys.path.insert(0, HERE)
import history  # noqa: E402
import textnorm  # noqa: E402

HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
SOURCE = re.compile(r"^(file|calendar):(\S+)$")
LIST_MARKERS = (";", "\n", "•", " and then ")
MIN_QUOTE_WORDS = 3
LIST_PREFIX = re.compile(r"^\s*(-|\*|\d+\.)\s")


def _load_json(path):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return json.loads(text)


def _write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _schema(context, p):
    errors = []
    if p.get("date") != context["today"]:
        errors.append(f"schema: date must be {context['today']}")
    for field in ("priority", "first_step"):
        if not isinstance(p.get(field), str):
            errors.append(f"schema: {field} must be a string")
    if not isinstance(p.get("why"), list) or not all(isinstance(w, dict) for w in p.get("why") or []):
        errors.append("schema: why must be a list of objects")
    block = p.get("block")
    if block is not None and not (isinstance(block, dict) and all(
            isinstance(block.get(k), str) and HHMM.fullmatch(block[k]) for k in ("start", "end"))):
        errors.append("schema: block must be null or {start, end} in HH:MM")
    if not isinstance(p.get("carried_over"), bool):
        errors.append("schema: carried_over must be a boolean")
    return errors


def validate(context, p, streak=0):
    errors = _schema(context, p)
    if errors:
        return errors
    text = p["priority"].strip()
    if not text:
        errors.append("priority_empty: priority is blank")
    elif len(text) > 120:
        errors.append("priority_too_long: keep it under 120 characters")
    if any(m in p["priority"] for m in LIST_MARKERS) or LIST_PREFIX.match(p["priority"]):
        errors.append("priority_is_list: one priority, not a list")
    step = p["first_step"].strip()
    if not step:
        errors.append("first_step_empty: first_step is blank")
    elif len(step) > 160:
        errors.append("first_step_too_long: keep it under 160 characters")

    why = p["why"]
    if not 1 <= len(why) <= 3:
        errors.append("why_count: give 1 to 3 reasons")
    sections = {s["id"]: s for s in context["file"]["sections"]}
    event_ids = {e["id"] for e in context["calendar"]["events"]}
    for i, item in enumerate(why[:3]):
        m = SOURCE.match(str(item.get("source") or ""))
        if not m:
            errors.append(f"why_source: why[{i}] needs source file:<section-id> or calendar:<event-id>")
            continue
        kind, ref = m.groups()
        if kind == "file":
            if ref not in sections:
                errors.append(f"file_section_not_found: why[{i}] cites '{ref}', known: {sorted(sections)}")
            elif not str(item.get("quote") or "").strip():
                errors.append(f"quote_missing: why[{i}] must quote the section verbatim")
            else:
                quote = textnorm.normalize(item["quote"])
                section_text = textnorm.normalize(sections[ref]["text"])
                if len(quote.split()) < MIN_QUOTE_WORDS and quote != section_text:
                    errors.append(f"quote_too_short: why[{i}] quote needs {MIN_QUOTE_WORDS}+ words, or the whole section")
                elif quote not in section_text:
                    errors.append(f"quote_not_in_section: why[{i}] quote is not in section '{ref}'")
        elif ref not in event_ids:
            errors.append(f"calendar_event_not_found: why[{i}] cites '{ref}'")

    block = p["block"]
    if block is not None:
        fits = block["start"] < block["end"] and any(
            fb["start"] <= block["start"] and block["end"] <= fb["end"]
            for fb in context["calendar"]["free_blocks"])
        if not fits:
            errors.append("block_not_free: block must sit inside one free_block, or be null")

    for section in context["file"]["sections"]:
        if section["kind"] != "not_now":
            continue
        for line in section["text"].splitlines():
            item = line.strip().lstrip("-*").strip()
            if item and textnorm.similar(p["priority"], item):
                errors.append(f"matches_not_now: owner parked '{item}'")
    if streak >= 3:
        errors.append("repeated_3_days: this was #1 for 3 days; choose another and say so in chat")
    return errors


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    run = pathlib.Path(args.run_dir)
    context = _load_json(run / "context.json")
    try:
        priority = _load_json(run / "priority.json")
        if not isinstance(priority, dict):
            raise ValueError
    except ValueError:
        priority = None
    if priority is None:
        print("INVALID\nschema: priority.json unreadable")
        return 0
    streak = history.streak(context["today"] if isinstance(context, dict) else "",
                            priority.get("priority") or "")
    errors = validate(context, priority, streak)
    if errors:
        print("INVALID")
        print("\n".join(errors))
        return 0
    priority["notes"] = context["notes"]
    _write_json(run / "priority.json", priority)
    print("VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
