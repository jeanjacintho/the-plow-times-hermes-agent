#!/usr/bin/env python3
"""Archive prior daily scratch so a run cannot mistake it for today's work."""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path


def _dated_directory(name: str) -> bool:
    if len(name) != 10:
        return False
    try:
        date.fromisoformat(name)
        return True
    except ValueError:
        return False


def _topic_directory(name: str) -> bool:
    return len(name) == 6 and name.startswith("t_") and all(c in "0123456789abcdef" for c in name[2:])


def _scratch(path: Path) -> bool:
    if path.is_dir():
        return path.name.startswith("desk-") or _topic_directory(path.name) or _dated_directory(path.name)
    return path.name in {"chat-status.json", "seal-session.json"}


def prepare(pt_home: Path, now: datetime | None = None) -> Path | None:
    run = pt_home / "run"
    run.mkdir(parents=True, exist_ok=True)
    scratch = sorted((path for path in run.iterdir() if _scratch(path)), key=lambda path: path.name)
    if not scratch:
        return None

    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S")
    archive = pt_home / f"run.archive-{stamp}"
    suffix = 2
    while archive.exists():
        archive = pt_home / f"run.archive-{stamp}-{suffix}"
        suffix += 1
    archive.mkdir()
    for path in scratch:
        path.replace(archive / path.name)
    return archive


def main() -> None:
    pt_home = Path(os.environ.get("PT_HOME", "/var/lib/hermes/pt"))
    archive = prepare(pt_home)
    print(f"ARCHIVED {archive}" if archive else "READY")


if __name__ == "__main__":
    main()
