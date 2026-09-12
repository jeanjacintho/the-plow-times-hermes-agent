---
name: pt-setup
description: First-run interview over chat — confirm the timezone, settle the delivery hour, ask about a printer and probe it once through Latch before trusting the answer — writing pt/config.json as each answer lands and validating it with the pt-config gate. Use in the owner's solo DM while pt/config.json is missing owner.timezone, delivery.hour or printer.configured. Never in a group, never in someone else's DM, and never to change one already-stored setting.
---

# pt-setup — the first conversation

This is a conversation, not a form, and `/var/lib/hermes/pt/config.json` is
the only record of how far it got. Read it first, every time, and continue
from the first key missing: `owner.timezone`, `delivery.hour`,
`printer.configured`. Never re-ask something it already holds — a resumed
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

**Changing one setting later** is not this skill: a different delivery hour
or a new printer is a one-line conversation that updates
`pt/config.json` directly and re-runs the gate — not an interview from the
top.

## The questions, in order

**1. The timezone.** The container already runs in `TZ` (from AGENT_TZ at
boot), and the cron system will fire in it — so the point of this question
is to make the OWNER'S zone the one everyone agrees on, out loud. Name the
zone you are running in and ask them to confirm or correct it. Write what
they confirm. If they correct it to something the container is not running
in, say plainly that the container must be restarted with that `TZ` before
crons will fire in it — registering schedules across a mismatch is refused
on purpose, and a morning paper at the wrong hour is the alternative.

**2. The delivery hour.** When should the morning paper land — that is the
nightly subscription moment and the default for deep one-offs. Suggest
07:00, take any hour they say, and record it as "HH:00" only: minutes are
refused at the gate because the cron fires at the hour and a config saying
"07:30" would be a promise the paper cannot keep. If they insist on a
half-hour, offer the nearest hour and say why.

**3. The printer.** Ask whether a printer is set up on their Mac. Whatever
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

**4. The paper's sections (optional).** Ask what they want in their paper
every day — "clima, dólar, as notícias do Grêmio", anything. This is the one
question with no required answer: an empty paper is a valid install, and
they can add sections later in chat. Take each thing they name as a `section`
topic via `pt-intake`'s writer (`topics.py add --kind section --depth quick`),
in the order they say it — that order is the paper's order. If they name more
than eight, take the first eight and say the cap; the daily run researches
every section in one session and eight is the honest ceiling. Never invent a
section they did not ask for.

## Writing and proving the config

After each answer, write `/var/lib/hermes/pt/config.json` (create
`/var/lib/hermes/pt/` when absent) and validate with the gate:

    python3 /var/lib/hermes/skills/pt-shared/scripts/pt_config_gate.py \
        /var/lib/hermes/pt/config.json

**Paste the gate's output verbatim.** Empty output is pass; anything it
prints is an invariant you have not satisfied yet — fix it before the next
question, not after the interview. The example shape lives beside the gate
at `pt-shared/references/config.example.json`.

When all three keys are in and the gate is silent, setup is done — and if
they named any sections, run `/var/lib/hermes/skills/news/pt-dashboard/scripts/register_crons.py`
once as setup's closing bring-up step so `pt-daily-edition` exists the
moment setup ends; paste its output and report its exit status. This is the
one cron registration a setup turn may do (it is the reviewed bring-up
script, not a hand-built schedule). If they named no sections, skip it — the
job is created by the first intake that adds a section or an assignment.

Then say so in one line — the timezone, the hour, whether the paper will
print, and that their sections are in — and invite the first topic. A first
research job is still pt-intake's, not this skill's.