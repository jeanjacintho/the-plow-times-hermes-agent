#!/usr/bin/env python3
"""Pin maybe_seal_after_turn into gateway run_turn post-turn hooks."""
from __future__ import annotations

import sys
from pathlib import Path

OLD_TURN = '''    async def _hmwa_post_turn_hooks(self, hook_ctx, agent_result, response):
        """agent:end hook, process-watcher scheduling, and watch-notification drain."""
        await self.hooks.emit("agent:end", {
'''

NEW_TURN = '''    async def _hmwa_post_turn_hooks(self, hook_ctx, agent_result, response):
        """agent:end hook, process-watcher scheduling, and watch-notification drain."""
        from plow_seal_session import maybe_seal_after_turn
        await maybe_seal_after_turn(self)
        await self.hooks.emit("agent:end", {
'''

OLD_SILENCE = '''def is_intentional_silence_response(response: Any) -> bool:
    """True only when ``response`` is exactly a silence marker.

    Prose that merely mentions ``NO_REPLY`` must be delivered normally. A blank
    response is not silence either — that is the empty-response failure path.
    """
    return any(c in LIVE_GATEWAY_SILENT_MARKERS for c in _canonical_silence_candidates(response))
'''

NEW_SILENCE = '''def is_intentional_silence_response(response: Any) -> bool:
    """True only when ``response`` is exactly a silence marker.

    Prose that merely mentions ``NO_REPLY`` must be delivered normally. A blank
    response is not silence either — that is the empty-response failure path.
    """
    from plow_seal_session import edition_posted_this_turn
    if edition_posted_this_turn():
        return True
    return any(c in LIVE_GATEWAY_SILENT_MARKERS for c in _canonical_silence_candidates(response))
'''


def apply(source: str) -> str:
    if OLD_TURN in source:
        if source.count(OLD_TURN) != 1:
            raise SystemExit(
                "seal-session pin: run_turn.py did not match "
                f"_hmwa_post_turn_hooks marker (count {source.count(OLD_TURN)}, want 1)"
            )
        return source.replace(OLD_TURN, NEW_TURN, 1)
    if OLD_SILENCE in source:
        if source.count(OLD_SILENCE) != 1:
            raise SystemExit(
                "seal-session pin: response_filters.py did not match "
                f"is_intentional_silence_response marker (count {source.count(OLD_SILENCE)}, want 1)"
            )
        return source.replace(OLD_SILENCE, NEW_SILENCE, 1)
    raise SystemExit(
        "seal-session pin: file did not match run_turn or response_filters markers"
    )


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit("usage: patch_seal_session.py <run_turn.py|response_filters.py>")
    path = Path(argv[0])
    path.write_text(apply(path.read_text()), encoding="utf-8")


if __name__ == "__main__":
    main()
