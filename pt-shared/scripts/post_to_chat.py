#!/usr/bin/env python3
"""post_to_chat.py -- the edition's chat leg: POST the text to the owner's
home channel over the Plow Chat API.

The cron rows pt-dashboard registers carry a --deliver target, and the gateway
relays the run's final response -- which for every edition run has content,
so the native deliver arm IS the chat leg (the same arm ld-weekly-digest
rides). This script is the fallback for a run that has no deliver arm to
ride: a manual `hermes cron run` of a job registered without one, or a
session that must hand the owner text mid-run.

The text is read on STDIN only -- never argv. An edition is web-derived
content, and argv is the one surface another process could read; a quoted
heredoc keeps it inert data on its way in. The endpoint and credential come
from the process environment alone (PLOW_API_BASE, PLOW_HOME_CHANNEL,
PLOW_AGENT_TOKEN), which first boot publishes from the credential the host
dropped in: a file the agent can write is not a place to look for the API
base its own bearer is sent to. Any of the three unset or blank is refused
BY NAME, before anything posts, so a half-delivered run cannot happen.

`--dry-run` prints the redacted envelope and never sends.
"""
from __future__ import annotations

import argparse
import json
import sys

from bearer_http import post_json, require


def resolve_chat():
    """The chat endpoint (base + path) + bearer, validated before anything posts."""
    base = require("PLOW_API_BASE").rstrip("/")
    uid = require("PLOW_HOME_CHANNEL")
    token = require("PLOW_AGENT_TOKEN")
    return base, f"/v1/chats/{uid}/messages", token


def read_message():
    text = sys.stdin.read().strip()
    if not text:
        sys.exit("error: no edition text on stdin")
    return text


def main():
    parser = argparse.ArgumentParser(description="Post an edition to the owner's Plow Chat.")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the request instead of sending it"
    )
    args = parser.parse_args()

    base, path, token = resolve_chat()
    text = read_message()

    if args.dry_run:
        print(
            f"dry-run: would POST {len(text)} chars to {base}{path} "
            f'body={{"body": "<redacted>"}}'
        )
        return

    post_json(base, path, token, "Plow Chat", {"body": text})
    print(f"chat edition posted ({len(text)} chars)")


if __name__ == "__main__":
    main()