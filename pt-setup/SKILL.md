---
name: pt-setup
description: First-run interview over chat — settle the morning delivery hour, ask about a printer and probe it once through Latch, ask whether today's mail should join as a letters desk, then resolve the owner's timezone from Latch location and convert that hour for the cron. Use on the owner's first DM, including greetings (oi, oi de novo, hi, hello, hey), while pt/config.json is missing owner.timezone, delivery.hour or printer.configured. Never ask their timezone, name, or a personal profile. Never in a group, never in someone else's DM, and never to change one already-stored setting.
---

# pt-setup — the first conversation

This is a conversation, not a form, and `/var/lib/hermes/pt/config.json` is
the only record of how far it got. Read it first, every time, and continue
from the first interview field missing: the local delivery hour, then
`printer.configured`. Do **not** ask their timezone — Latch location at the
end supplies `owner.timezone`. (`mail.configured` is asked in this interview
too, but a missing mail key is a valid older install — treat it as false, do
not restart setup for it.) Never re-ask something the draft or config
already holds.

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

**1. The delivery hour only.** Ask what local time they want the morning
paper. Suggest 07:00. Do not ask a city, a zone, or a fuso — you will
read that from Latch at the end. Write their answer (or 07:00 if they
skip) to `/var/lib/hermes/pt/.setup-draft.json` as
`{"local_hour":"HH:MM"}` so a resumed session does not ask again. Do not
write `pt/config.json` yet: `owner.timezone` is still unknown, and the
gate would fail.

**2. The printer.** Ask whether a printer is set up on their Mac. Whatever
they answer, **probe once through Latch before writing
`printer.configured: true`** — the same discipline ld-setup applies to the
Pi bring-up; a yes/no alone is a configured printer that fails on every
nightly run. The probe:

```json
{ "command": ["lpstat", "-p"] }
```

(`plow_run_command` takes an argv array and runs it directly — no shell, no
`~` expansion, values as separate array elements.)

- lpstat lists a printer: merge into `.setup-draft.json`
  `printer.configured: true` and its exact CUPS name as `printer.name` —
  `lp -d` will need that spelling.
- lpstat reports none, or the Mac is unreachable: merge
  `printer.configured: false`, `name: null`, and say the paper still
  delivers in chat — printing joins automatically if a printer shows up
  later (that is the changing-one-setting path, plus a re-probe).

**3. The letters desk.** Ask whether the paper should carry today's mail
(a letters column: sender and subject, not full bodies). Weather and
calendar always run; mail is opt-in. Whatever they answer, **probe once
through Latch before writing `mail.configured: true`**, Google first,
Mail.app only if that fails:

1. `plow_run_command` argv (exact):

```json
{ "argv": ["plow-gog", "gmail", "search", "newer_than:1d", "--max", "5", "--json", "--fields", "id,date,from,subject"] }
```

   A result (including zero messages) means the Google account in Latch
   works — merge `mail.configured: true` into the draft.
2. Only if that call is denied, 401/412, or Latch has no Google account:
   probe Mail.app:

```json
{ "argv": ["osascript", "-e", "tell application \"Mail\" to get name"] }
```

- They said yes and **either** probe works: merge `mail.configured: true`.
- They said no, or both probes fail / the Mac is unreachable: merge
  `mail.configured: false` and say the letters column can join later the
  same way a printer does. Never invent an inbox.

**4. The news sections (optional).** Ask what they want on the news desk
every day — "the dollar, sports news", anything. Weather and the diary
already have their own departments; do not also add a "weather" news
section unless they insist on a second, different weather beat. This is
the one question with no required answer: a paper of only weather and
calendar is a valid install, and they can add news sections later in chat
(including a different newspaper at another hour).
Take each thing they name as a `section`
topic via `pt-intake`'s writer (`topics.py add --kind section --depth quick`),
in the order they say it — that order is the news desk's order. If they name more
than eight, take the first eight and say the cap; the daily run researches
every news section in one session and eight is the honest ceiling. Never invent a
section they did not ask for.

## Close: location, convert, write config

Do not write `pt/config.json` until this step. After the interview answers
are in `.setup-draft.json` (at least `local_hour` and `printer`):

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
