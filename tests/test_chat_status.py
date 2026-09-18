"""chat_status.py -- at most two live pings, never a decision dump."""
from __future__ import annotations

import json

import pytest

from conftest import load_module

status = load_module("chat_status", "pt-shared/scripts/chat_status.py")


class TestCopy:
    def test_portuguese_soon_and_wait(self):
        assert "minutos" in status.status_text("soon", "Portuguese").lower()
        wait = status.status_text("wait", "pt-BR")
        assert "minutos" in wait.lower()
        assert "quase" in wait.lower() or "pronto" in wait.lower()

    def test_english_when_language_is_not_portuguese(self):
        text = status.status_text("soon", "English")
        assert "few minutes" in text.lower()
        assert "jornal" not in text.lower()


class TestSoonGate:
    def test_soon_posts_when_there_is_no_stamp(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        assert status.soon_action(stamp, now=1000.0) == "send"

    def test_soon_is_idempotent_while_the_same_paper_is_running(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        status.record_soon(stamp, now=1000.0)
        assert status.soon_action(stamp, now=1000.0 + 30) == "already"

    def test_soon_posts_again_after_the_previous_paper_finished(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        status.record_soon(stamp, now=1000.0)
        status.record_wait_sent(stamp)
        assert status.soon_action(stamp, now=2000.0) == "send"


class TestWaitGate:
    def test_wait_without_soon_is_a_noop(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        assert status.wait_action(stamp, now=1000) == "no-soon"

    def test_wait_too_early_is_a_noop(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        status.record_soon(stamp, now=1000.0)
        assert status.wait_action(stamp, now=1000.0 + 60) == "too-early"

    def test_wait_fires_once_after_the_budget(self, tmp_path):
        stamp = tmp_path / "chat-status.json"
        status.record_soon(stamp, now=1000.0)
        later = 1000.0 + status.WAIT_SECONDS + 1
        assert status.wait_action(stamp, now=later) == "send"
        status.record_wait_sent(stamp)
        assert status.wait_action(stamp, now=later + 600) == "already"


class TestLanguageFromConfig:
    def test_reads_owner_language(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"owner": {"language": "Portuguese"}}), encoding="utf-8"
        )
        assert status.owner_language(cfg) == "Portuguese"
