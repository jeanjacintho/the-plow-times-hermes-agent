#!/usr/bin/env python3
"""Stamp newspaper gates onto plow-seed/config.yaml.

plow-init writes seed['display'] onto the home config every boot, and
runtime/config.yaml copied into /var/lib/hermes is shadowed by the
agent-home volume, so quiet chat has to live on the seed. Any other
seed key reaches only a new home, so --home carries
context_file_max_chars into an existing one at boot (03-pt-context-cap).
"""
from __future__ import annotations

import os
import re
import sys

CAP = re.compile(r"^context_file_max_chars:.*$", re.M)


def _progress_token(value):
    """YAML 1.1 loads a bare `off` as False; Hermes wants the string `off`."""
    if value is False:
        return "off"
    if isinstance(value, str) and value.strip().lower() in {"off", "false", "no", "0"}:
        return "off"
    return value


def overlay_display(seed: dict, ours: dict) -> dict:
    seed_disp = dict(seed.get("display") or {})
    ours_disp = dict(ours.get("display") or {})
    seed_plats = dict(seed_disp.get("platforms") or {})
    ours_plats = dict(ours_disp.get("platforms") or {})
    seed_pc = dict(seed_plats.get("plow_chat") or {})
    ours_pc = dict(ours_plats.get("plow_chat") or {})
    merged_pc = {**seed_pc, **ours_pc}
    merged = {**seed_disp, **ours_disp}
    for key in ("tool_progress", "live_status"):
        if key in merged:
            merged[key] = _progress_token(merged[key])
        if key in merged_pc:
            merged_pc[key] = _progress_token(merged_pc[key])
    merged["platforms"] = {**seed_plats, **ours_plats, "plow_chat": merged_pc}
    seed["display"] = merged
    return seed


def carry_cap(home_path, seed_path):
    """Set the home's top-level cap line to the seed's, keeping every other byte."""
    with open(seed_path) as handle:
        cap = CAP.search(handle.read())
    if cap is None:
        raise SystemExit(f"refusing: {seed_path} has no context_file_max_chars")
    with open(home_path) as handle:
        home = handle.read()
    new, found = CAP.subn(lambda _: cap.group(0), home)
    new = new if found else home.rstrip("\n") + "\n" + cap.group(0) + "\n"
    if new != home:  # a sibling, then a rename, as plow-init writes it
        with open(home_path + ".tmp", "w") as handle:
            os.fchmod(handle.fileno(), 0o640)
            handle.write(new)
        os.replace(home_path + ".tmp", home_path)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 3 and argv[0] == "--home":
        return carry_cap(argv[1], argv[2])
    if len(argv) != 2:
        raise SystemExit("usage: merge_pt_seed_config.py <seed.yaml> <runtime.yaml> | --home <home.yaml> <seed.yaml>")
    seed_path, ours_path = argv
    import yaml

    with open(seed_path) as handle:
        seed = yaml.safe_load(handle) or {}
    with open(ours_path) as handle:
        ours = yaml.safe_load(handle) or {}
    overlay_display(seed, ours)
    seed["context_file_max_chars"] = ours["context_file_max_chars"]
    disp = seed.get("display") or {}
    pc = (disp.get("platforms") or {}).get("plow_chat") or {}
    if disp.get("interim_assistant_messages") is not False:
        raise SystemExit("refusing: seed display.interim_assistant_messages is not false")
    if _progress_token(disp.get("tool_progress")) != "off":
        raise SystemExit("refusing: seed display.tool_progress is not off")
    if disp.get("long_running_notifications") is not False:
        raise SystemExit("refusing: seed display.long_running_notifications is not false")
    if pc.get("interim_assistant_messages") is not False:
        raise SystemExit("refusing: seed plow_chat.interim_assistant_messages is not false")
    if _progress_token(pc.get("tool_progress")) != "off":
        raise SystemExit("refusing: seed plow_chat.tool_progress is not off")
    if pc.get("long_running_notifications") is not False:
        raise SystemExit("refusing: seed plow_chat.long_running_notifications is not false")
    with open(seed_path, "w") as handle:
        yaml.safe_dump(seed, handle, sort_keys=False)


if __name__ == "__main__":
    main()
