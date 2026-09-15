---
name: pt-setup
description: First-run interview over chat — settle the morning delivery hour, ask about a printer and probe it once through Latch, ask whether today's mail should join as a letters desk, then resolve the owner's timezone from Latch location and convert that hour for the cron. Use on the owner's first DM, including greetings (oi, oi de novo, hi, hello, hey), while pt/config.json is missing owner.timezone, delivery.hour or printer.configured. Never ask their timezone, name, or a personal profile. Never in a group, never in someone else's DM, and never to change one already-stored setting.
---

# pt-setup — the first conversation

This is a conversation, not a form. `/var/lib/hermes/pt/config.json` and
`/var/lib/hermes/pt/.setup-draft.json` are the **only** record of how far
it got — not the Plow Chat thread. Older messages about a printer or
letters after a wiped session are leftover; if the draft is missing,
start at the delivery hour. Do **not** ask their timezone — Latch location
at the end supplies `owner.timezone`. (`mail.configured` is asked in this
interview too, but a missing mail key is a valid older install — treat it
as false, do not restart setup for it.) Never re-ask something the draft
or config already holds.

**Every draft write, and every "what's next", goes through one script —
never a hand-edited `.setup-draft.json`, never your own judgement about
which question comes after which.** Measured live: the model once wrote
the hour to the draft with a plain `write_file` call and then, in that
same reply, went on to probe the printer through Latch and ask about the
letters desk too — the owner never saw "is a printer set up on your Mac?"
as its own question, and the printer probe's answer was never even saved
to the draft. That is exactly the failure this script exists to make
structurally impossible:

    /var/lib/hermes/skills/pt-shared/scripts/record_setup.py \
        /var/lib/hermes/pt/config.json key=value [key=value ...]

One line, no interpreter prefix, no shell operators — same rule SOUL.md
gives `setup_needed.py`. `key` is a dot-path (`local_hour`,
`printer.configured`, `printer.name`, `mail.configured`, `news_asked`);
`true`/`false` become real JSON booleans, anything else stays a string. A
value with a space needs its own quoting, e.g. `printer.name="HP LaserJet 4"`.
It prints two lines:

    DRAFT:<fields already recorded>
    NEXT_QUESTION=<hour|printer|mail|news|close>

**Send exactly the one message `NEXT_QUESTION` calls for, then stop.**
Not that question plus the probe for the one after it. Not that question
plus a summary of what you just recorded. One question, one reply, then
wait for the owner. The questions below are written in two parts for
exactly this reason: part **a** is what you send and then stop for; part
**b** is what you do on their *next* message, before sending the
question after it.

It runs only in the owner's own solo DM — sender role **owner**, chat type
**DM**, roster just the two of you; the platform reports all three. Anywhere
else, none of this applies: answer what was actually asked, ask none of
these questions, and write nothing.

One or two short lines per message, no bullet lists — this lands on a
phone. Answer what the owner actually said first. And never narrate the
mechanics: no "let me run setup", no announcing a step. Send the message the
step calls for.

**A greeting is this interview.** "oi", "oi de novo", "hi", "hello", "hey"
with a missing config is the opener below, not a hello-plus-help-menu and
not a continuation of a profile interview that already happened in this
chat. Do not introduce a personal assistant, do not offer `/help`, do not
ask their name or how they like to work.

**Opener — send this, then stop and wait.** Match the owner's language.
Portuguese:

> Sou o The Plow Times, seu jornal. A que horas quer o jornal da manhã? Se não disser, uso 7h.

English:

> I'm The Plow Times, your newspaper. What time should the morning paper land? Default is 7:00.

Do not ask their timezone, their name, a profile, or `/help`. The zone comes
from their Mac, through Latch, when this interview closes.

**Changing one setting later** is not this skill: a different delivery hour,
**a second (or third) daily delivery time** (`delivery.extra_hours`, a list
of "HH:MM" strings alongside `delivery.hour` — convert each with
`convert_delivery.py` using the stored `owner.timezone`, never by asking
the zone again), **turning the letters desk
on or off** (`mail.configured`), or a new printer is a
one-line conversation that updates `pt/config.json` directly, re-runs the
gate, and then re-runs
`/var/lib/hermes/skills/pt-dashboard/scripts/register_crons.py` so the
new schedule exists now — not an interview from the top, and **never a
hand-registered `hermes cron create`**: a cron job that name doesn't
recognize (see `pt-dashboard/SKILL.md`'s spec table) is invisible to every
future reconcile, so a typo'd time or a since-changed delivery hour drifts
forever with nothing to catch it. This has happened live: asked for a
second daily edition, a session hand-built a `pt-daily-edition-2` job at
the wrong hour instead of writing `delivery.extra_hours` and reconciling —
`register_crons.py` exists precisely so that never has to be improvised.

## The questions, in order

Start of turn, every turn while `SETUP_NEEDED`: `setup_needed.py`'s second
line (`DRAFT:...`) or `record_setup.py`'s own `NEXT_QUESTION` from the
answer you just recorded says which of these you are on. Never infer it
from the draft's shape yourself, and never from what the chat thread
already discussed.

**1a. Ask the delivery hour, nothing else** — but only if the message
you are answering right now is a bare greeting ("oi", "hi", "hello")
with nothing else in it. **If it already reads like an hour answer
(see 1b's list), skip straight to 1b — do not send this question
again just because the draft still says `DRAFT:none`.** Measured live:
the assistant asked this, the owner replied "7 is fine", and because
nothing had been written to the draft *yet* the assistant sent this
exact question a second time instead of recognizing the reply as an
answer — a fresh, un-recorded draft is not proof the incoming message
is a fresh greeting. Otherwise: suggest 07:00, do not ask a city, a
zone, or a fuso — you will read that from Latch at the end. Send only
this question, then stop.

**1b. On their next message**, treat any of "yes", "y", "sim", "ok",
"okay", "that", "default", "7", "7h", "7:00", "07:00", "pode", "isso", or
a skip as accepting 07:00; a clock time they name ("8:30", "08:30") is
that time. Record it and read the next question:

    record_setup.py /var/lib/hermes/pt/config.json local_hour=07:00

Send only the `NEXT_QUESTION` it prints (question 2a), then stop. Do not
also probe the printer in this reply — that happens on their *next*
message, in 2b, never before question 2a has actually been sent to them.
Do not write `pt/config.json` yet: `owner.timezone` is still unknown, and
the gate would fail.

**2a. Ask whether a printer is set up on their Mac.** Send only this
question, then stop — do not probe Latch yet, no matter what they might
have said about a printer earlier in this same chat thread.

**2b. On their next message**, whatever they answered, **probe once
through Latch before recording `printer.configured`** — the same
discipline ld-setup applies to the Pi bring-up; a yes/no alone is a
configured printer that fails on every nightly run.

Latch's `plow_run_command` schema (mcp-server `tools.ts`) requires **`argv`**
and runs the array directly — no shell, no `~`. It also accepts a defined
set of optional keys (`goal`, `network`, `cwd`, `read_paths`,
`write_paths`, `apple_events`, `wait_ms`, …) — `additionalProperties: false`
rejects a genuinely unknown key like `"command"` (not in the schema at
all; the relay returns JSON-RPC -32601 / "Server returned an error
response" and the Mac never sees `lpstat`), not these. Hermes names the
tool `mcp__plow__plow_run_command` (or `mcp__latch__plow_run_command` if
`tools_list` says so). **Never send `"command"`.**

**This call needs `"network": true`.** Measured live, with a printer
genuinely configured and visible in System Settings: `lpstat -p` still
came back `exit_code:1, "lpstat: Bad file descriptor"` under the
default sandboxed call. Diagnosis (see latch's
`packages/device-core/src/executor.ts`, `SandboxProfile.generate`):
`lpstat` talks to `cupsd` over a local socket, and Latch's seatbelt
profile denies all `network*`/`system-socket` primitives whenever
`network` is left false or omitted — CUPS can't even reach its own
scheduler, and libcups surfaces that denial as "Bad file descriptor"
rather than a real "no destinations" report. `network: true` is a
broader grant than this call strictly needs (it opens general network
access for one local IPC round-trip, not just a scoped CUPS exception —
that scoped fix belongs in Latch's own sandbox profile, not here), but
it is the fix available from this side without editing a different
project's security-sensitive code.

Exact call:

```json
{
  "argv": ["lpstat", "-p"],
  "network": true,
  "goal": "List CUPS printers on the owner's Mac for newspaper setup"
}
```

If the result is `{"status":"pending","handle":…}`, poll
`plow_get_result` with that handle until `ready` (Latch's call budget is
10s, not a failed Mac). `denied` / `blocked` is the owner tapping No on
the Latch card, not an unreachable device. Latch parked/unreachable is
also an answer, not a reason to skip 2a — you already asked it; now
record the probe's outcome:

- lpstat lists a printer:

      record_setup.py /var/lib/hermes/pt/config.json printer.configured=true "printer.name=<exact CUPS name>"

  as a bare invocation, two space-separated arguments — the same
  invocation you've been using for every other field, nothing more.
  CUPS queue names routinely have underscores (macOS itself substitutes
  `.`/spaces from the display name into `_` for the actual queue name,
  e.g. "virtual-printer.online" the owner sees in System Settings is
  `virtual_printer_online` in `lpstat`'s own output — use exactly what
  `lpstat` printed, not the display name) but that changes nothing about
  how to call this script: only the *key* (the part before `=`) is
  split on dots to build nested JSON, so a dotted or underscored
  *value* is never at risk of being misread — it's taken verbatim,
  whatever's in it. Quote it only if it has a space; nothing else is
  ever needed. **Do not wrap this in `python3 - <<'PY' ... PY`, a `-c`
  flag, or any other interpreter** — that is exactly the "script
  execution" pattern SOUL.md's gate exists to flag, and it hands the
  owner a raw approval prompt instead of the printer answer they're
  waiting on (measured live: this happened, over a printer name with
  nothing unusual in it at all — a plain space-separated call would
  have worked the first time).
- lpstat's own output says there are none (e.g. "No destinations
  added."), Latch is parked, or the Mac is unreachable:

      record_setup.py /var/lib/hermes/pt/config.json printer.configured=false

  and say, **in the owner's own language, the one they've been writing
  this chat in** — not necessarily English, whatever this file happens
  to be written in — that the paper still delivers in chat; printing
  joins automatically if a printer shows up later (that is the
  changing-one-setting path, plus a re-probe).
- the call itself returned an error that isn't a real lpstat report —
  e.g. `exit_code` non-zero with output like "Bad file descriptor"
  rather than an actual destinations list or "No destinations added."
  (measured live: this happens): still

      record_setup.py /var/lib/hermes/pt/config.json printer.configured=false

  (never guess `true` without a real listing), but say plainly, in
  their language, that the printer check itself didn't run cleanly —
  not "no printer was found." Those are different claims; only make
  the one that's actually true. Printing can still be turned on later
  once the check works.

Send only the `NEXT_QUESTION` it prints (question 3a), then stop.

**3a. Ask whether the paper should carry today's mail** (a letters
column: sender and subject, not full bodies). Weather and calendar
always run; mail is opt-in. Send only this question, then stop.

**3b. On their next message**, whatever they answered, **probe once
through Latch before recording `mail.configured`**, Google first,
Mail.app only if that fails:

1. `plow_run_command` argv (exact):

```json
{ "argv": ["plow-gog", "gmail", "search", "newer_than:1d", "--max", "5", "--json", "--fields", "id,date,from,subject"] }
```

   A result (including zero messages) means the Google account in Latch
   works.
2. Only if that call is denied, 401/412, or Latch has no Google account:
   probe Mail.app:

```json
{ "argv": ["osascript", "-e", "tell application \"Mail\" to get name"], "apple_events": true, "goal": "See whether Mail.app is reachable for the letters desk" }
```

Then record the outcome:

- They said yes and **either** probe works:

      record_setup.py /var/lib/hermes/pt/config.json mail.configured=true

- They said no, or both probes fail / the Mac is unreachable:

      record_setup.py /var/lib/hermes/pt/config.json mail.configured=false

  and say, **in the owner's own language, the one they've been writing
  this chat in**, that the letters column can join later the same way a
  printer does. Never invent an inbox.

Send only the `NEXT_QUESTION` it prints (question 4a), then stop.

**4a. Ask what they want on the news desk every day** — "the dollar,
sports news", anything. Weather and the diary already have their own
departments; do not also add a "weather" news section unless they insist
on a second, different weather beat. This is the one question with no
required answer: a paper of only weather and calendar is a valid install,
and they can add news sections later in chat (including a different
newspaper at another hour). Send only this question, then stop.

**4b. On their next message** (including "nothing" / "skip"), take each
thing they name as a `section` topic via `pt-intake`'s writer
(`topics.py add --kind section --depth quick`), in the order they say
it — that order is the news desk's order. If they name more than eight,
take the first eight and say the cap; the daily run researches every news
section in one session and eight is the honest ceiling. Never invent a
section they did not ask for. Then, regardless of whether they named
any:

    record_setup.py /var/lib/hermes/pt/config.json news_asked=true

Send only the `NEXT_QUESTION` it prints — `close` — and move straight
into the close step below (this one has no separate question to send;
"close" means do the close work now).

## Close: location, convert, write config

Do not write `pt/config.json` until `NEXT_QUESTION` says `close`:

1. **Read location through Latch**, the same script as
   `pt-research/references/desks.md` §1 — `~/Plow/pt/location.py` via
   `plow_write_file` then `plow_run_command`
   `["/usr/bin/python3", "/Users/<user>/Plow/pt/location.py"]`.
   Take `timezone` from the JSON (IANA, e.g. `America/Sao_Paulo`). If the
   call fails or `timezone` is blank, say the paper cannot be scheduled
   until the Mac can report where they are — do not invent a zone, do not
   ask them to type one.
2. **Convert** the draft `local_hour` into the container's clock. Never
   subtract hours by hand:

       python3 /var/lib/hermes/skills/pt-setup/scripts/convert_delivery.py \
           --local-hour HH:MM --owner-tz America/Sao_Paulo

   The printed line is `delivery.hour`. `owner.timezone` is the IANA name
   from step 1, unconverted. If the script says container TZ is empty, say
   so once — a restart with `AGENT_TZ` set is the fix.
3. **Write** `/var/lib/hermes/pt/config.json` from the draft plus those two
   fields (`delivery.local_hour` may keep what they asked, for later
   edits). Validate:

       python3 /var/lib/hermes/skills/pt-shared/scripts/pt_config_gate.py \
           /var/lib/hermes/pt/config.json

   **Paste the gate's output verbatim.** Empty output is pass. Then run
   `/var/lib/hermes/skills/pt-dashboard/scripts/register_crons.py`,
   paste its output, and delete `.setup-draft.json`.

Say the result in the owner's own terms — "seu jornal chega às 7h" using
the hour they named, never the container's zone, `TZ`, or the conversion.
Invite the first topic. A first research job is still pt-intake's.
