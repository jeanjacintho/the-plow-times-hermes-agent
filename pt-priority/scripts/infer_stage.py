#!/usr/bin/env python3
"""Infer company stage from the parsed prioritization file. Deterministic, no model.

usage: infer_stage.py <file.json> <out.json>
Prints STAGE:<stage> MODIFIERS:<list|none>.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

STAGE_HEADING = re.compile(r"company state|estado da empresa", re.I)
ARR_UNIT = re.compile(
    r"(?:arr[:\s]+(?:r\$|us\$|\$)?|(?:r\$|us\$|\$))\s*(\d+(?:[.,]\d+)?)\s*([mkb])\b",
    re.I,
)
ARR_PLAIN_M = re.compile(
    r"(?<![A-Za-z0-9])(\d+(?:[.,]\d+)?)\s*([mb])(?:\s*arr)?\b",
    re.I,
)
ARR_ZERO = re.compile(r"\$0\b|0 revenue", re.I)
REF_RE = re.compile(
    r"(\d+)\s+(?:referenceable|clientes referenciaveis)",
    re.I,
)
PIVOT_RE = re.compile(
    r"\bpivot\b|down round|security incident|missed milestone|\blayoff\b|missed q\d",
    re.I,
)
FUND_RE = re.compile(r"\braising\b|captando|term sheet", re.I)
CONSUMER_RE = re.compile(r"consumer|\bb2c\b|\bplg\b|self-serve|self serve", re.I)
LABELS = {
    "discovery": "Discovery ($0–1M ARR)",
    "blueprint": "Blueprint ($1–10M ARR)",
    "scale": "Scale ($10M+ ARR)",
    "pivot": "Pivot",
    "unknown": "Stage unknown",
}


def _ascii(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()


def _state_text(parsed):
    sections = (parsed or {}).get("sections") or []
    for section in sections:
        if section.get("id") == "company-state":
            return section.get("text") or ""
        if STAGE_HEADING.search(section.get("heading") or ""):
            return section.get("text") or ""
    return ""


def _to_millions(number, unit):
    n = float(number.replace(",", "."))
    unit = unit.lower()
    if unit == "k":
        return n / 1000.0
    if unit == "b":
        return n * 1000.0
    return n


def _arr_millions(text):
    match = ARR_UNIT.search(text)
    if match:
        return _to_millions(match.group(1), match.group(2))
    plain = ARR_PLAIN_M.search(text)
    if plain:
        return _to_millions(plain.group(1), plain.group(2))
    if ARR_ZERO.search(text):
        return 0.0
    return None


def _referenceable(text):
    match = REF_RE.search(_ascii(text))
    return int(match.group(1)) if match else None


def _band(arr, refs):
    if arr is not None:
        if arr < 1:
            return "discovery"
        if arr < 10:
            return "blueprint"
        return "scale"
    if refs is None:
        return "unknown"
    if refs < 5:
        return "discovery"
    return "blueprint"


BAND_WHY = {
    "discovery": "$0–1M",
    "blueprint": "$1–10M",
    "scale": "$10M+",
}


def infer(parsed):
    text = _state_text(parsed)
    arr = _arr_millions(text)
    refs = _referenceable(text)
    stage = _band(arr, refs)
    if PIVOT_RE.search(text):
        stage = "pivot"
    modifiers = []
    if FUND_RE.search(text):
        modifiers.append("fundraising")
    domain = "consumer-plg" if CONSUMER_RE.search(text) else "unknown"
    if domain != "consumer-plg" and (arr is not None or refs is not None):
        domain = "b2b-saas"
    signals = []
    if arr is not None:
        if arr == 0:
            signals.append("arr=0")
        elif arr == int(arr):
            signals.append(f"arr={int(arr)}M")
        else:
            signals.append(f"arr={arr:g}M")
    if refs is not None:
        signals.append(f"referenceable={refs}")
    if stage == "unknown":
        why = "no ARR or referenceable count in Company state"
    elif stage == "pivot":
        why = "explicit shock in Company state overrides the ARR band"
    elif arr is not None:
        why = f"ARR {signals[0].split('=', 1)[1]} is the {BAND_WHY.get(stage, stage)} band"
    else:
        why = f"{refs} referenceable customers"
    return {
        "stage": stage,
        "modifiers": modifiers,
        "domain": domain,
        "signals": signals,
        "why": why,
        "label": LABELS[stage],
    }


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: infer_stage.py <file.json> <out.json>\n")
        return 2
    try:
        parsed = json.loads(open(argv[0], encoding="utf-8").read())
        if not isinstance(parsed, dict):
            parsed = {"sections": []}
    except (OSError, ValueError):
        parsed = {"sections": []}
    result = infer(parsed)
    with open(argv[1], "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    mods = ",".join(result["modifiers"]) or "none"
    print(f"STAGE:{result['stage']} MODIFIERS:{mods}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
