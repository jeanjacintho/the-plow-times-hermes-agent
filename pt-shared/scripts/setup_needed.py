#!/usr/bin/env python3
"""Print SETUP_NEEDED or READY for the live-chat first-run gate.

SOUL.md tells the model to run this on every owner DM before greeting.
A missing file, unreadable JSON, or any of the three setup keys absent
is SETUP_NEEDED — load pt-setup, do not introduce a general assistant.
READY means the interview already finished; greetings are ordinary turns.

Exit 0 either way so a missing config is not mistaken for a crashed check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_DELIVERY_HOUR_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
CONFIG_FILE = "/var/lib/hermes/pt/config.json"


def setup_needed(path):
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(config, dict):
        return True
    owner = config.get("owner")
    delivery = config.get("delivery")
    printer = config.get("printer")
    tz = owner.get("timezone") if isinstance(owner, dict) else None
    hour = delivery.get("hour") if isinstance(delivery, dict) else None
    configured = printer.get("configured") if isinstance(printer, dict) else None
    if not (isinstance(tz, str) and tz.strip()):
        return True
    if not (isinstance(hour, str) and _DELIVERY_HOUR_RE.fullmatch(hour)):
        return True
    if not isinstance(configured, bool):
        return True
    return False


def main(argv=None):
    argv = sys.argv if argv is None else argv
    path = argv[1] if len(argv) > 1 else CONFIG_FILE
    print("SETUP_NEEDED" if setup_needed(path) else "READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
