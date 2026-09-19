#!/usr/bin/env python3
"""Stamp newspaper gates onto plow-seed/config.yaml.

plow-init recopies the seed over the home config every boot.
runtime/config.yaml copied into /var/lib/hermes is shadowed by the
agent-home volume, so display quiet-chat, context_file_max_chars, and
the Sonnet 5 default have to live on the seed or a recreate restores
the base (loud plow_chat, 20 000-char SOUL truncation, glm-5.2).
"""
from __future__ import annotations

import sys


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


def overlay_model(seed: dict, ours: dict) -> dict:
    """Fleet seed default is glm-5.2; stamp only the paper's model id."""
    model_id = ours["model"]["default"]
    seed["model"]["default"] = model_id
    seed["providers"]["plow"]["models"][model_id] = ours["providers"]["plow"]["models"][model_id]
    return seed


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        raise SystemExit("usage: merge_pt_seed_config.py <seed.yaml> <runtime.yaml>")
    seed_path, ours_path = argv
    import yaml

    with open(seed_path) as handle:
        seed = yaml.safe_load(handle) or {}
    with open(ours_path) as handle:
        ours = yaml.safe_load(handle) or {}
    overlay_display(seed, ours)
    overlay_model(seed, ours)
    seed["context_file_max_chars"] = ours["context_file_max_chars"]
    disp = seed.get("display") or {}
    pc = (disp.get("platforms") or {}).get("plow_chat") or {}
    default = (seed.get("model") or {}).get("default")
    if default != "anthropic/claude-sonnet-5":
        raise SystemExit("refusing: seed model.default is not anthropic/claude-sonnet-5")
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
