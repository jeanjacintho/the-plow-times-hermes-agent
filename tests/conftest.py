"""Loaders for the pt- scripts under test.

The scripts are plain files beside the skills that run them (no package, no
install), so each suite loads them by path -- the same realpath resolution
the cross-skill imports use inside the container.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pt-shared" / "scripts"))


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
