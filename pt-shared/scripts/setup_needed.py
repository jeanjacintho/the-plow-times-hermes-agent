#!/usr/bin/env python3
"""Print SETUP_NEEDED or READY for the live-chat first-run gate.

SOUL.md tells the model to run this on every owner DM before greeting.
A missing file, unreadable JSON, or any of the three setup keys absent
is SETUP_NEEDED — load pt-setup, do not introduce a general assistant.
READY means the interview already finished; greetings are ordinary turns.

When SETUP_NEEDED, a second line names what `.setup-draft.json` already
holds (or DRAFT:none). Chat history is not progress: a wiped session
still shows old printer/mail turns in the Plow thread.

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


def draft_line(config_path):
    """Second gate line: which interview fields the draft already holds."""
    draft_path = Path(config_path).with_name(".setup-draft.json")
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "DRAFT:none"
    if not isinstance(draft, dict):
        return "DRAFT:none"
    fields = []
    hour = draft.get("local_hour")
    if isinstance(hour, str) and hour.strip():
        fields.append("local_hour")
    printer = draft.get("printer")
    if isinstance(printer, dict) and isinstance(printer.get("configured"), bool):
        fields.append("printer")
    priority = draft.get("priority")
    if isinstance(priority, dict) and isinstance(priority.get("configured"), bool):
        fields.append("priority")
    mail = draft.get("mail")
    if isinstance(mail, dict) and isinstance(mail.get("configured"), bool):
        fields.append("mail")
    elif isinstance(draft.get("mail.configured"), bool):
        fields.append("mail")
    return "DRAFT:" + (",".join(fields) if fields else "none")


def language_line(config_path):
    """Third gate line: the language the owner writes in, as recorded.

    This gate is the first action of EVERY reply while setup is unfinished,
    so this line puts the owner's language in front of the model on every
    single turn -- as a recorded fact, not a rule it has to hold in mind
    while composing. Measured live four times: a whole interview written in
    English, and a reply came back in another language -- three times on a
    failure explanation, once on the printer success branch, in Dutch. Each
    of those branches had (or lacked) its own prose reminder; attaching one
    more reminder to one more branch is how the first three were "fixed".
    """
    draft_path = Path(config_path).with_name(".setup-draft.json")
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "LANG:unrecorded"
    if not isinstance(draft, dict):
        return "LANG:unrecorded"
    owner = draft.get("owner")
    language = owner.get("language") if isinstance(owner, dict) else None
    if isinstance(language, str) and language.strip():
        return "LANG:" + language.strip()
    return "LANG:unrecorded"


def main(argv=None):
    argv = sys.argv if argv is None else argv
    path = argv[1] if len(argv) > 1 else CONFIG_FILE
    if setup_needed(path):
        print("SETUP_NEEDED")
        print(draft_line(path))
        print(language_line(path))
    else:
        print("READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
