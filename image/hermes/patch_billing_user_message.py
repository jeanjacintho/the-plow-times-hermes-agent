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
    *,
    capability: str,
    provider: str,
    base_url: str,
    model: str,
    unverified: bool = False,
) -> str:
    if _is_nous_inference_route(provider, base_url):
""",
        """def _billing_or_entitlement_message(
    *,
    capability: str,
    provider: str,
    base_url: str,
    model: str,
    unverified: bool = False,
) -> str:
    from agent.billing_user_message import BILLING_USER_MESSAGE
    return BILLING_USER_MESSAGE
    if _is_nous_inference_route(provider, base_url):
""",
    ),
    (
        """def _billing_block_dict(
    provider, base_url, model, message="", *, unverified: bool = False
) -> Optional[dict]:
    \"\"\"Best-effort structured billing descriptor (None if billing_links is unavailable).\"\"\"
    try:
""",
        """def _billing_block_dict(
    provider, base_url, model, message="", *, unverified: bool = False
) -> Optional[dict]:
    \"\"\"Pinned off: a billing_block lets the gateway attach a second CTA.\"\"\"
    return None
    try:
""",
    ),
    (
        """    if unverified:
        return (
            "Provider reported usage/credit exhaustion (unverified — the same "
            f"error can be a content-filter rejection, not billing): {summary}"
        )
    return f"Billing or credits exhausted: {summary}"
""",
        """    from agent.billing_user_message import BILLING_USER_MESSAGE
    return BILLING_USER_MESSAGE
""",
    ),
    (
        """    final = _billing_terminal_label(summary, unverified)
    if guidance:
        final += f"\\n\\n{guidance}"
""",
        """    from agent.billing_user_message import BILLING_USER_MESSAGE
    final = BILLING_USER_MESSAGE
""",
    ),
    (
        """        "completed": False,
        "failed": True,
        "error": summary,
        "failure_reason": classified.reason.value,
""",
        """        "completed": False,
        "failed": True,
        "error": final,
        "failure_reason": classified.reason.value,
""",
    ),
    (
        """                            agent._emit_status(
                                "❌ Provider reported usage/credit exhaustion "
                                f"(unverified — may be a content-filter rejection) — {_final_summary}"
                            )
""",
        """                            from agent.billing_user_message import BILLING_USER_MESSAGE
                            agent._emit_status(BILLING_USER_MESSAGE)
""",
    ),
    (
        """                            agent._emit_status(f"❌ Billing or credits exhausted — {_final_summary}")
""",
        """                            from agent.billing_user_message import BILLING_USER_MESSAGE
                            agent._emit_status(BILLING_USER_MESSAGE)
""",
    ),
    (
        """                        _final_response = _billing_terminal_label(
                            _final_summary, _billing_unverified
                        )
                        if _billing_guidance:
                            _final_response += f"\\n\\n{_billing_guidance}"
""",
        """                        from agent.billing_user_message import BILLING_USER_MESSAGE
                        _final_response = BILLING_USER_MESSAGE
                        _final_summary = BILLING_USER_MESSAGE
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
