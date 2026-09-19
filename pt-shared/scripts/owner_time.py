"""owner_time.py -- the owner's own clock, from pt/config.json, not the
container's.

register_crons.py no longer requires the container's TZ to equal
owner.timezone (see its module docstring): pt-setup converts the owner's
stated local time into the container's local hour once, at write time, but
never touches the container's own TZ. A page named for the owner's day, or
a heading stamped with the owner's own hour, can therefore land a day (or
an hour) off whatever the container's clock reads. Two callers need the
owner's own now -- history.py's seven-day window, record_edition.py's
`## HH:MM edition` heading and `created`/`updated` -- so this is their one
shared source instead of two.

owner_now()/owner_today() fall back to the container's own clock only when
the config file or the owner.timezone key is genuinely absent. A config
that exists but can't be trusted (bad JSON, an unreadable file, an unknown
zone name) raises instead of guessing -- a silently wrong window or heading
would read as valid.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG = Path("/var/lib/hermes/pt/config.json")


def owner_now(config_path=CONFIG):
    """An aware datetime in the owner's own zone."""
    try:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return datetime.now().astimezone()
    try:
        tz = config["owner"]["timezone"]
    except (KeyError, TypeError):
        return datetime.now().astimezone()
    return datetime.now(ZoneInfo(tz))


def owner_today(config_path=CONFIG):
    return owner_now(config_path).date()
