#!/usr/bin/env python3
"""Register the Plow Times' crons, idempotently, from the topic store.

Why this exists at all. `hermes cron` persists jobs to
/var/lib/hermes/cron/jobs.json, which no rebuild replays -- so a rebuilt
agent would come up with subscriptions that never fire and nothing to diff
against. Keeping the spec here, derived from pt/topics.json (the one record
of what the owner asked to be watched), means "set up the plow times crons"
replays a reviewed derivation instead of improvising schedules from a
sentence. The same mechanism ld-dashboard's register_crons.py uses, with a
spec that is data-driven rather than fixed: the topic list changes.

The spec (design doc §3.6 and the personalized-paper plan §3.3/§6):

  pt-daily-edition       <min> <hour> * * *        one job; exists while at
                         computed as                least one section topic is
                         delivery.hour -            not cancelled OR one
                         lead_minutes (owner         assignment is pending/
                         zone, wraparound           running
                         exact)
  pt-subscription-<id>   0 <delivery.hour> * * *   one per subscription topic
                                                   not yet cancelled
  pt-oneoff-<id>         created by pt-intake at   one-time; its own prompt
                         the scheduled minute      self-removes after firing

This script therefore CREATES missing jobs and REMOVES pt-* jobs whose
topic is gone -- cancelled, delivered one-offs their prompt failed to
remove, or names with no topic behind them. "Created/removed as topics
change", the design doc calls it. It never touches a job whose name does
not start with pt-: those are not this agent's to manage.

It also RECONCILES drift, which create-if-missing alone does not: a job
that is registered with a different schedule or skill than the spec calls
for (the owner changed delivery.hour, the lead changed, the prompt's
contract moved) is removed and recreated. Without this, "already present,
skipped" means a changed delivery hour is silently ignored forever -- the
exact class of failure this script exists to prevent. Drift is only judged
when hermes's own jobs.json carries the field; a fixture or an older row
without a schedule is left alone rather than recreated on a guess.

Two refusals are the point of the script, both inherited from ld-dashboard:

  - an unreadable or unexpected jobs.json aborts. Never read "I could not
    tell what is registered" as "nothing is" -- that re-registers every job
    and duplicates all of them.
  - the container's TZ and the config's owner.timezone must agree. `hermes
    cron create` takes no per-job zone, so every schedule fires in the
    container's zone while the delivery hour is promised in the owner's;
    a silent mismatch is a paper that lands at the wrong hour, every night.

It runs INSIDE the container, where /opt/hermes/bin/hermes and that file
live -- from a turn, which inherits PLOW_HOME_CHANNEL from the gateway.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import date

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "pt-intake", "scripts"),
)

HERMES = "/opt/hermes/bin/hermes"
# Where `hermes cron` persists its jobs -- nothing replays it on a rebuild,
# which is the reason this script exists.
JOBS_FILE = "/var/lib/hermes/cron/jobs.json"
CONFIG_FILE = "/var/lib/hermes/pt/config.json"
# The only job names this spec owns. Pinned as a fullmatch so a name that
# does not parse is never interpreted, and a half-matching id never removes
# a job (see stale_names).
_JOB_NAME_RE = re.compile(r"^pt-(?P<kind>subscription|oneoff)-(?P<tid>t_[0-9a-f]{4})$")
# The one daily-paper job; no topic id because it is the whole paper, not a
# topic. Owned and swept by name, exactly like the id-borne jobs above.
DAILY_NAME = "pt-daily-edition"
DEFAULT_LEAD_MINUTES = 45

SUBSCRIPTION_PROMPT = (
    "Run pt-research on topic {tid} now (depth deep), then pt-edition for it. "
    "pt-edition writes edition.json, runs render_edition.py, and returns the "
    "renderer's chat output as the final response. When the edition is out, "
    "mark the topic delivered with pt-intake's topics.py and then mark it "
    "pending again, so tomorrow's run finds it."
)

# The daily paper's run prompt. It works in one cron-fired session: acquire
# the run lock (two runs racing would deliver a hollow edition), research
# every active section and every assignment due today, compile one
# edition.json, render it, deliver, then release the lock.
DAILY_PROMPT = (
    "Run the daily edition now, in one session. First run pt-shared's "
    "run_lock.py acquire --name daily-<today's date in the owner's zone> "
    "--stale-minutes 120; if its output is 'held', another run owns today's "
    "edition -- say NO_REPLY and stop. Then run pt-research over every active "
    "section and every assignment with run_on <= today, writing each topic's "
    "notes. Then run pt-edition for the batch -- it compiles edition.json "
    "from those notes, renders it, and returns the chat edition as the final "
    "response. Mark every topic it carried: sections delivered then pending, "
    "assignments delivered. Release the lock with pt-shared's run_lock.py "
    "release --name the same daily-<date>."
)

DELIVER_TARGET = "plow_chat:${PLOW_HOME_CHANNEL}"


def require_timezone_agreement(config_path=CONFIG_FILE, env=None):
    """Refuse to register if the config's zone is not the container's.

    Same guard ld-dashboard enforces, for the same reason: every schedule
    here is a bare cron expression and hermes cron create takes no per-job
    timezone, so jobs fire in the CONTAINER's zone while the delivery hour
    is promised in owner.timezone. A silently-wrong hour is worse than a
    refusal naming both zones. TZ (not /etc/localtime) is what Python and
    cron honour -- the ld gate measured the image's /etc/localtime pointing
    at UTC while TZ carries the real zone, so reading the symlink would
    refuse every correct config.
    """
    env = os.environ if env is None else env
    container = (env.get("TZ") or "").strip()
    if not container:
        raise SystemExit(
            "refusing to register: TZ is empty in this container. The image "
            "sets it at boot from AGENT_TZ, so an empty one means that step "
            "did not run and the schedules would fire in a zone nothing here "
            "can name."
        )
    path = pathlib.Path(config_path)
    try:
        owner = json.loads(path.read_text())["owner"]["timezone"]
    except FileNotFoundError:
        raise SystemExit(
            f"refusing to register: {path} is missing. pt-setup writes it; "
            "its owner.timezone is what every schedule here is written against."
        ) from None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(
            f"refusing to register: could not read owner.timezone from {path} "
            f"({exc!r})."
        ) from exc

    if str(owner or "").strip() != container:
        raise SystemExit(
            f"refusing to register: {path} says owner.timezone is "
            f"{owner!r} but this container runs in {container!r}. Every "
            "schedule here is a bare cron expression and hermes cron create "
            "takes no per-job zone, so editions would land at the wrong local "
            "hour -- silently. TZ is fixed at boot, so this means the config "
            "changed after the container started: restart it to pick the new "
            "zone up, or fix owner.timezone if THAT is what is wrong."
        )


def registered_jobs(jobs_path=JOBS_FILE):
    """What is already scheduled, from hermes's own persisted state.

    Reads the file `hermes cron` writes rather than parsing `hermes cron
    list` -- a human rendering nothing pins. Returns {name: is_runnable};
    a paused job is registered but will never fire, and the caller must
    tell those apart (re-registering duplicates it, skipping it silently
    strands it).

    The invariant with teeth: never read "I could not tell what is
    registered" as "nothing is". Only FileNotFoundError means empty -- an
    unreadable or unexpected file raises and stops the run.
    """
    try:
        jobs = json.loads(pathlib.Path(jobs_path).read_text())["jobs"]
    except FileNotFoundError:
        return {}
    return {
        job["name"]: bool(job["enabled"]) and not job["paused_at"]
        for job in jobs
    }


def resolve_deliver(deliver, env=None):
    """Expand every ${VAR} in a delivery target from the container environment.

    The chat uid is whichever chat the owner holds with this agent -- never
    a literal in this repo. First boot publishes PLOW_HOME_CHANNEL; run this
    from a turn, which inherits it from the gateway. Unset or blank REFUSES
    loudly: an empty target is a chat leg that silently delivers nowhere.
    """
    import re

    values = os.environ if env is None else env
    source = "the container environment" if env is None else "the injected env"

    def expand(match):
        name = match.group(1)
        value = (values.get(name) or "").strip()
        if not value:
            raise SystemExit(
                f"refusing to register: deliver target {deliver!r} needs {name}, "
                f"which is unset or blank in {source}. Registering without it "
                "would create a chat leg that silently delivers nowhere."
            )
        return value

    return re.sub(r"\$\{(\w+)\}", expand, deliver)


def load_delivery_hour(config_path=CONFIG_FILE):
    """delivery.hour from pt/config.json -- its exact 'HH:00' shape is the
    gate's contract; the hour part is all a schedule needs."""
    path = pathlib.Path(config_path)
    try:
        config = json.loads(path.read_text())
        return str(config["delivery"]["hour"])
    except FileNotFoundError:
        raise SystemExit(
            f"refusing to register: {path} is missing -- pt-setup owns it"
        ) from None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"refusing to register: malformed {path} ({exc!r}).") from exc


def load_lead_minutes(config_path=CONFIG_FILE):
    """delivery.lead_minutes from pt/config.json, defaulting to 45.

    The key is optional on purpose (the gate only validates it when present):
    an install written before the personalized paper existed has no
    lead_minutes, and a schedule that refuses to compute for it would strand
    a working agent. Absent means the default, not an error.
    """
    path = pathlib.Path(config_path)
    try:
        config = json.loads(path.read_text())
        raw = config.get("delivery", {}).get("lead_minutes", DEFAULT_LEAD_MINUTES)
    except FileNotFoundError:
        raise SystemExit(
            f"refusing to register: {path} is missing -- pt-setup owns it"
        ) from None
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise SystemExit(f"refusing to register: malformed {path} ({exc!r}).") from exc
    if isinstance(raw, bool) or not isinstance(raw, int) or not (0 <= raw <= 59):
        raise SystemExit(
            f"refusing to register: {path} has delivery.lead_minutes={raw!r}; "
            "it must be an integer 0-59 (minutes before delivery.hour)."
        )
    return raw


def daily_schedule(delivery_hour, lead_minutes):
    """The daily paper's cron expression, wraparound exact.

    delivery.hour is "HH:00" (the gate's contract). Subtracting the lead is
    done in minutes and taken modulo a day, so 00:00 - 45 min is the PREVIOUS
    day's 23:15 and yields "15 23 * * *" -- not "45 -1 * * *", which is not a
    cron expression, and not a schedule that fires a day late. A daily job
    fires at that local minute every day, which is exactly one edition per
    day at the promised moment.
    """
    hour = int(delivery_hour.split(":")[0])
    total = (hour * 60 - lead_minutes) % (24 * 60)
    return f"{total % 60} {total // 60} * * *"


def has_paper(topics):
    """True when the daily paper has anything to carry.

    A section is evergreen (pending, running or delivered all count); an
    assignment only counts while it can still appear (pending or running --
    a crashed run leaves it running on purpose, and the next edition must
    still exist to carry it late). Cancelled and delivered assignments are
    done, and must not keep the job alive forever.
    """
    return any(
        (t["kind"] == "section" and t["status"] != "cancelled")
        or (t["kind"] == "assignment" and t["status"] in ("pending", "running"))
        for t in topics
    )


def daily_job(delivery_hour, lead_minutes, env=None):
    """The one daily-paper job, when there is a paper to run."""
    return {
        "name": DAILY_NAME,
        "schedule": daily_schedule(delivery_hour, lead_minutes),
        "prompt": DAILY_PROMPT,
        "skill": "pt-research",
        "deliver": DELIVER_TARGET,
    }


def subscription_job(topic, delivery_hour, env=None):
    """The job spec for one subscription topic: nightly at the delivery hour."""
    hour = int(delivery_hour.split(":")[0])
    return {
        "name": f"pt-subscription-{topic['id']}",
        "schedule": f"0 {hour} * * *",
        "prompt": SUBSCRIPTION_PROMPT.format(tid=topic["id"]),
        "skill": "pt-research",
        "deliver": DELIVER_TARGET,
    }


def desired_jobs(topics, delivery_hour, env=None, lead_minutes=DEFAULT_LEAD_MINUTES):
    """The jobs the topic store calls for, in spec order.

    The daily edition comes first (it is the paper), then one job per
    subscription. Both the paper and subscriptions are separate products:
    subscriptions deliver their own edition, sections/assignments ride the
    paper.
    """
    jobs = []
    if has_paper(topics):
        jobs.append(daily_job(delivery_hour, lead_minutes, env))
    jobs.extend(
        subscription_job(t, delivery_hour, env)
        for t in topics
        if t["kind"] == "subscription" and t["status"] != "cancelled"
    )
    return jobs


def stale_names(topics, registered):
    """Registered pt-* jobs the topic store no longer calls for.

    A subscription job outlives only its non-cancelled topic; a one-off job
    outlives only a topic still pending or running (its prompt self-removes
    it after firing -- this sweep is the backstop, and prunes delivered,
    cancelled or vanished topics' leftovers). The daily job outlives only a
    paper that still exists -- any section not cancelled, or any assignment
    that can still run. Names not starting with pt- are never ours to remove.
    """
    by_id = {t["id"]: t for t in topics}
    stale = []
    for name in registered:
        if name == DAILY_NAME:
            if not has_paper(topics):
                stale.append(name)
            continue
        # One shape to match, pinned exactly: pt-subscription-t_9f2a or
        # pt-oneoff-t_0c11. A name that does not parse as one of those is
        # not this spec's to interpret, and a parse that half-matches an id
        # must not remove a job -- hence fullmatch, not prefix tests.
        match = _JOB_NAME_RE.fullmatch(name)
        if match is None:
            continue
        kind, tid = match.group("kind"), match.group("tid")
        topic = by_id.get(tid)
        if topic is None:
            stale.append(name)
        elif kind == "subscription" and topic["status"] == "cancelled":
            stale.append(name)
        elif kind == "oneoff" and topic["status"] in ("delivered", "cancelled"):
            stale.append(name)
    return stale


def registered_specs(jobs_path=JOBS_FILE):
    """The registered jobs' own fields, for drift detection.

    registered_jobs() answers only "does it run"; this answers "does it match
    the spec". Only fields hermes actually persisted are returned -- a
    missing key means "unknown", and job_drift() leaves an unknown alone
    rather than recreating on a guess (older rows, and the test fixtures,
    carry no schedule).
    """
    try:
        jobs = json.loads(pathlib.Path(jobs_path).read_text())["jobs"]
    except FileNotFoundError:
        return {}
    return {
        job["name"]: {
            "schedule": job.get("schedule"),
            "skill": job.get("skill"),
            "deliver": job.get("deliver"),
        }
        for job in jobs
    }


def job_drift(job, spec):
    """True when a registered job's persisted fields contradict the spec.

    Only a field that is BOTH persisted and different is a drift; an absent
    field is silence, not a mismatch. Schedule and skill are the fields a
    spec change actually moves (the delivery hour, the lead, the contract);
    deliver is not compared because its resolved form depends on the turn's
    environment and a false drift would recreate every job on every run.
    """
    for key in ("schedule", "skill"):
        stored = spec.get(key)
        if stored is not None and stored != job[key]:
            return True
    return False


def prune_runtime(topics, home):
    """Best-effort housekeeping of the paper's scratch space.

    Removes daily locks older than today (a lock from a day that will never
    fire again) and the notes directory of every terminal topic (delivered
    one-offs and assignments, everything cancelled). Failures are reported,
    never fatal: a stale scratch file is not worth refusing a registration
    over, and the next run prunes again. `home` is the pt state directory.
    """
    run_dir = pathlib.Path(home) / "run"
    if not run_dir.is_dir():
        return []
    removed = []
    today = date.today().isoformat()
    terminal = {
        t["id"] for t in topics
        if t["status"] == "cancelled"
        or (t["kind"] in ("one_off", "assignment") and t["status"] == "delivered")
    }
    for entry in sorted(run_dir.iterdir()):
        try:
            if entry.name.startswith("daily-") and entry.name.endswith(".lock"):
                stamp = entry.name[len("daily-"):-len(".lock")]
                if stamp < today:
                    entry.unlink()
                    removed.append(str(entry))
            elif entry.is_dir() and entry.name in terminal:
                shutil.rmtree(entry)
                removed.append(str(entry))
        except OSError as exc:
            print(f"WARNING: could not prune {entry}: {exc!r}")
    return removed


def create_argv(job, env=None):
    argv = [HERMES, "cron", "create", job["schedule"], job["prompt"],
            "--name", job["name"], "--skill", job["skill"]]
    if job["deliver"]:
        argv += ["--deliver", resolve_deliver(job["deliver"], env)]
    return argv


def _run(argv):
    return subprocess.run(argv, capture_output=True, text=True)


def main(argv=None, runner=_run, jobs_path=JOBS_FILE, config_path=CONFIG_FILE, env=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The script takes no flags; parse_args(None) on the CLI is sys.argv[1:]
    # == empty, but in-process callers pass [] so argparse never reads
    # the test runner's argv.
    parser.parse_args(argv if argv is not None else [])

    if not shutil.which(HERMES) and not os.path.exists(HERMES):
        raise SystemExit(f"{HERMES} not found -- run this inside the agent container")

    require_timezone_agreement(config_path, env)
    delivery_hour = load_delivery_hour(config_path)
    lead_minutes = load_lead_minutes(config_path)

    # The topic store, via pt-intake's single reader -- so a broken
    # topics.json refuses here too, rather than reading as "no topics" and
    # pruning every subscription job this run could have kept.
    import topics as topics_mod
    topics = topics_mod.load_topics()

    for path in prune_runtime(topics, topics_mod.home()):
        print(f"pruned: {path}")

    registered = registered_jobs(jobs_path)
    specs = registered_specs(jobs_path)
    paused = []

    for job in desired_jobs(topics, delivery_hour, env, lead_minutes):
        if job["name"] in registered:
            if not registered[job["name"]]:
                print(
                    f"WARNING: {job['name']} is registered but PAUSED -- it will "
                    "never fire, and this leaves it alone rather than "
                    f"duplicating it. Resume it: {HERMES} cron resume {job['name']}"
                )
                paused.append(job["name"])
                continue
            spec = specs.get(job["name"], {})
            if not job_drift(job, spec):
                print(f"already present, skipped: {job['name']}")
                continue
            proc = runner([HERMES, "cron", "remove", job["name"]])
            if proc.returncode != 0:
                raise SystemExit(
                    f"could not remove drifted job {job['name']}:\n"
                    f"{proc.stdout}\n{proc.stderr}"
                )
            print(
                f"recreating drifted job: {job['name']} "
                f"(was {spec.get('schedule')!r}, now {job['schedule']!r})"
            )
        proc = runner(create_argv(job, env))
        if proc.returncode != 0:
            raise SystemExit(
                f"could not register {job['name']}:\n{proc.stdout}\n{proc.stderr}"
            )
        print(f"registered: {job['name']} ({job['schedule']})")

    for name in stale_names(topics, registered):
        proc = runner([HERMES, "cron", "remove", name])
        if proc.returncode != 0:
            raise SystemExit(
                f"could not remove stale job {name}:\n{proc.stdout}\n{proc.stderr}"
            )
        print(f"removed stale job: {name}")

    if paused:
        raise SystemExit(
            f"registered what was missing, but {len(paused)} job(s) are "
            f"PAUSED and will never fire: {', '.join(paused)} -- "
            f"{HERMES} cron resume <name>"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())