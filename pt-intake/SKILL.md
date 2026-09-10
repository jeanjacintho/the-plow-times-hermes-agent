---
name: pt-intake
description: Classify a chat message into a research topic — new topic or status question, one-off or subscription, quick or deep — write it to pt/topics.json via the topics script, and schedule the run that will produce its edition. Use on every owner chat turn that is not a status question. Status questions (list my topics, stop watching X, when will it land) are answered from the files, not this skill's scheduling path. Never research inside the turn.
---

# pt-intake — a chat message becomes a scheduled research job

You classify; a later session researches. **Never run pt-research inside the
turn that received the request** — a chat turn that blocks for minutes while
a browser crawls is the single worst thing this agent can do. The turn's job
is: classify, write, schedule, confirm with a time. Nothing more.

## Read the state first, every turn

Two local files, both cheap:

- `/var/lib/hermes/pt/topics.json` — run `topics.py list` for the readable form
- `/var/lib/hermes/pt/config.json` — delivery preferences (run
  `../../pt-shared/scripts/pt_config_gate.py` on it if it looks wrong)

If the config is missing keys, this is a first run: SOUL.md routes that to
`pt-setup`. Answer status questions from these files, never from session
memory — another session may have delivered since yours started.

## Status questions — answer from the file, then stop

These are ordinary turns, not classifications. Do them and end:

- **"what are you watching" / "list my topics"** — run
  `../../pt-intake/scripts/topics.py list` and render it as a short list:
  each active topic, its kind, when its edition last landed.
- **"stop watching X" / "stop the coffee one"** — resolve X against the
  active topics; if ambiguous, ask which one and stop. Then
  `topics.py cancel <id>`, and immediately run
  `../../pt-dashboard/scripts/register_crons.py` so the nightly job is
  removed now rather than at the next bring-up. Confirm in one line.
- **"when will it land" / "did it come?"** — read the topic's `status` and
  `scheduled_for` / `last_edition_at` and answer. A missing edition in this
  session's history is not evidence it never landed.

## New topic — classify, then write

Decide three things, in this order:

**1. Is this a topic at all?** A greeting, a question about the agent, a
complaint about an edition — none of these is a topic. Answer it like a
person and stop. A question the OWNER wants researched is a topic only when
the answer must be *looked up* on the web, not when it's something you know
or can say in a line.

**2. One-off or subscription?** A subscription is anything with a cadence in
it — "every night", "keep an eye on", "when there's news", "watch this".
Everything else is a one-off. When the owner asks for "X, tell me later"
that is a one-off, not a subscription. When you genuinely cannot tell
whether they want it once or watched, ask — one question, then classify
their answer. Do not silently guess a cadence into someone's mornings.

**3. Quick or deep?** The clock decides the default: a topic asked during
the owner's waking day is `quick`; a topic asked late at night, anything
they said to "keep an eye on", and every subscription's nightly run is
`deep`. An explicit "properly" / "deep dive" overrides upward; an explicit
"quick, one line" overrides downward.

Then write it — this script is the ONLY writer for topics.json:

    ../../pt-intake/scripts/topics.py add --text "<the topic, in the owner's words>" \
        --kind one_off|subscription --depth quick|deep [--scheduled-for <ISO8601>]

Paste its output. The `id` it prints is the topic's identity everywhere
else — cron names, delivery, cancellation.

## Schedule the run — one-time crons, never inline

All jobs fire in the container's zone (the image sets it from AGENT_TZ, and
register_crons.py refuses a disagreement with `owner.timezone` — so
container time is owner time). Every job carries
`--deliver plow_chat:${PLOW_HOME_CHANNEL}`: the run's final response IS the
edition, and relaying it is the chat leg.

- **One-off, quick** — a one-time job ~3 minutes out. Compute the local time
  now+3m and register it as a 5-field expression with that exact minute:
  `<min> <hour> <dom> <month> *`, name `pt-oneoff-<id>`, skill `pt-research`,
  prompt "Run pt-research on topic <id> now, then pt-edition for it, and
  return the edition as the final response. When the edition is delivered,
  mark the topic delivered with topics.py and remove this job with
  `hermes cron remove pt-oneoff-<id>`." Record the scheduled moment with
  `topics.py mark`-adjacent `add --scheduled-for` (you pass it at add time).
- **One-off, deep** — the same, at the next `delivery.hour` from
  pt/config.json (today if it has not passed, tomorrow otherwise), so the
  result lands with the morning paper.
- **Subscription** — nothing to schedule here: write the topic, then run
  `../../pt-dashboard/scripts/register_crons.py` so the nightly job
  `pt-subscription-<id>` exists now (it is create-if-missing and idempotent).

If `hermes cron create` fails, say so — a topic whose run was never
scheduled is a promise with no paper behind it, and the owner must hear it
rather than wait for an edition that will never come.

## Confirm, in one line

The turn's final response is a confirmation with a time, not a progress
report: "On it — an edition on <topic> lands here in ~3 minutes" or "You'll
get one on <topic> every morning at 7." Never narrate the mechanics (no
"writing topics.json", no "scheduling a cron"). The edition, when it lands,
speaks for itself.

## Budgeted statuses, kept honest

The run itself moves the topic through `pending → running → delivered`
(via `topics.py mark`, from the cron-fired session). A subscription goes
back to `pending` after delivery, awaiting tomorrow's fire. Never mark a
topic delivered yourself in the intake turn — nothing has been delivered
yet, and a delivered mark on a topic whose edition failed is how a silent
gap looks like a working paper.