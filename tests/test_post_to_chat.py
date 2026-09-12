"""post_to_chat.py -- PDF-only payload vs text fallback."""
from __future__ import annotations

import sys

import pytest

from conftest import ROOT, load_module

sys.path.insert(0, str(ROOT / "pt-shared" / "scripts"))
post = load_module("post_to_chat", "pt-shared/scripts/post_to_chat.py")


class TestComposePayload:
    def test_pdf_is_attachment_with_empty_body(self):
        payload = post.compose_payload("ignored transcript", "att_1")
        assert payload == {"body": "", "attachment_uids": ["att_1"]}

    def test_text_only_when_no_pdf(self):
        payload = post.compose_payload("THE PLOW TIMES")
        assert payload == {"body": "THE PLOW TIMES"}

    def test_text_only_refuses_blank_stdin(self):
        with pytest.raises(SystemExit, match="no edition text"):
            post.compose_payload("")
