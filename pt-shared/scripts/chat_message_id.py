#!/usr/bin/env python3
"""chat_message_id.py -- issue #85's plow_chat item handle.

A phone-backed line already has an item today: a Messages chat plus rowid
(pt-priority/SKILL.md defines the shape, "a named reader plus the id it
re-opens with"), read live off the Mac. A `plow_chat` line with no Messages
or mail thread behind it -- an `<name>@plow.co` address, say -- had no
counterpart: the correction or setup answer could only be written item-less,
so `pt-intake` and `pt-setup` fell back to "unsupported" and wrote nothing.

This is that counterpart. The reader is the same Plow Chat API
`post_to_chat.py` already posts through; the id is the uid it already
assigns every message in the channel -- the obvious candidate the issue
names, since nothing needs inventing to read it back.

    chat_message_id.py

Always exits 0 and prints exactly one line:

  HANDLE:<uid>   the owner's own latest message on the home channel -- this
                 is only ever called while processing that very message, so
                 nothing this agent has posted since outranks it in the list
  HANDLE:none    the API could not be read (env not set, request failed, an
                 answer with no usable list or uid) -- callers treat this
                 exactly like a phone/mail line with no handle: the
                 correction is unsupported, not fabricated

Read-only: never posts, never marks anything read.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bearer_http import get_json  # noqa: E402
from post_to_chat import resolve_chat  # noqa: E402


def _messages_from(payload):
    """The list of message objects in a GET .../messages answer, whatever
    key (if any) it is wrapped under -- unverified against a live response,
    so every shape but a bare or wrapped list is treated as unusable."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("messages", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def latest_message_uid(messages):
    """The last message's own uid, or None.

    Called synchronously while processing the owner's own inbound message
    and before this agent posts anything back, so the last entry in the
    channel's list is definitionally that message.
    """
    if not messages:
        return None
    latest = messages[-1]
    if not isinstance(latest, dict):
        return None
    uid = latest.get("uid")
    return uid if isinstance(uid, str) and uid.strip() else None


def resolve_handle():
    """`<uid>` or None -- never raises; any failure here is "no handle"."""
    try:
        base, uid, token = resolve_chat()
        payload = get_json(base, f"/v1/chats/{uid}/messages", token, "Plow Chat")
    except SystemExit:
        return None
    return latest_message_uid(_messages_from(payload))


def main():
    handle = resolve_handle()
    print(f"HANDLE:{handle}" if handle else "HANDLE:none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
