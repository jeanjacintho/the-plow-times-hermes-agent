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
ADVISOR_SOURCE = re.compile(r"^advisor:([^#\s]+)#(\S+)$")
LIST_MARKERS = (";", "\n", "•", " and then ")
MIN_QUOTE_WORDS = 3
MAX_QUOTE_WORDS = 25
LIST_PREFIX = re.compile(r"^\s*(-|\*|\d+\.)\s")
FOUNDER_TALK = re.compile(
    r"\b("
    r"the founder|o fundador|a fundadora|"
    r"founder should|fundador deve|fundadora deve|"
    r"the ceo should|o ceo deve"
    r")\b",
    re.I,
)


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
    expected_stage = _context_stage(context)
    if expected_stage is not None and p.get("stage") != expected_stage:
        errors.append(f"schema: stage must be {expected_stage}")
    return errors


def _context_stage(context):
    stage = context.get("stage")
    if isinstance(stage, dict):
        return stage.get("stage")
    if isinstance(stage, str):
        return stage
    return None


def _advisor_index(context):
    found = {}
    for advisor in context.get("advisors") or []:
        fname = advisor.get("file")
        for section in advisor.get("sections") or []:
            found[(fname, section.get("id"))] = section
    return found


def _quote_errors(i, item, haystack):
    errors = []
    quote_raw = str(item.get("quote") or "").strip()
    if not quote_raw:
        errors.append(f"quote_missing: why[{i}] must quote the section verbatim")
        return errors
    if len(quote_raw.split()) > MAX_QUOTE_WORDS:
        errors.append(f"quote_too_long: why[{i}] quote is over {MAX_QUOTE_WORDS} words")
    quote = textnorm.normalize(item["quote"])
    section_text = textnorm.normalize(haystack)
    if len(quote.split()) < MIN_QUOTE_WORDS and quote != section_text:
        errors.append(f"quote_too_short: why[{i}] quote needs {MIN_QUOTE_WORDS}+ words, or the whole section")
    elif quote not in section_text:
        errors.append(f"quote_not_in_section: why[{i}] quote is not in the cited section")
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
    spoken = [text, step]
    for item in (p.get("why") or []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            spoken.append(item["text"])
    if any(FOUNDER_TALK.search(s or "") for s in spoken):
        errors.append(
            "talks_about_the_founder: speak to the reader (you / você), "
            "never 'the founder should'"
        )

    why = p["why"]
    if not 1 <= len(why) <= 3:
        errors.append("why_count: give 1 to 3 reasons")
    sections = {s["id"]: s for s in context["file"]["sections"]}
    event_ids = {e["id"] for e in context["calendar"]["events"]}
    advisor_sections = _advisor_index(context)
    kinds_seen = []
    for i, item in enumerate(why[:3]):
        source = str(item.get("source") or "")
        m = SOURCE.match(source)
        adv = ADVISOR_SOURCE.match(source)
        if m:
            kind, ref = m.groups()
            kinds_seen.append(kind)
            if kind == "file":
                if ref not in sections:
                    errors.append(f"file_section_not_found: why[{i}] cites '{ref}', known: {sorted(sections)}")
                else:
                    errors.extend(_quote_errors(i, item, sections[ref]["text"]))
            elif ref not in event_ids:
                errors.append(f"calendar_event_not_found: why[{i}] cites '{ref}'")
        elif adv:
            kinds_seen.append("advisor")
            fname, sid = adv.groups()
            section = advisor_sections.get((fname, sid))
            if section is None:
                errors.append(f"advisor_section_not_found: why[{i}] cites '{fname}#{sid}'")
            else:
                errors.extend(_quote_errors(i, item, section["text"]))
        else:
            errors.append(f"why_source: why[{i}] needs source file:<section-id>, calendar:<event-id> or advisor:<file>#<section-id>")
    calendar_only = kinds_seen and not any(k in ("file", "advisor") for k in kinds_seen)
    if 1 <= len(why) <= 3 and calendar_only and not any(
            e.startswith("calendar_event_not_found:") for e in errors):
        errors.append("why_needs_file_or_advisor: at least one why must cite the file or an advisor")

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
            if item and textnorm.similar(p["priority"], item, textnorm.AVOID_THRESHOLD):
                errors.append(f"matches_not_now: owner parked '{item}'")
    for advisor in context.get("advisors") or []:
        for section in advisor.get("sections") or []:
            if section.get("kind") != "avoid":
                continue
            for line in section.get("text", "").splitlines():
                item = line.strip().lstrip("-*").strip()
                if item and textnorm.similar(p["priority"], item, textnorm.AVOID_THRESHOLD):
                    errors.append(f"matches_stage_avoid: stage says not '{item}'")
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
