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

The spec (design doc §3.6):

  pt-subscription-<id>   0 <delivery.hour> * * *   one per subscription topic
                                                   not yet cancelled
  pt-oneoff-<id>         created by pt-intake at   one-time; its own prompt
                         the scheduled minute      self-removes after firing

This script therefore CREATES missing subscription jobs and REMOVES pt-*
jobs whose topic is gone -- cancelled, delivered one-offs their prompt
failed to remove, or names with no topic behind them. "Created/removed as
topics change", the design doc calls it. It never touches a job whose name
does not start with pt-: those are not this agent's to manage.

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

SUBSCRIPTION_PROMPT = (
    "Run pt-research on topic {tid} now (depth deep), then pt-edition for it, "
    "and return the edition as the final response. When the edition is out, "
    "mark the topic delivered with pt-intake's topics.py and then mark it "
    "pending again, so tomorrow's run finds it."
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


def desired_jobs(topics, delivery_hour, env=None):
    """The pt-subscription jobs the topic store calls for, in spec order."""
    return [
        subscription_job(t, delivery_hour, env)
        for t in topics
        if t["kind"] == "subscription" and t["status"] != "cancelled"
    ]


def stale_names(topics, registered):
    """Registered pt-* jobs the topic store no longer calls for.

    A subscription job outlives only its non-cancelled topic; a one-off job
    outlives only a topic still pending or running (its prompt self-removes
    it after firing -- this sweep is the backstop, and prunes delivered,
    cancelled or vanished topics' leftovers). Names not starting with pt-
    are never ours to remove.
    """
    by_id = {t["id"]: t for t in topics}
    stale = []
    for name in registered:
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

    # The topic store, via pt-intake's single reader -- so a broken
    # topics.json refuses here too, rather than reading as "no topics" and
    # pruning every subscription job this run could have kept.
    import topics as topics_mod
    topics = topics_mod.load_topics()

    registered = registered_jobs(jobs_path)
    paused = []

    for job in desired_jobs(topics, delivery_hour, env):
        if job["name"] in registered:
            if registered[job["name"]]:
                print(f"already present, skipped: {job['name']}")
            else:
                print(
                    f"WARNING: {job['name']} is registered but PAUSED -- it will "
                    "never fire, and this leaves it alone rather than "
                    f"duplicating it. Resume it: {HERMES} cron resume {job['name']}"
                )
                paused.append(job["name"])
            continue
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