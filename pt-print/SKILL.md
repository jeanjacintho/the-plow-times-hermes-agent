---
name: pt-print
description: Best-effort paper delivery — ship the edition PDF the chat already got to the owner's printer through Latch when pt/config.json says printer.configured. Invoked by post_to_chat.py after the PDF POST, not by the model. Never a delivery requirement: every failure here ends with the chat edition as the outcome.
---

# pt-print — the paper edition, best-effort

**The chat edition is the contract; paper is the bonus.** Every step here is
best-effort: no failure in this skill blocks a delivery, re-runs research,
or delays the chat edition — it only costs the page.

**Every step below runs silently.** No "rendering now", no "sending to the
printer", no restating what a tool call just returned — only the outcome
messages this file actually names (the failure line below, or nothing at
all on success, since the chat edition already said the paper is on its
way). A tool result is never something to narrate back to the owner.

## When to run at all

Do not run this skill from the live turn. `post_to_chat.py --pdf` already
calls `print_edition.py` after the chat POST. A second invocation would
double-print. The script itself is still the Latch/`lp` implementation.

It reads `pt/config.json` itself. If
`printer.configured` is not exactly `true` — false, null, absent, malformed,
missing file — it prints `skipped: printer.configured is not true` and
exits 0. That skip is silence: say nothing about printing in the edition;
the chat edition is the whole delivery.

## Ship it through Latch

The printer is on the owner's Mac. **Do not call Latch tools from this
skill and do not paste the page into a tool argument.** Measured live:
stuffing ~43k of HTML into a Latch write call killed the LLM stream
(incomplete chunked read) and `lp` never ran, while the chat PDF still
posted because a script read the file from disk. Paper is the same shape.
One bare command; the script reads `edition.pdf` (the same file the chat
already posted — measured live, JornalVirtual refused `text/html`), writes
it through Latch, and runs `lp` with `network: true` (CUPS talks to `cupsd`
over a local socket — same grant as the printer probe):

    /var/lib/hermes/skills/pt-print/scripts/print_edition.py /var/lib/hermes/pt/run/<id>/edition.pdf /var/lib/hermes/pt/config.json

Date comes from sibling `edition.json`. The PDF, the Mac path, the CUPS
name, pending-handle polling, and the AppleScript retry if sandboxed `lp`
returns "Bad file descriptor" all live in that script — never retyped here.

## When it fails — and it is allowed to

Any failure — the Mac unreachable, the write denied, `lp` non-zero, "no
such printer", the script exiting non-zero — ends the same way:

- the chat edition already delivered is the outcome; say nothing that
  implies the whole delivery failed,
- `post_to_chat.py` posts the one line itself ("page not printed — <reason>;
  next scheduled run retries"), because the turn ends in `NO_REPLY`; do not
  repeat it,
- do not retry in a loop, do not queue the page, do not re-run research to
  "fix" it. The next scheduled run recomposes and re-delivers on its own.

A printer that fails on every run is a config problem, not a print problem:
after the second consecutive failed run on a subscription, say the printer
may need re-probing (the pt-setup changing-one-setting path), once, and stop
mentioning it until the owner does something.

## How this reaches the Mac, and what a failure means

`print_edition.py` opens a Latch session through `latch_mcp.connect()`, which
takes whichever credential the install has:

- **self-hosted** — the static `DOMO_DEVICE_UID` / `DOMO_MCP_TOKEN` pair the
  owner pasted into the home's `.env` (README, "create a static credential").
- **otherwise** — the `PLOW_MCP_URL` and `PLOW_AGENT_TOKEN` that `plow-init`
  publishes to every service at boot, having read this agent's own `mcp_url`
  from `/v1/agents/me` once. Nothing is fetched here. That pair is present on
  a hosted install, which never gets a static pair and used to fail every
  print, and on a self-hosted one too.

That means **there is no state in which paper can never print.** A hosted
install used to fail every run on a missing `DOMO_DEVICE_UID`; it no longer
can. So every print failure here is one a later run may succeed at, and the
retry line `post_to_chat.py` posts is honest:

- the relay answers 404 until Latch connects — the owner opening Latch on
  their Mac fixes it, and the next run prints,
- a sleeping Mac, an off printer, a `lp` refusal — all recoverable.

Two things follow for what you say to the owner. Do not tell them paper is
unavailable on this install; it is not. And do not send them to relink a
Latch pairing without reading its state first — a failure here is far more
often the Mac being asleep than the pairing being broken. Never report the
state of a layer you did not check as evidence about the one that broke.
