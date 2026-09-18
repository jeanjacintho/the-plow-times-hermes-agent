#!/usr/bin/env python3
"""Rewrite Hermes billing surfaces onto BILLING_USER_MESSAGE.

Markers are the base image's own source. If a digest bump moves them, this
exits non-zero so the image does not ship the vendor 402 prose by accident.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        """def _billing_or_entitlement_message(
    *, capability: str, provider: str, base_url: str, model: str, unverified: bool = False
) -> str:
    if _is_nous_inference_route(provider, base_url):
""",
        """def _billing_or_entitlement_message(
    *, capability: str, provider: str, base_url: str, model: str, unverified: bool = False
) -> str:
    from agent.billing_user_message import BILLING_USER_MESSAGE
    return BILLING_USER_MESSAGE
    if _is_nous_inference_route(provider, base_url):
""",
    ),
    (
        """def _billing_block_dict(provider, base_url, model, message="", *, unverified: bool = False) -> Optional[dict]:
    \"\"\"Best-effort structured billing descriptor (None if billing_links is unavailable).\"\"\"
    try:
""",
        """def _billing_block_dict(provider, base_url, model, message="", *, unverified: bool = False) -> Optional[dict]:
    \"\"\"Pinned off: a billing_block lets the gateway attach a second CTA.\"\"\"
    return None
    try:
""",
    ),
    (
        """def _billing_terminal_label(summary: str, unverified: bool) -> str:
    \"\"\"Terminal-failure prefix for a billing-classified error; ``unverified`` (#82154) must
    not assert exhaustion as fact.\"\"\"
    if unverified:
""",
        """def _billing_terminal_label(summary: str, unverified: bool) -> str:
    \"\"\"Terminal-failure prefix for a billing-classified error; ``unverified`` (#82154) must
    not assert exhaustion as fact.\"\"\"
    from agent.billing_user_message import BILLING_USER_MESSAGE
    return BILLING_USER_MESSAGE
    if unverified:
""",
    ),
    (
        """    final = _billing_terminal_label(summary, unverified) + (f"\\n\\n{guidance}" if guidance else "")
    return {
        "final_response": final, "messages": messages, "api_calls": api_call_count,
        "completed": False, "failed": True, "error": summary,
""",
        """    from agent.billing_user_message import BILLING_USER_MESSAGE
    final = BILLING_USER_MESSAGE
    return {
        "final_response": final, "messages": messages, "api_calls": api_call_count,
        "completed": False, "failed": True, "error": final,
""",
    ),
)


def apply(source: str) -> str:
    text = source
    missing: list[str] = []
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            missing.append(f"marker count {count} (want 1): {old[:80]!r}")
            continue
        text = text.replace(old, new, 1)
    if missing:
        raise SystemExit(
            "billing-message pin: conversation_loop.py did not match "
            "the expected Hermes source:\n  " + "\n  ".join(missing)
        )
    return text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: patch_billing_user_message.py <conversation_loop.py>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    path.write_text(apply(path.read_text()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
