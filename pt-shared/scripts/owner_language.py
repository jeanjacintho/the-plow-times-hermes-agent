"""owner_language.py -- the one place that decides the owner's language.

Not a flow script: a library the pt-* scripts import. `record_owner_language.py`
writes `owner.language`; this reads it, for the mechanical lines that are
repo-authored copy rather than model prose (the chat wait lines, the priority
gap card, the unavailable-paper notice).

Measured 2026-09-21: the same predicate existed three times -- in
chat_status.py, render_edition.py and print_edition.py -- and two of the three
recognized Portuguese as membership in {"pt", "pt-br"}. So `pt-PT` and `pt_AO`
owners got English wait lines and an English gap card while `pt-BR` owners got
Portuguese, from the same config value. Three copies of a policy is three
policies; this is one.
"""
from __future__ import annotations


def is_portuguese(language):
    """True for every Portuguese tag, not an allow-list of regions.

    Accepts the plain-English name `record_owner_language.py` stores
    ("Português"), the bare tag, and every region: pt-BR, pt-PT, pt-AO, and
    the underscore forms Hermes sometimes passes through.
    """
    tag = (language or "").lower().replace("_", "-")
    return "portug" in tag or tag == "pt" or tag.startswith("pt-")
