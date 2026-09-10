# The Plow Times

> [!NOTE]
> **Planning stage.** This directory currently holds design docs only — no
> skills, no runtime, no code. See [`docs/`](docs/) for the full plan. Treat
> this README as the pitch a judge or a teammate reads first, not as a
> description of anything that runs yet.

A [Hermes](https://howto.plow.co/hermes) agent — texted from iMessage over the
Plow Chat platform — that turns any question into an autonomous overnight (or
few-minute) research job, and delivers the result as a formatted "edition":
in the chat, and on paper if the owner has a printer within reach of their
Mac.

You text it a topic. It researches — driving the owner's own Mac browser
through [Latch](https://howto.plow.co/latch), the same mechanism
`property-hunt-hermes-agent` uses to browse listings — for a bounded time
budget, then hands back a synthesized, sourced brief. Ask it something
throw-away and it answers in a few minutes; ask it to keep an eye on
something and it re-runs every night and the edition is waiting when you wake
up.

## Goal

An agent that works while you're not looking, produces something you can
hold up as proof, and is trivial for someone else to spin up and try. This
project aims to land on Plow's [Agent
Index](https://aiworthusing.com/agent-index) leaderboard on that strength: a
short demo video, a one-line pitch, and a repo someone can register and run
in one `agent-mgr` command.

## Why this and not another life-assistant skill

[`life-assistant-hermes-agent`](../life-assistant-hermes-agent) is scoped to
one household's logistics: the calendar, the wall dashboard, family message
triage. It only ever knows about *your* life, and it runs on a fixed daily
schedule of fixed producers (weather, sports, digest…).

The Plow Times is the opposite shape on purpose:

| | life-assistant | The Plow Times |
|---|---|---|
| Domain | fixed: family/calendar/dashboard | open: whatever you ask it to research |
| Trigger | fixed daily crons | a chat message, any time, about anything |
| Output | wall-mounted dashboard cards | a chat "edition" + optional printed page |
| Data it needs about you | family, calendar accounts, iMessage | nothing durable except topics you gave it |
| Demo in 60 seconds | hard — needs your real calendar/family data | easy — ask it anything live, on stage |

Same Hermes skeleton (`runtime/SOUL.md`, `runtime/config.yaml`, `pt-*`
skills mirroring `ld-*`, cron registration through `agent-mgr`), deliberately
different job.

## Documents

- [`docs/superpowers/specs/2026-09-09-the-plow-times-design.md`](docs/superpowers/specs/2026-09-09-the-plow-times-design.md) —
  the full architecture: skills, data model, request lifecycle, cron spec,
  delivery formats, risks.
- [`docs/demo-script.md`](docs/demo-script.md) — the live hackathon demo
  runbook: what to ask on stage, what to have pre-baked as a fallback, timing.
- [`docs/leaderboard-submission.md`](docs/leaderboard-submission.md) — the
  plan for getting this onto the Agent Index leaderboard: what "one-click
  deployable" means concretely here, and the video/blurb/image to record.
- [`docs/roadmap.md`](docs/roadmap.md) — MVP scope for the hackathon window
  vs. stretch goals for after.

## Status

Design only. Nothing in this repo has been built. The next step, once this
plan is reviewed, is an implementation plan for the MVP skills in
`docs/roadmap.md`.
