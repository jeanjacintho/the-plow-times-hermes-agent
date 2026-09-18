#!/usr/bin/env python3
"""At most two live chat pings while an on-demand paper is being built,
plus a hang-on during slow first-run setup.

Measured live: a "send me the paper now" turn posted every research
decision into the owner's chat (desk by desk, URL by URL), then attached
the PDF as ``edition.pdf``. The owner asked for a wait line, not a
play-by-play. Setup has the same hole: Latch probes and Mac file writes
leave the chat silent, so the owner thinks it froze.

This script POSTs through the same Plow Chat path as post_to_chat.py, so
the model does not type a sentence (Hermes delivers every assistant
chunk). Cron-fired papers must not call it: they already end in NO_REPLY.

    /var/lib/hermes/skills/pt-shared/scripts/chat_status.py --soon
    /var/lib/hermes/skills/pt-shared/scripts/chat_status.py --wait
    /var/lib/hermes/skills/pt-shared/scripts/chat_status.py --busy

``--wait`` is safe to call after every desk: it no-ops until WAIT_SECONDS
have passed since ``--soon``, then posts once. ``--busy`` is the setup
equivalent: first call posts a hang-on, later calls in the same wave
no-op until BUSY_REPEAT_SECONDS, then post "still on it" once. It does
not seal the session — setup is not done.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_to_chat  # noqa: E402
import setup_needed as _gate  # noqa: E402
from bearer_http import post_json  # noqa: E402

WAIT_SECONDS = 240
BUSY_REPEAT_SECONDS = 20
BUSY_NEW_WAVE_SECONDS = 90
STAMP_DEFAULT = "/var/lib/hermes/pt/run/chat-status.json"
BUSY_STAMP_DEFAULT = "/var/lib/hermes/pt/run/setup-busy.json"
CONFIG_DEFAULT = "/var/lib/hermes/pt/config.json"

SOON = {
    "pt": "⏳ Seu jornal sai daqui a pouco.",
    "en": "⏳ Your paper will be ready in a few minutes.",
}
WAIT = {
    "pt": "⏰ Mais uns minutinhos — o jornal está quase pronto.",
    "en": "⏰ A few more minutes — the paper is almost ready.",
}
BUSY = {
    "pt": "⏳ Um instante — tô nessa.",
    "en": "⏳ Hang on a sec — still setting up.",
}
BUSY_STILL = {
    "pt": "⏳ Ainda nisso — já já eu falo.",
    "en": "⏳ Still on it — back in a moment.",
}


def is_portuguese(language):
    s = (language or "").lower().replace("_", "-")
    return "portug" in s or s in {"pt", "pt-br"}


def status_text(kind, language):
    tables = {
        "soon": SOON,
        "wait": WAIT,
        "busy": BUSY,
        "busy-still": BUSY_STILL,
    }
    table = tables[kind]
    return table["pt"] if is_portuguese(language) else table["en"]


owner_language = _gate.owner_language


def _load_stamp(path):
    try:
        data = json.loads(open(str(path), encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def record_soon(path, now=None):
    _write_stamp(
        path,
        {
            "soon_at": float(now if now is not None else time.time()),
            "wait_sent": False,
        },
    )


def record_wait_sent(path):
    data = _load_stamp(str(path)) or {}
    data["wait_sent"] = True
    _write_stamp(path, data)


def soon_action(path, now=None, stale_seconds=7200):
    """Whether --soon should POST.

    Intake and pt-research both call --soon on a live copy. The second
    call must not send a second "few minutes" line. A finished paper
    (wait_sent) or a stamp older than stale_seconds is a new copy.
    """
    data = _load_stamp(str(path))
    if not data or "soon_at" not in data:
        return "send"
    if data.get("wait_sent") is True:
        return "send"
    start = data.get("soon_at")
    try:
        start = float(start)
    except (TypeError, ValueError):
        return "send"
    clock = float(now if now is not None else time.time())
    if clock - start > stale_seconds:
        return "send"
    return "already"


def _write_stamp(path, payload):
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def record_busy_start(path, now=None):
    _write_stamp(
        path,
        {
            "busy_at": float(now if now is not None else time.time()),
            "still_sent": False,
        },
    )


def record_busy_still(path):
    data = _load_stamp(str(path)) or {}
    data["still_sent"] = True
    _write_stamp(path, data)


def busy_action(path, now=None, repeat_seconds=BUSY_REPEAT_SECONDS,
                new_wave_seconds=BUSY_NEW_WAVE_SECONDS):
    data = _load_stamp(str(path))
    if not data or "busy_at" not in data:
        return "send-start"
    start = data.get("busy_at")
    try:
        start = float(start)
    except (TypeError, ValueError):
        return "send-start"
    clock = float(now if now is not None else time.time())
    elapsed = clock - start
    if elapsed >= new_wave_seconds:
        return "send-start"
    if data.get("still_sent") is True:
        return "already"
    if elapsed < repeat_seconds:
        return "too-early"
    return "send-still"


def wait_action(path, now=None, wait_seconds=WAIT_SECONDS):
    data = _load_stamp(str(path))
    if not data or "soon_at" not in data:
        return "no-soon"
    if data.get("wait_sent") is True:
        return "already"
    start = data.get("soon_at")
    try:
        start = float(start)
    except (TypeError, ValueError):
        return "no-soon"
    clock = float(now if now is not None else time.time())
    if clock < start + wait_seconds:
        return "too-early"
    return "send"


def post_status(text, dry_run):
    if dry_run:
        print(f"dry-run: would POST {len(text)} chars")
        return
    base, uid, token = post_to_chat.resolve_chat()
    post_json(
        base, f"/v1/chats/{uid}/messages", token, "Plow Chat",
        post_to_chat.compose_payload(text),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Owner-facing wait lines for a live paper or setup."
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--soon", action="store_true")
    which.add_argument("--wait", action="store_true")
    which.add_argument("--busy", action="store_true")
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stamp = args.stamp or (BUSY_STAMP_DEFAULT if args.busy else STAMP_DEFAULT)

    language = owner_language(args.config)
    if args.busy:
        action = busy_action(stamp)
        if action == "send-start":
            text = status_text("busy", language)
            post_status(text, args.dry_run)
            record_busy_start(stamp)
            print("STATUS:busy")
            return
        if action == "send-still":
            text = status_text("busy-still", language)
            post_status(text, args.dry_run)
            record_busy_still(stamp)
            print("STATUS:busy-still")
            return
        print(f"STATUS:{action}")
        return
    if args.soon:
        action = soon_action(stamp)
        if action != "send":
            print(f"STATUS:{action}")
            return
        text = status_text("soon", language)
        post_status(text, args.dry_run)
        record_soon(stamp)
        if not args.dry_run:
            import seal_chat_session

            seal_chat_session.request(seal_chat_session.STAMP_DEFAULT)
        print("STATUS:soon")
        return
    action = wait_action(stamp)
    if action != "send":
        print(f"STATUS:{action}")
        return
    text = status_text("wait", language)
    post_status(text, args.dry_run)
    record_wait_sent(stamp)
    print("STATUS:wait")


if __name__ == "__main__":
    main()
