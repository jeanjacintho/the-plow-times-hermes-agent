#!/usr/bin/env python3
"""Fail if runtime/SOUL.md is longer than the effective Hermes limit.

Hermes truncates context files silently in chat; the warning is only in
`docker compose logs`. Default limit is 20 000; runtime/config.yaml raises
it, and merge_pt_seed_config.py carries that into the home config.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERMES_DEFAULT = 20000


def effective_limit(config_text):
    match = re.search(r"^context_file_max_chars:\s*(\d+)\s*$", config_text, re.M)
    return int(match.group(1)) if match else HERMES_DEFAULT


def check(root=None):
    root = ROOT if root is None else Path(root)
    limit = effective_limit((root / "runtime" / "config.yaml").read_text(encoding="utf-8"))
    n = len((root / "runtime" / "SOUL.md").read_text(encoding="utf-8"))
    if n > limit:
        raise SystemExit(f"SOUL.md is {n} chars; Hermes truncates above {limit}")
    return n, limit


def main(argv=None):
    n, limit = check()
    print(f"SOUL.md {n} <= {limit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
