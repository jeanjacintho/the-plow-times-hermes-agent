#!/usr/bin/env python3
"""Split the owner's prioritization.md into typed sections. Deterministic, no model.

usage: parse_priority_file.py <raw.md> <out.json>
Prints "FILE:<ok|missing|empty> SECTIONS:<n>". A missing <raw.md> is status "missing".
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

KINDS = ("goals", "projects", "advice", "rules", "not_now", "other")
MAX_BYTES = 32 * 1024
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING = re.compile(r"^(#{1,2})\s+(.+?)\s*#*\s*$")
KIND_RULES = (
    ("not_now", re.compile(r"not now|ignore|agora nao|ignorar")),
    ("goals", re.compile(r"goal|objetivo|meta")),
    ("projects", re.compile(r"project|deadline|projeto|prazo")),
    ("advice", re.compile(r"advice|conselho|mentor|investor|investidor")),
    ("rules", re.compile(r"rule|regra")),
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


def _truncate(text):
    raw = text.encode("utf-8")
    if len(raw) <= MAX_BYTES:
        return text, False
    return raw[:MAX_BYTES].decode("utf-8", "ignore"), True


def parse(text):
    if text is None:
        return {"status": "missing", "truncated": False, "sections": []}
    if text.startswith("\ufeff"):
        text = text[1:]
    text, truncated = _truncate(COMMENT.sub("", text))
    blocks = []  # [level, heading, lines]
    current = [0, "", []]
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            blocks.append(current)
            current = [len(m.group(1)), m.group(2), []]
        else:
            current[2].append(line)
    blocks.append(current)

    sections, seen = [], {}
    first_heading = True
    for level, heading, lines in blocks:
        body = "\n".join(lines).strip()
        if level == 0:
            if body:
                sections.append({"id": "preamble", "kind": "other", "heading": "", "text": body})
            continue
        is_title = first_heading and level == 1
        first_heading = False
        if not body:
            continue  # empty sections, including a bare title, are dropped
        base = slug(heading)
        seen[base] = seen.get(base, 0) + 1
        sid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        sections.append({"id": sid, "kind": "other" if is_title else kind_of(heading),
                         "heading": heading, "text": body})
    return {"status": "ok" if sections else "empty", "truncated": truncated, "sections": sections}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: parse_priority_file.py <raw.md> <out.json>\n")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        text = None
    result = parse(text)
    with open(argv[1], "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"FILE:{result['status']} SECTIONS:{len(result['sections'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
