#!/usr/bin/env python3
"""convert_delivery.py -- owner's local HH:MM in their IANA zone -> container HH:MM.

pt-setup learns the owner's zone from Latch location (not by asking). The
owner names a wall-clock time in that zone; hermes cron fires in the
container's TZ. This script is the only conversion — never mental UTC
offsets. Prints one HH:MM line.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_HOUR_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def convert(local_hour, owner_tz_name, container_tz_name):
    """Return container-local HH:MM for local_hour on today's date in owner_tz."""
    if not (isinstance(local_hour, str) and _HOUR_RE.fullmatch(local_hour)):
        sys.exit(f"error: {local_hour!r} is not a strict HH:MM hour")
    try:
        owner_tz = ZoneInfo(owner_tz_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        sys.exit(f"error: unknown owner timezone {owner_tz_name!r}")
    try:
        container_tz = ZoneInfo(container_tz_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        sys.exit(f"error: unknown container timezone {container_tz_name!r}")
    hour_s, minute_s = local_hour.split(":")
    today = datetime.now(owner_tz).date()
    moment = datetime(
        today.year, today.month, today.day,
        int(hour_s), int(minute_s),
        tzinfo=owner_tz,
    )
    return moment.astimezone(container_tz).strftime("%H:%M")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--local-hour", required=True, help="HH:MM in the owner's zone")
    parser.add_argument("--owner-tz", required=True, help="IANA zone from Latch location")
    parser.add_argument(
        "--container-tz", default=None,
        help="IANA zone; default is the TZ environment variable",
    )
    args = parser.parse_args(argv)
    container = (args.container_tz or os.environ.get("TZ") or "").strip()
    if not container:
        sys.exit(
            "error: container TZ is empty — cannot convert. Set TZ in "
            "compose.yml's environment and restart."
        )
    print(convert(args.local_hour, args.owner_tz, container))
    return 0


if __name__ == "__main__":
    sys.exit(main())
