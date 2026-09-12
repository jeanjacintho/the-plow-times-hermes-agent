---
name: pt-setup
description: First-run interview over chat — confirm the timezone, settle the delivery hour, ask about a printer and probe it once through Latch before trusting the answer, ask whether today's mail should join as a letters desk — writing pt/config.json as each answer lands and validating it with the pt-config gate. Use on the owner's first DM, including greetings (oi, oi de novo, hi, hello, hey), while pt/config.json is missing owner.timezone, delivery.hour or printer.configured. Never a generic assistant intro, never a personal-profile interview, never in a group, never in someone else's DM, and never to change one already-stored setting.
---

# pt-setup — the first conversation

This is a conversation, not a form, and `/var/lib/hermes/pt/config.json` is
the only record of how far it got. Read it first, every time, and continue
from the first key missing: `owner.timezone`, `delivery.hour`,
`printer.configured`. (`mail.configured` is asked in this interview too,
but a missing mail key is a valid older install — treat it as false, do
not restart setup for it.) Never re-ask something it already holds — a resumed
session that asks the timezone twice is the failure this file exists to
prevent.

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

> Sou o The Plow Times, seu jornal. Qual seu fuso (ex.: horário de Brasília) e a que horas quer o jornal da manhã? Se não disser, uso 7h.

English:

> I'm The Plow Times, your newspaper. What timezone are you in, and what time should the morning paper land? Default is 7:00.

Do not add a name question, a profile offer, or `/help` around that.

**Changing one setting later** is not this skill: a different delivery hour,
**a second (or third) daily delivery time** (`delivery.extra_hours`, a list
of "HH:MM" strings alongside `delivery.hour` — same conversion recipe above,
run once per additional time the owner names), **turning the letters desk
on or off** (`mail.configured`), or a new printer is a
one-line conversation that updates `pt/config.json` directly, re-runs the
gate, and then re-runs
`/var/lib/hermes/skills/news/pt-dashboard/scripts/register_crons.py` so the
new schedule exists now — not an interview from the top, and **never a
hand-registered `hermes cron create`**: a cron job that name doesn't
recognize (see `pt-dashboard/SKILL.md`'s spec table) is invisible to every
future reconcile, so a typo'd time or a since-changed delivery hour drifts
forever with nothing to catch it. This has happened live: asked for a
second daily edition, a session hand-built a `pt-daily-edition-2` job at
the wrong hour instead of writing `delivery.extra_hours` and reconciling —
`register_crons.py` exists precisely so that never has to be improvised.

## The questions, in order

**1. The timezone and the delivery hour, together.** Ask the owner's real
zone (a city or a named zone like "Brasilia time" is enough — resolve it to the IANA
name yourself, e.g. `America/Sao_Paulo`) and what local time they want their
morning paper, in the same turn if they volunteer both. Suggest 07:00 in
their own zone as the default.

You do **not** need the container restarted to serve an owner in a different
zone than this container's `TZ` (from `AGENT_TZ` at boot) — `hermes cron
create` fires bare cron expressions (minute-precise) in the container's own
zone, so convert: compute the container-local clock time, to the minute,
that corresponds to the owner's chosen local time, on today's date (so a DST
boundary on either side resolves correctly), and write that converted value
to `delivery.hour` as "HH:MM" — any real minute is fine, the gate and the
cron spec both carry it through exactly. Do the conversion in code, never by
mental UTC-offset arithmetic (DST makes that wrong twice a year in either
zone):

    python3 -c "
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import os
    owner_hour, owner_minute = 10, 25  # what the owner asked for, in THEIR zone
    owner_tz = ZoneInfo('America/Sao_Paulo')  # resolved from what they said
    container_tz = ZoneInfo(os.environ['TZ'])
    today = datetime.now(owner_tz).date()
    moment = datetime(today.year, today.month, today.day, owner_hour, owner_minute, tzinfo=owner_tz)
    print(moment.astimezone(container_tz).strftime('%H:%M'))
    "

Write the
owner's real, unconverted zone to `owner.timezone` — that is what you show
back to them and what any future re-setup or "changing one setting" edit
recomputes from, never the container's own zone.

Say the result in the owner's own terms — "your paper arrives at 07:00,
Brasilia time" — never mention the container's zone, `TZ`, or the
conversion; that plumbing is not theirs to know about. The one case that
still needs a restart: the container's `TZ` itself is unset or empty (a
config problem nothing here can compute around) — say so plainly, once, and
that a restart with `AGENT_TZ` set is what fixes it.

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

- lpstat lists a printer: write `printer.configured: true` and its exact
  CUPS name as `printer.name` — `lp -d` will need that spelling.
- lpstat reports none, or the Mac is unreachable: write
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
   works — write `mail.configured: true`.
2. Only if that call is denied, 401/412, or Latch has no Google account:
   probe Mail.app:

```json
{ "argv": ["osascript", "-e", "tell application \"Mail\" to get name"] }
```

- They said yes and **either** probe works: write `mail.configured: true`.
- They said no, or both probes fail / the Mac is unreachable: write
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

## Writing and proving the config

After each answer, write `/var/lib/hermes/pt/config.json` (create
`/var/lib/hermes/pt/` when absent) and validate with the gate:

    python3 /var/lib/hermes/skills/news/pt-shared/scripts/pt_config_gate.py \
        /var/lib/hermes/pt/config.json

**Paste the gate's output verbatim.** Empty output is pass; anything it
prints is an invariant you have not satisfied yet — fix it before the next
question, not after the interview. The example shape lives beside the gate
at `pt-shared/references/config.example.json`.

When all three keys are in and the gate is silent, setup is done — run
`/var/lib/hermes/skills/news/pt-dashboard/scripts/register_crons.py`
once as setup's closing bring-up step so `pt-daily-edition` exists the
moment setup ends (the paper always has weather and calendar, even with
zero news sections); paste its output and report its exit status. This is the
one cron registration a setup turn may do (it is the reviewed bring-up
script, not a hand-built schedule).

Then say so in one line — the timezone, the hour, whether the paper will
print, whether letters join, and that their news sections are in — and invite
the first topic. A first research job is still pt-intake's, not this skill's.