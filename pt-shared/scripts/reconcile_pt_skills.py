#!/usr/bin/env python3
"""Seed pt-* skills into AGENT_HOME, the same rule Hermes bundled_manifest uses.

Update a copy we last wrote and the agent has not edited. Keep a copy the
agent has edited. Measured as a review finding: deploy-hook used to skip
any non-empty dest, so a skill PR never reached an agent-mgr home.

usage: reconcile_pt_skills.py <AGENT_HOME>
Prints one status line per pt-* skill. Exit 0 on success.
This script lives at <checkout>/pt-shared/scripts/reconcile_pt_skills.py;
the checkout root is parents[2].
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

STAMP = ".the-plow-times-origin"
SKIP_NAMES = {STAMP, ".DS_Store"}


def _checkout_root():
    return Path(__file__).resolve().parents[2]


def dir_hash(directory):
    """MD5 of relative paths + bytes, ignoring the stamp and bytecode."""
    hasher = hashlib.md5()
    root = Path(directory)
    if not root.is_dir():
        return ""
    files = []
    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        if fpath.name in SKIP_NAMES or fpath.suffix == ".pyc":
            continue
        if "__pycache__" in fpath.parts:
            continue
        files.append(fpath)
    for fpath in files:
        hasher.update(str(fpath.relative_to(root)).encode("utf-8"))
        hasher.update(fpath.read_bytes())
    return hasher.hexdigest()


def _read_stamp(dest):
    path = Path(dest) / STAMP
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return text if len(text) == 32 else ""


def _write_stamp(dest, digest):
    # The home is agent-writable: unlink first so a stamp the agent swapped
    # for a symlink is replaced, never written through on the host deploy.
    stamp = Path(dest) / STAMP
    stamp.unlink(missing_ok=True)
    stamp.write_text(digest + "\n", encoding="utf-8")


def _is_empty_dir(path):
    path = Path(path)
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    return False


def _install(src, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    incoming = dest.parent / (dest.name + ".incoming")
    if incoming.exists():
        shutil.rmtree(incoming)
    shutil.copytree(src, incoming)
    digest = dir_hash(incoming)
    _write_stamp(incoming, digest)
    if dest.exists():
        shutil.rmtree(dest)
    os.replace(incoming, dest)
    return digest


def reconcile_one(src, dest):
    """Return a short status verb for this skill directory."""
    src = Path(src)
    dest = Path(dest)
    seed = dir_hash(src)
    if _is_empty_dir(dest):
        _install(src, dest)
        return "seeded"
    current = dir_hash(dest)
    if current == seed:
        _write_stamp(dest, seed)
        return "already current"
    origin = _read_stamp(dest)
    if not origin:
        # Old hook never stamped. Those copies were ours. Re-seed once;
        # after this, the stamp protects agent edits.
        _install(src, dest)
        return "seeded"
    if current == origin:
        _install(src, dest)
        return "updated"
    return "keeping user-modified"


def iter_pt_skills(checkout):
    checkout = Path(checkout)
    found = []
    for path in sorted(checkout.iterdir()):
        if not path.is_dir() or not path.name.startswith("pt-"):
            continue
        skill = path / "SKILL.md"
        if not skill.is_file():
            raise SystemExit(f"the-plow-times: {path.name} has no SKILL.md -- broken checkout")
        found.append(path)
    if not found:
        raise SystemExit("the-plow-times: no pt-* skill dirs -- broken checkout")
    return found


def reconcile(checkout, home):
    lines = []
    skills_home = Path(home) / "skills"
    skills_home.mkdir(parents=True, exist_ok=True)
    for src in iter_pt_skills(checkout):
        dest = skills_home / src.name
        verb = reconcile_one(src, dest)
        lines.append(f"the-plow-times: {verb} {src.name}")
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) != 2:
        print("usage: reconcile_pt_skills.py <AGENT_HOME>", file=sys.stderr)
        return 1
    home = argv[1]
    print(reconcile(_checkout_root(), home))
    return 0


if __name__ == "__main__":
    sys.exit(main())
