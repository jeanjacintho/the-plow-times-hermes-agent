#!/usr/bin/env python3
"""Deep-merge runtime/config.yaml onto plow-seed/config.yaml, ours winning.

The seed is the one config this agent's home is built from: cont-init copies
it into a home that has none, and plow-init re-stamps its display, model,
provider and terminal.cwd onto the home every boot. Merging every key keeps
the GPT-6 Astra pin, the quiet plow_chat block and the rest of runtime/config.yaml
(cron.wrap_response, agent.disabled_toolsets, context_file_max_chars, ...)
from falling back to the base's on either path. Mappings merge; any other
value in ours replaces the seed's.
"""
from __future__ import annotations

import sys


def deep_merge(seed, ours):
    merged = dict(seed)
    for key, value in ours.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def main(argv=None):
    import yaml

    seed_path, ours_path = sys.argv[1:] if argv is None else argv
    with open(seed_path) as handle:
        seed = yaml.safe_load(handle)
    with open(ours_path) as handle:
        ours = yaml.safe_load(handle)
    with open(seed_path, "w") as handle:
        yaml.safe_dump(deep_merge(seed, ours), handle, sort_keys=False)


if __name__ == "__main__":
    main()
