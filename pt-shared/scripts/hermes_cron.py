"""Hermes's persisted cron jobs: the one reader of jobs.json and its runnable rule."""
import json
import pathlib

# Where `hermes cron` persists its jobs -- nothing replays it on a rebuild.
JOBS_FILE = "/var/lib/hermes/cron/jobs.json"


def job_rows(jobs_path):
    """hermes's persisted job rows; only a missing file means none."""
    try:
        return json.loads(pathlib.Path(jobs_path).read_text())["jobs"]
    except FileNotFoundError:
        return []


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
    return {
        job["name"]: bool(job["enabled"]) and not job["paused_at"]
        for job in job_rows(jobs_path)
    }
