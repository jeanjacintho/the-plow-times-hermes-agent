#!/usr/bin/env python3
"""Parse the owner's advisor library into typed, citable sections.

usage: parse_advisors.py <dir-listing.json> <out.json>
dir-listing.json is {"files": [{"name": "...", "text": "..."}]}.
Prints ADVISORS:<n> ERRORS:<n>. README.md and files with no frontmatter
are skipped. Frontmatter without an advisor is an error, never a crash.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

HEADING = re.compile(r"^(#{1,2})\s+(.+?)\s*#*\s*$")
KIND_RULES = (
    ("avoid", re.compile(r"do not focus|avoid|not now")),
    ("focus", re.compile(r"focus first|focus")),
    ("signals", re.compile(r"signal")),
    ("benchmarks", re.compile(r"benchmark|metric")),
    ("exit", re.compile(r"exit criteria|exit")),
)


def _ascii(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def slug(heading):
    return re.sub(r"[^a-z0-9]+", "-", _ascii(heading)).strip("-") or "section"


def kind_of(heading):
    norm = _ascii(heading)
    for kind, pattern in KIND_RULES:
        if pattern.search(norm):
            return kind
    return "other"


def _frontmatter(text):
    if not text.startswith("---"):
        return None, text
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return None, text
    raw, body = rest[:end], rest[end + 4:]
    meta = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip()
    return meta, body.lstrip("\n")


def _sections(body):
    blocks = []
    current = [0, "", []]
    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            blocks.append(current)
            current = [len(m.group(1)), m.group(2), []]
        else:
            current[2].append(line)
    blocks.append(current)
    sections, seen = [], {}
    for level, heading, lines in blocks:
        if level == 0:
            continue
        text = "\n".join(lines).strip()
        if not text:
            continue
        base = slug(heading)
        seen[base] = seen.get(base, 0) + 1
        sid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        sections.append({"id": sid, "kind": kind_of(heading), "heading": heading, "text": text})
    return sections


def _stages(raw):
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def parse(files):
    advisors, errors = [], []
    for item in files or []:
        name = str((item or {}).get("name") or "unknown.md")
        if name.lower() == "readme.md":
            continue
        text = (item or {}).get("text")
        if not isinstance(text, str):
            continue
        meta, body = _frontmatter(text)
        if meta is None:
            continue
        if not str(meta.get("advisor") or "").strip():
            errors.append(f"{name}: missing advisor")
            continue
        advisors.append({
            "file": name,
            "advisor": meta.get("advisor", "").strip(),
            "stages": _stages(meta.get("stages", "")),
            "domain": (meta.get("domain") or "").strip(),
            "source": (meta.get("source") or "").strip(),
            "sections": _sections(body),
        })
    return {"advisors": advisors, "errors": errors}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: parse_advisors.py <dir-listing.json> <out.json>\n")
        return 2
    try:
        payload = json.loads(open(argv[0], encoding="utf-8").read())
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, list):
            files = []
    except (OSError, ValueError):
        files = []
    result = parse(files)
    with open(argv[1], "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"ADVISORS:{len(result['advisors'])} ERRORS:{len(result['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
