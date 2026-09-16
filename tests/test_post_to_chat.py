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


class TestTextFileFlag:
    """`--text-file` exists so the text leg needs no shell redirect.

    Measured live: told to "pass the chat text on stdin" with no command
    shown, a run built `/bin/sh -c '... post_to_chat.py < .../edition.chat.txt'`
    -- a shell operator, which is exactly what SOUL.md's gate flags. The owner
    got an /approve prompt instead of their newspaper.
    """

    def test_reads_the_edition_text_from_a_file(self, tmp_path):
        f = tmp_path / "edition.chat.txt"
        f.write_text("THE PLOW TIMES\nfront page\n", encoding="utf-8")
        assert post.read_text_file(str(f)) == "THE PLOW TIMES\nfront page"

    def test_missing_file_is_refused_by_name(self, tmp_path):
        with pytest.raises(SystemExit, match="text-file"):
            post.read_text_file(str(tmp_path / "nope.txt"))

    def test_blank_file_is_refused(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("   \n", encoding="utf-8")
        with pytest.raises(SystemExit, match="empty"):
            post.read_text_file(str(f))
