#!/usr/bin/env python3
"""print_edition.py -- the paper edition's Latch leg, from disk, not the model.

Measured live 2026-09-17: pt-print told the model to `cat` edition.html and
paste that ~43k page into plow_write_file's `content`. The LLM stream died
mid tool-call (RemoteProtocolError: incomplete chunked read); `lp` never
ran. The chat PDF still arrived because post_to_chat.py reads the file
itself. This script is that same shape for paper.

A later run that DID reach `lp` failed because the CUPS queue refused HTML
(`Unsupported document-format "text/html"` on JornalVirtual). The file
shipped is edition.pdf, the one the chat already got. Latch write_file is
text, so the PDF rides as base64 and is decoded on the Mac before `lp`.

Usage:

    print_edition.py <edition.pdf> <config.json>

Date comes from sibling edition.json. Skips with exit 0 when
printer.configured is not true. Any real Latch or `lp` failure exits
non-zero with `page not printed` in the message.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shlex
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent / "pt-shared" / "scripts"))
from latch_mcp import LatchError, connect, require_command_result

PATH_RE = re.compile(
    r"(/Users/[^\s'\"]+/Plow/pt/edition-[0-9-]+\.pdf(?:\.b64)?)"
)


def printer_name(config_path):
    """CUPS name when printer.configured is exactly true; else None (skip)."""
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(cfg, dict):
        return None
    printer = cfg.get("printer") or {}
    if not isinstance(printer, dict) or printer.get("configured") is not True:
        return None
    name = printer.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def read_pdf(path):
    try:
        data = Path(path).read_bytes()
    except OSError:
        sys.exit(f"error: pdf path cannot be read: {path}")
    if not data:
        sys.exit(f"error: pdf is empty: {path}")
    return data


def edition_date(pdf_path):
    sibling = Path(pdf_path).resolve().parent / "edition.json"
    try:
        data = json.loads(sibling.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        sys.exit(f"error: sibling edition.json has no date: {sibling}")
    date = data.get("date") if isinstance(data, dict) else None
    if not isinstance(date, str) or not date.strip():
        sys.exit(f"error: sibling edition.json has no date: {sibling}")
    return date.strip()


def mac_pdf_path(date):
    return f"~/Plow/pt/edition-{date}.pdf"


def mac_b64_path(date):
    return f"~/Plow/pt/edition-{date}.pdf.b64"


def pdf_path_from_b64(b64_path):
    if b64_path.endswith(".b64"):
        return b64_path[:-4]
    return b64_path


def written_path(parsed):
    candidates = []
    if isinstance(parsed, dict):
        for key in ("path", "absolute_path", "file", "wrote"):
            if parsed.get(key):
                candidates.append(parsed[key])
        if parsed.get("raw"):
            candidates.append(parsed["raw"])
    else:
        candidates.append(parsed)
    blob = " ".join(str(c) for c in candidates)
    match = PATH_RE.search(blob)
    if match:
        return match.group(1)
    if candidates:
        first = str(candidates[0])
        if first.startswith("/"):
            return first
    sys.exit("error: page not printed — write did not return a Mac path")


def is_bfd(parsed):
    blob = json.dumps(parsed) if not isinstance(parsed, str) else parsed
    return "bad file descriptor" in blob.lower()


def require_finished_ok(parsed, step, call_tool=None):
    """Refuse a Latch run that never reported exit_code 0.

    A run that outlives Latch's wait_ms is polled to its exit; one that never
    reports it prints 'outcome unknown' rather than 'page printed' (issue #35)
    or a failure the job may still contradict.
    """
    try:
        code, output = require_command_result(parsed, call_tool)
    except LatchError as exc:
        sys.exit(f"error: page may not have printed — {step} outcome unknown: {exc}; "
                 "check the printer queue")
    if code:
        sys.exit(f"error: page not printed — {step} {code}: {output or parsed}")


def require_lp_ok(parsed, call_tool=None):
    require_finished_ok(parsed, "lp", call_tool)


def ship(pdf_path, printer, date, call_tool):
    pdf = read_pdf(pdf_path)
    dest_b64 = mac_b64_path(date)

    wrote = call_tool(
        "plow_write_file",
        {"path": dest_b64, "content": base64.b64encode(pdf).decode("ascii")},
    )
    abs_b64 = written_path(wrote)
    abs_pdf = pdf_path_from_b64(abs_b64)
    decoded = call_tool(
        "plow_run_command",
        {
            "argv": ["base64", "-D", "-i", abs_b64, "-o", abs_pdf],
            "read_paths": [abs_b64],
            "write_paths": [abs_pdf],
            "goal": "Decode the edition PDF on the owner's Mac",
        },
    )
    require_finished_ok(decoded, "base64", call_tool)
    lp = call_tool(
        "plow_run_command",
        {
            "argv": ["lp", "-d", printer, abs_pdf],
            "network": True,
            "read_paths": [abs_pdf],
            "goal": "Print today's Founder Times edition",
        },
    )
    if is_bfd(lp):
        cmd = f"lp -d {shlex.quote(printer)} {shlex.quote(abs_pdf)}"
        lp = call_tool(
            "plow_run_applescript",
            {
                "app": "System Events",
                "script": f"do shell script {json.dumps(cmd)}",
                "goal": "Print today's Founder Times edition (sandboxed lp failed)",
            },
        )
    require_lp_ok(lp, call_tool)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write the edition PDF to the owner's Mac and print it."
    )
    parser.add_argument("pdf")
    parser.add_argument("config")
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    printer = printer_name(args.config)
    if not printer:
        print("skipped: printer.configured is not true")
        return
    date = args.date or edition_date(args.pdf)
    if args.dry_run:
        print(f"dry-run: would write {mac_pdf_path(date)} and lp -d {printer}")
        return

    try:
        ship(args.pdf, printer, date, connect().call_tool)
    except LatchError as exc:
        sys.exit(f"error: page not printed — {exc}")
    print(f"page printed on {printer}")


if __name__ == "__main__":
    main()
