---
name: pt-dashboard
description: The Plow Times' cron spec — one nightly job per active subscription plus the pruning of stale pt-* jobs — and the idempotent registration that replays them from the topic store. Use when asked to set up, re-register, inspect or repair the paper's crons, after rebuilding the agent's home, and after pt-intake adds or cancels a subscription.
---

# The Plow Times — the cron spec

Two shapes plus the paper, all derived from `/var/lib/hermes/pt/topics.json`
at run time — unlike `ld-dashboard`'s fixed seven rows, this spec is the
topic list:

| job | schedule | notes |
|---|---|---|
| `pt-daily-edition` | `<min> <hour> * * *`, computed as `delivery.hour − delivery.lead_minutes` (default 0) in the owner's zone, wraparound exact | one job; the **main** paper: desks, sections with no `deliver_at` (or `deliver_at` equal to this hour), and assignments due today |
| `pt-daily-edition-<n>` (n ≥ 2) | same computation, against `delivery.extra_hours[n-2]` | reprint of that **same main** roster later the same day — not a different newspaper |
| `pt-paper-HHMM` | `<min> <hour> * * *` from a section `deliver_at` that is not `delivery.hour` (same lead subtraction) | one job per distinct hour; desks plus only the sections at that hour. Two sections at 12:30 share `pt-paper-1230`. A cancelled last section at that hour is pruned |
| `pt-subscription-<id>` | `<min> <hour> * * *` from `delivery.hour` (container TZ, both parts) | one per subscription topic not yet cancelled; created and removed as topics change |
| `pt-oneoff-<id>` | one-time, `now + 3m` (quick) or next `delivery.hour` (deep) | created by pt-intake at the scheduled minute; its own prompt self-removes it after firing — this script's sweep is the backstop |

The daily schedule is computed in minutes and taken modulo a day, so
`00:00 − 0min` is `0 0 * * *` (midnight itself). A non-zero lead still
wraps: `00:00 − 20min` is `40 23 * * *` (the previous evening). `00:00` is
a real delivery hour and the wraparound is a tested case, not an accident.

Every row still carries `--deliver plow_chat:${PLOW_HOME_CHANNEL}` (an
unset or blank `PLOW_HOME_CHANNEL` refuses the registration by name). The
edition itself is posted mid-run as the PDF only (`post_to_chat.py --pdf`,
empty body). The job's final response is `NO_REPLY` so that `--deliver`
does not also send the research transcript. An empty target is a chat
leg that silently delivers nowhere.

The daily run additionally takes a **run lock** with
`pt-shared/scripts/run_lock.py` (see the prompt this script writes): two runs
at once — a manual `hermes cron run` beside the scheduled fire — would
otherwise see every section already `running`, compile an empty edition, and
deliver it. The lock is a file created with O_EXCL, so the two runs agree on
one owner.

## Registering

**This is a bring-up step, not a repair step.** A rebuild does not replay
`jobs.json`, so an instance brought up without it has subscriptions that
never fire — and nothing to diff against, because the failure looks
identical to a producer running and finding nothing. Run it after `sign-in`,
after any rebuild of the home, at the close of `pt-setup` (so the first
paper's job exists as soon as setup ends), and after pt-intake adds or
cancels a subscription, section or assignment.

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
is absent. It also **reconciles drift**: a registered job whose persisted
`schedule` or `skill` no longer matches the spec — the owner changed the
delivery hour or lead, the prompt's contract moved — is removed and recreated.
`--deliver` is expanded for every create and recreate **before** any
`cron remove`, so a blank `PLOW_HOME_CHANNEL` refuses without deleting
the morning job. Without that, "already present, skipped" would mean a
changed delivery hour is silently ignored forever. Drift is judged only against fields hermes
actually persisted; an absent field is left alone, not recreated on a guess.
It removes `pt-daily-edition-<n>` whose number exceeds the current
`delivery.extra_hours` count, `pt-paper-HHMM` jobs whose hour no longer has
an active section, `pt-subscription-*` jobs whose
topic is cancelled, and `pt-oneoff-*` jobs whose topic is delivered,
cancelled or missing. The canonical `pt-daily-edition` stays registered
after setup — weather and calendar still need a run even with no news
topics. It never touches a job whose name is not one of
`pt-daily-edition`, `pt-daily-edition-<n>`, `pt-paper-*`, `pt-subscription-*` or
`pt-oneoff-*` with a real topic id behind it: those are not this spec's to
interpret or remove — **hand-registering a job by shell command instead of
adding a `delivery.extra_hours` entry and re-running this script is exactly
the mistake this spec exists to make unnecessary**, and such a job is
invisible to this sweep forever (measured live: a hand-made
`pt-daily-edition-2` sat in `jobs.json` with a schedule that had nothing to
do with the hour the owner asked for, and no one but the owner removing it
by hand would ever fix that). As housekeeping it also prunes old
daily locks and notes of terminal topics from `/var/lib/hermes/pt/run/`,
reporting failures without ever failing the run over a scratch file.

Two refusals are inherited from `ld-dashboard` and are the whole reason this
is a script and not a habit:

- **An unreadable or unexpected `jobs.json` aborts.** Never read "I could
  not tell what is registered" as "nothing is" — that re-registers every
  job and duplicates all of them.
- **The container's `TZ` and `owner.timezone` must both be nameable.**
  `hermes cron create` takes no per-job zone, so every schedule fires in the
  container's own zone, always — `owner.timezone` no longer has to equal it:
  pt-setup converts the owner's stated local time into the container's local
  time with `zoneinfo` before writing `delivery.hour`, so this script trusts
  `delivery.hour` as already correct for the zone it is running in. What it
  still refuses is an empty container `TZ` (nothing here could even attempt
  the conversion) or a blank `owner.timezone` (pt-setup's conversion step,
  and every reply that names it back to the owner, need it).

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