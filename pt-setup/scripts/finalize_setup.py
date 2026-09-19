#!/usr/bin/env python3
"""finalize_setup.py -- the ONLY way pt-setup writes pt/config.json.

Measured live (2026-09-16): the close step said "**Write**
/var/lib/hermes/pt/config.json from the draft plus those two fields" and
named no command, and nothing in the tree wrote that file. The run had
everything it needed -- printer probed through the AppleScript fallback,
timezone read from the browser, topics saved -- then ran pt_config_gate.py
against a file nobody had created. The gate collapses OSError into "not
valid JSON", so a MISSING file reported as a corrupt one, and the owner was
told the setup "hit a configuration error". Nothing was wrong with the data.

This script is the fix, the same shape record_setup.py is for the draft:
one named command that owns the file, so the close step never has to
improvise a write. It reads the draft, converts the hour, writes the config,
and validates it -- refusing, without leaving a partial file behind, rather
than writing something the gate would reject.

Usage:

    finalize_setup.py <config.json path> --owner-tz <IANA zone>

The zone is step 1's answer (from the browser), unconverted. The hour comes
from the draft and is converted into the container's clock by
convert_delivery.py's own function -- never by hand. Prints CONFIG:written
plus the delivery line on success; on failure prints why, on stderr, and
writes nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "pt-shared" / "scripts"))
import convert_delivery as _convert  # noqa: E402 -- sibling script
import pt_config_gate as _gate  # noqa: E402 -- the contract this must satisfy
import record_setup as _record  # noqa: E402 -- next_question, the completeness rule


def build(draft, owner_tz, container_tz):
    """The config.json body for a completed draft. Pure: no I/O."""
    hour = _convert.convert(draft["local_hour"], owner_tz, container_tz)
    printer = draft.get("printer") or {}
    # owner.language is gate check 7 and what a SCHEDULED edition writes in.
    # pt-intake keeps it current from live chat, but the first paper can land
    # before pt-intake ever runs, so setup plants what it recorded. Absent
    # stays absent -- the gate allows that, and an invented default would be
    # a language nobody chose.
    language = (draft.get("owner") or {}).get("language")
    owner = {"timezone": owner_tz}
    if isinstance(language, str) and language.strip():
        owner["language"] = language.strip()
    config = {
        "owner": owner,
        "delivery": {
            "hour": hour,
            # Kept so a later edit can reason in the owner's own clock
            # rather than re-deriving it from the container's.
            "local_hour": draft["local_hour"],
            "lead_minutes": 0,
        },
        "printer": {
            "configured": bool(printer.get("configured")),
            "name": printer.get("name") if printer.get("configured") else None,
        },
        "mail": {"configured": bool((draft.get("mail") or {}).get("configured"))},
    }
    priority = draft.get("priority") or {}
    if isinstance(priority.get("configured"), bool):
        block = {"configured": bool(priority.get("configured"))}
        if block["configured"]:
            block["file"] = priority.get("file") or "~/Plow/prioritization.md"
        config["priority"] = block
    return config


def main(argv=None):
    argv = sys.argv if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config_path")
    parser.add_argument("--owner-tz", required=True, help="IANA zone from step 1")
    args = parser.parse_args(argv[1:])

    config_path = Path(args.config_path)
    draft_path = config_path.with_name(".setup-draft.json")
    if not draft_path.exists():
        print(
            f"error: no setup draft at {draft_path} -- nothing to finalize",
            file=sys.stderr,
        )
        return 1
    draft = _record.load_draft(draft_path)
    pending = _record.next_question(draft)
    if pending != "close":
        print(
            f"error: setup is not finished (still needs: {pending}); "
            "refusing to write a partial config",
            file=sys.stderr,
        )
        return 1

    container_tz = os.environ.get("TZ", "").strip()
    if not container_tz:
        print(
            "error: the container's TZ is empty -- set TZ in compose.yml's "
            "environment and restart (not AGENT_TZ)",
            file=sys.stderr,
        )
        return 1
    try:
        config = build(draft, args.owner_tz, container_tz)
    except SystemExit as exc:  # convert_delivery exits on a bad hour/zone
        print(str(exc), file=sys.stderr)
        return 1

    # Validated BEFORE it lands: a config the gate would reject must never
    # become the file the daily run reads.
    failures = _gate.gate(config)
    if failures:
        print(f"error: {failures}", file=sys.stderr)
        return 1

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("CONFIG:written")
    print(f"delivery.hour={config['delivery']['hour']} (owner {config['delivery']['local_hour']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
