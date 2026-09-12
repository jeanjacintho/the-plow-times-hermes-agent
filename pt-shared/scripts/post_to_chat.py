#!/usr/bin/env python3
"""post_to_chat.py -- the edition's chat leg: POST the PDF (or, if none, the
chat text) to the owner's home channel over the Plow Chat API, directly,
with no dependency on a connected live platform adapter.

Originally the fallback for a run with no --deliver arm. Promoted to the
PRIMARY chat leg (not a fallback) after measuring cron/scheduler.py's own
delivery live: the same unchanged content, run to run, both delivered fine
via --deliver and was silently discarded with "Fire claim ownership lost;
stale result was discarded" -- a genuine intermittent race in Hermes' own
cron heartbeat/claim mechanism, not anything about this script's content.
Calling the Plow Chat REST API directly, the same three calls
plow-chat-platform's own adapter makes internally (declare an attachment,
PUT the bytes to its signed upload_url, POST the message with
attachment_uids), needs no live adapter and is not subject to that race --
it is a plain HTTP call that either succeeds or exits loudly, same as the
text-only POST below always was.

The text is read on STDIN only -- never argv -- and only when there is no
PDF. With ``--pdf`` the message is the attachment alone (empty body), the
same envelope plow-chat-platform uses for photo-only sends. An edition is
the newspaper file; piping the chat transcript in as a caption is how the
owner got the PDF *and* a wall of text. Omit ``--pdf`` to post text only
(the fallback when weasyprint could not write the file).

The endpoint and credential come
from the process environment alone (PLOW_API_BASE, PLOW_HOME_CHANNEL,
PLOW_AGENT_TOKEN), which first boot publishes from the credential the host
dropped in: a file the agent can write is not a place to look for the API
base its own bearer is sent to. Any of the three unset or blank is refused
BY NAME, before anything posts, so a half-delivered run cannot happen.

`--pdf PATH` attaches that file (declare -> upload -> message-with-
attachment_uids) and sends no caption. `--dry-run` prints the
redacted envelope and never sends.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys

from bearer_http import post_json, post_json_read, put_bytes, require


def resolve_chat():
    """The chat endpoint (base + path) + bearer, validated before anything posts."""
    base = require("PLOW_API_BASE").rstrip("/")
    uid = require("PLOW_HOME_CHANNEL")
    token = require("PLOW_AGENT_TOKEN")
    return base, uid, token


def read_message():
    return sys.stdin.read().strip()


def compose_payload(text, attachment_uid=None):
    """One chat message: PDF-only when attached, otherwise the chat edition.

    plow-chat-platform posts ``{"body": "", "attachment_uids": [...]}`` for
    attachment-only sends; an empty body with a PDF is the newspaper, not a
    missing caption.
    """
    if attachment_uid:
        return {"body": "", "attachment_uids": [attachment_uid]}
    if not text:
        sys.exit("error: no edition text on stdin")
    return {"body": text}


def declare_and_upload(base, uid, token, pdf_path):
    """Declare the attachment, PUT its bytes to the signed upload_url, return its uid.

    Mirrors plow-chat-platform's own ``_send_attachment`` exactly (same three
    calls, same field names) -- this is not a new contract, just this
    script's own copy of the one Plow's REST API defines.
    """
    if not os.path.isfile(pdf_path):
        sys.exit(f"error: --pdf path does not exist: {pdf_path}")
    with open(pdf_path, "rb") as fh:
        data = fh.read()
    filename = os.path.basename(pdf_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/pdf"
    declared = post_json_read(
        base, f"/v1/chats/{uid}/attachments", token, "Plow Chat attachment declare",
        {"filename": filename, "content_type": content_type, "size_bytes": len(data)},
    )
    put_bytes(declared["upload_url"], declared.get("upload_headers") or {}, data,
              "Plow Chat attachment")
    return declared["uid"]


def main():
    parser = argparse.ArgumentParser(description="Post an edition to the owner's Plow Chat.")
    parser.add_argument(
        "--pdf", default=None,
        help="path to a PDF to attach (declare -> upload -> attach, same call the "
             "platform's own adapter makes); omit to post text only",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the request instead of sending it"
    )
    args = parser.parse_args()

    base, uid, token = resolve_chat()
    text = read_message()
    if not args.pdf and not text:
        sys.exit("error: no edition text on stdin")

    if args.dry_run:
        attach_note = f" + attach {args.pdf}" if args.pdf else ""
        kind = "pdf-only" if args.pdf else f"{len(text)} chars"
        print(
            f"dry-run: would POST {kind} to {base}/v1/chats/{uid}/messages"
            f'{attach_note}'
        )
        return

    attachment_uid = None
    if args.pdf:
        attachment_uid = declare_and_upload(base, uid, token, args.pdf)
    body = compose_payload(text, attachment_uid)

    post_json(base, f"/v1/chats/{uid}/messages", token, "Plow Chat", body)
    if args.pdf:
        print(f"chat edition posted (pdf only) {args.pdf}")
    else:
        print(f"chat edition posted ({len(text)} chars)")


if __name__ == "__main__":
    main()