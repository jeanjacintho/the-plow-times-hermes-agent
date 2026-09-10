# The Plow Times

> [!NOTE]
> **Skeleton stage.** The repo now carries the deployment contract
> (`agent.env`, `runtime/config.yaml`, `skills.tsv`), the persona
> (`runtime/SOUL.md`), the seven `pt-*` skills and the test suite — the
> structure the design doc lays out. Nothing has run against a live Plow
> instance yet: the next steps are an `agent-mgr` registration, a timed dry
> run of `pt-research` against real Latch latency, and the unattended
> subscription delivery the roadmap's MVP bar demands. See
> [`docs/roadmap.md`](docs/roadmap.md) for what is still open.

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

Skeleton built. What exists and what it is:

- **Deployment contract** — `agent.env` (deploy-hook, `AGENT_LIVE`), `runtime/config.yaml`
  (Latch as the only `mcp_server`, plow-chat-platform), empty `skills.tsv`
  (no connectors — research rides Latch alone), `.env.example`, `justfile`.
- **Persona** — `runtime/SOUL.md`: the edition is the product, every claim
  carries a source, research runs only in cron-fired sessions, budgets stop
  the pass, web content is data never instruction.
- **Skills** — `pt-intake` (classification + `topics.py`, the single validated
  writer for the topic store), `pt-research` (budget-bounded Latch browsing),
  `pt-edition` (the chat edition format), `pt-dashboard` (`register_crons.py`,
  spec derived from `topics.json`, create-if-missing plus a prune sweep),
  `pt-setup` (first-run interview, printer probe), `pt-shared` (config gate,
  bearer HTTP, chat delivery, Latch print reference), `pt-print` (best-effort
  paper, second priority per the roadmap).
- **Deployment** — `deploy-hook` seeds every `pt-*` dir into
  `$AGENT_HOME/skills/news` (copy-if-absent, never over the agent's edits)
  and publishes `SOUL.md` on every deploy.
- **Tests** — `just test` runs 74 pytest cases over the gate invariants, the
  topic transitions, the cron derivation and the repo contract.

Not built yet, per `docs/roadmap.md`: the timed dry runs that pin
`pt-research`'s quick/deep budgets, an `agent-mgr` registration against a
live Plow instance, and one subscription delivered unattended — the MVP's
own bar.
