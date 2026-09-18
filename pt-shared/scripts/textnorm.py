#!/usr/bin/env python3
"""Text normalization shared by history and validation. Library only."""
from __future__ import annotations

import re
import unicodedata

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})

# A "do not do this" line is a paraphrase of the priority, not a copy of it, so the
# avoidance checks compare with a lower bar than the repeat-detection default.
AVOID_THRESHOLD = 0.45


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").translate(_QUOTES))
    s = s.encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _stem(token):
    """Crude, language-agnostic suffix trim so rep/reps and lead/leading match."""
    for suffix, keep in (("ing", 5), ("es", 5), ("s", 4)):
        if token.endswith(suffix) and len(token) >= keep:
            return token[: -len(suffix)]
    return token


def _tokens(s):
    return {_stem(t) for t in normalize(s).split() if len(t) >= 3}


def similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold
