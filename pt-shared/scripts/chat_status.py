#!/usr/bin/env python3
"""At most two live chat pings while an on-demand paper is being built.

Measured live: a "send me the paper now" turn posted every research
decision into the owner's chat (desk by desk, URL by URL), then attached
the PDF as ``edition.pdf``. The owner asked for a wait line, not a
play-by-play.

This script POSTs through the same Plow Chat path as post_to_chat.py, so
the model does not type a sentence (Hermes delivers every assistant
chunk). Cron-fired papers must not call it: they already end in NO_REPLY.

    /var/lib/hermes/skills/pt-shared/scripts/chat_status.py --soon
    /var/lib/hermes/skills/pt-shared/scripts/chat_status.py --wait

``--wait`` is safe to call after every desk: it no-ops until WAIT_SECONDS
have passed since ``--soon``, then posts once.
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
from bearer_http import post_json  # noqa: E402

WAIT_SECONDS = 240
STAMP_DEFAULT = "/var/lib/hermes/pt/run/chat-status.json"
CONFIG_DEFAULT = "/var/lib/hermes/pt/config.json"

SOON = {
    "pt": "Seu jornal sai daqui a alguns minutos.",
    "en": "Your paper will be ready in a few minutes.",
}
WAIT = {
    "pt": "Mais uns minutos — o jornal está quase pronto.",
    "en": "A few more minutes — the paper is almost ready.",
}


def is_portuguese(language):
    s = (language or "").lower().replace("_", "-")
    return "portug" in s or s in {"pt", "pt-br"}


def status_text(kind, language):
    table = SOON if kind == "soon" else WAIT
    return table["pt"] if is_portuguese(language) else table["en"]


def owner_language(config_path):
    try:
        data = json.loads(open(str(config_path), encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return ""
    owner = data.get("owner") if isinstance(data, dict) else None
    if not isinstance(owner, dict):
        return ""
    lang = owner.get("language")
    return lang if isinstance(lang, str) else ""


def _load_stamp(path):
    try:
        data = json.loads(open(str(path), encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def record_soon(path, now=None):
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {"soon_at": float(now if now is not None else time.time()), "wait_sent": False}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def record_wait_sent(path):
    path = str(path)
    data = _load_stamp(path) or {}
    data["wait_sent"] = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


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
        description="One or two owner-facing wait lines for a live paper."
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--soon", action="store_true")
    which.add_argument("--wait", action="store_true")
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    language = owner_language(args.config)
    if args.soon:
        action = soon_action(args.stamp)
        if action != "send":
            print(f"STATUS:{action}")
            return
        text = status_text("soon", language)
        post_status(text, args.dry_run)
        record_soon(args.stamp)
        print("STATUS:soon")
        return
    action = wait_action(args.stamp)
    if action != "send":
        print(f"STATUS:{action}")
        return
    text = status_text("wait", language)
    post_status(text, args.dry_run)
    record_wait_sent(args.stamp)
    print("STATUS:wait")


if __name__ == "__main__":
    main()
