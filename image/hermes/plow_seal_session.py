"""Gateway-side consume of seal-session.json after a paper turn.

Pinned into run_turn._hmwa_post_turn_hooks so the reset happens after
NO_REPLY / the PDF POST, not mid-research (a /new during the paper aborts
it).
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_STAMP = "/var/lib/hermes/pt/run/seal-session.json"


def _seal_mod():
    try:
        import seal_chat_session
        return seal_chat_session
    except ImportError:
        path = Path("/var/lib/hermes/skills/pt-shared/scripts/seal_chat_session.py")
        if not path.is_file():
            return None
        import importlib.util

        spec = importlib.util.spec_from_file_location("seal_chat_session", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def edition_posted_this_turn(stamp=None):
    """True after post_to_chat.py POSTed the PDF (or text fallback).

    chat_status --soon also writes the stamp, but delivered is false until
    the file is in chat. Measured live: the model then typed a section
    recap; the owner already had the PDF.
    """
    mod = _seal_mod()
    if mod is None:
        return False
    path = Path(stamp) if stamp is not None else Path(DEFAULT_STAMP)
    data = mod.peek(path)
    return bool(isinstance(data, dict) and data.get("delivered") is True)


async def seal_one(gateway, session_key):
    if not session_key:
        return
    invalidate = getattr(gateway, "_invalidate_session_run_generation", None)
    if invalidate:
        invalidate(session_key, reason="edition_seal")
    release = getattr(gateway, "_release_running_agent_state", None)
    if release:
        release(session_key)
    evict = getattr(gateway, "_evict_cached_agent", None)
    if evict:
        evict(session_key)
    clear = getattr(gateway, "_clear_conversation_scope", None)
    if clear:
        clear(session_key, reason="edition_seal")
    store = getattr(gateway, "async_session_store", None)
    if store is None:
        return
    await store.reset_session(session_key)


async def maybe_seal_after_turn(gateway, stamp=None):
    mod = _seal_mod()
    if mod is None:
        return
    path = Path(stamp) if stamp is not None else Path(DEFAULT_STAMP)
    payload = mod.consume(path)
    if not payload:
        return
    store = getattr(gateway, "session_store", None)
    entries = store.list_sessions() if store is not None else []
    for key in sorted(mod.keys_to_seal(payload, entries)):
        await seal_one(gateway, key)
