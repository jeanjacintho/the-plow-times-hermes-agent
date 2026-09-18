#!/usr/bin/env python3
"""Stamp that this chat's next turn must not inherit the paper that just ran.

Hermes keeps one gateway session for the owner's Plow Chat DM until /new.
A live paper dumps Latch pages and desk JSON into that session; the next
"send me the paper" then spends tens of seconds re-reading it and starts
hand-patching yesterday's files. Durable state is topics.json / pt/, not
the transcript.

post_to_chat.py (and chat_status --soon) write the stamp. The gateway pin
consumes it on agent:end and /new's the producing session plus every
plow_chat route, with no banner in chat.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

STAMP_DEFAULT = "/var/lib/hermes/pt/run/seal-session.json"


def request(path, session_key="", platform="", now=None, delivered=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pending": True,
        "delivered": bool(delivered),
        "session_key": session_key or os.environ.get("HERMES_SESSION_KEY", ""),
        "platform": platform or os.environ.get("HERMES_SESSION_PLATFORM", ""),
        "at": float(now if now is not None else time.time()),
    }
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)
    return payload


def peek(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def consume(path):
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        path.unlink()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _platform_value(entry):
    platform = getattr(entry, "platform", None)
    if platform is None:
        return ""
    return str(getattr(platform, "value", platform) or "")


def keys_to_seal(payload, entries):
    """The producing session, and every plow_chat DM (cron papers must
    clear the owner's live thread too)."""
    keys = set()
    payload = payload or {}
    stamped = payload.get("session_key") or ""
    if stamped:
        keys.add(stamped)
    for entry in entries or []:
        key = getattr(entry, "session_key", "") or ""
        if not key:
            continue
        plat = _platform_value(entry)
        if plat == "plow_chat" or "plow_chat" in key:
            keys.add(key)
    return keys


def main():
    parser = argparse.ArgumentParser(
        description="Stamp the gateway to /new the owner's chat after this paper.",
    )
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    args = parser.parse_args()
    request(args.stamp)
    print("SEAL:pending")


if __name__ == "__main__":
    main()
