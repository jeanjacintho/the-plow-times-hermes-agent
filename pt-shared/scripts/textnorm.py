#!/usr/bin/env python3
"""Text normalization shared by history and validation. Library only."""
from __future__ import annotations

import re
import unicodedata

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").translate(_QUOTES))
    s = s.encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _tokens(s):
    return {t for t in normalize(s).split() if len(t) >= 3}


def similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold
