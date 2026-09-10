---
name: pt-dashboard
description: The Plow Times' cron spec — one nightly job per active subscription plus the pruning of stale pt-* jobs — and the idempotent registration that replays them from the topic store. Use when asked to set up, re-register, inspect or repair the paper's crons, after rebuilding the agent's home, and after pt-intake adds or cancels a subscription.
---

# The Plow Times — the cron spec

Two shapes, both derived from `/var/lib/hermes/pt/topics.json` at run time —
unlike `ld-dashboard`'s fixed seven rows, this spec is the topic list:

| job | schedule | notes |
|---|---|---|
| `pt-subscription-<id>` | `0 <delivery.hour> * * *` (container TZ) | one per subscription topic not yet cancelled; created and removed as topics change |
| `pt-oneoff-<id>` | one-time, `now + 3m` (quick) or next `delivery.hour` (deep) | created by pt-intake at the scheduled minute; its own prompt self-removes it after firing — this script's sweep is the backstop |

Every row's chat leg is `plow_chat:${PLOW_HOME_CHANNEL}`: the run's final
response IS the edition, and the gateway relays it. An unset or blank
`PLOW_HOME_CHANNEL` refuses the registration by name — an empty target is a
chat leg that silently delivers nowhere.

## Registering

**This is a bring-up step, not a repair step.** A rebuild does not replay
`jobs.json`, so an instance brought up without it has subscriptions that
never fire — and nothing to diff against, because the failure looks
identical to a producer running and finding nothing. Run it after `sign-in`,
after any rebuild of the home, and after pt-intake adds or cancels a
subscription.

    /var/lib/hermes/skills/pt-dashboard/scripts/register_crons.py

**Then paste its output verbatim and report its exit status. The run is not
done until you have.** The script signals every refusal it has — a missing
or unusable config, an `owner.timezone` that is not the container's zone, an
empty `TZ`, a blank `PLOW_HOME_CHANNEL`, a failed `cron create` or `remove`,
a registered-but-PAUSED job — through its output and a non-zero exit, and a
turn does not propagate an exit code. If you summarise instead of pasting,
"set up the crons, though one was paused" is an honest sentence describing a
run that failed, and nobody can tell. Do not paraphrase, and do not call it
done on a non-zero exit.

Create-if-missing, so it is safe to re-run: it reads what is already
scheduled from `/var/lib/hermes/cron/jobs.json` (the file `hermes cron`
itself writes — never the text of `hermes cron list`) and creates only what
is absent. It also removes `pt-*` jobs whose topic is cancelled, delivered
(one-offs), or missing — and it never touches a job whose name is not a
`pt-subscription-*` or `pt-oneoff-*` with a real topic id behind it: those
are not this spec's to interpret or remove.

Two refusals are inherited from `ld-dashboard` and are the whole reason this
is a script and not a habit:

- **An unreadable or unexpected `jobs.json` aborts.** Never read "I could
  not tell what is registered" as "nothing is" — that re-registers every
  job and duplicates all of them.
- **A timezone disagreement refuses everything.** `hermes cron create`
  takes no per-job zone, so every schedule fires in the container's zone
  while the delivery hour is promised in the owner's. The script compares
  the container's `TZ` with `owner.timezone` in `pt/config.json` and refuses
  to register anything when they differ, naming both zones — a silently
  wrong delivery hour is the one failure nobody would notice until a
  morning paper showed up at noon.

A paused job is neither skipped nor duplicated: it is left alone, named, and
the run exits non-zero after everything else finishes — the same contract
`ld-dashboard` holds.

## Verifying an unattended run

From inside the container:

    /opt/hermes/bin/hermes cron list          # is the job there, and not paused?
    /opt/hermes/bin/hermes cron run <job-id>  # force one
    /opt/hermes/bin/hermes cron runs          # then look for the edition in chat

A forced run exercises the whole path a nightly fire would take once it
starts. What it does not prove is that the running gateway loaded a
newly-created schedule — the `source=builtin` row in `cron runs` is the only
thing that proves that, and it takes a real scheduled fire (measured on the
life-assistant image: the gateway does load new jobs without a restart; see
ld-dashboard's sheet if the image has moved since).

A subscription delivered unattended at least once is the MVP's own bar
(docs/roadmap.md): confirm the edition in the chat, not just that the cron
fired — a run that completes with no edition is the failure this whole
skill exists to surface.