"""chat_status.py -- at most two live pings, never a decision dump."""
from __future__ import annotations

import json

import pytest

from conftest import load_module

status = load_module("chat_status", "pt-shared/scripts/chat_status.py")


class TestCopy:
    def test_portuguese_soon_and_wait(self):
        soon = status.status_text("soon", "Portuguese")
        wait = status.status_text("wait", "pt-BR")
        assert soon.startswith("⏳ ")
        assert wait.startswith("⏰ ")
        assert "minutos" in soon.lower() or "pouco" in soon.lower()
        assert "quase" in wait.lower() or "pronto" in wait.lower()
        assert "`" not in soon and "`" not in wait

    def test_english_when_language_is_not_portuguese(self):
        text = status.status_text("soon", "English")
        assert text.startswith("⏳ ")
        assert "few minutes" in text.lower() or "few" in text.lower()
        assert "jornal" not in text.lower()
        assert status.status_text("wait", "English").startswith("⏰ ")

    def test_setup_busy_is_a_hang_on_not_a_play_by_play(self):
        start = status.status_text("busy", "Portuguese")
        still = status.status_text("busy-still", "pt-BR")
        assert start.startswith("⏳ ")
        assert still.startswith("⏳ ")
        assert start != still
        for line in (start, still):
            assert "`" not in line
            assert "latch" not in line.lower()
            assert "desk" not in line.lower()
            assert "arquivo" not in line.lower()
            assert "file" not in line.lower()
        en = status.status_text("busy", "English")
        assert en.startswith("⏳ ")
        assert "jornal" not in en.lower()

    def test_unknown_kind_fails_loudly(self):
        with pytest.raises(KeyError):
            status.status_text("not-a-kind", "English")


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


class TestBusyGate:
    @pytest.mark.parametrize(
        "prep,now,expected",
        [
            (None, 1000.0, "send-start"),
            ("start", 1008.0, "too-early"),
            ("start", 1000.0 + status.BUSY_REPEAT_SECONDS + 1, "send-still"),
            (
                "start-still",
                1000.0 + status.BUSY_REPEAT_SECONDS + 6,
                "already",
            ),
            (
                "start-still",
                1000.0 + status.BUSY_NEW_WAVE_SECONDS + 1,
                "send-start",
            ),
        ],
    )
    def test_busy_wave(self, tmp_path, prep, now, expected):
        stamp = tmp_path / "setup-busy.json"
        if prep in ("start", "start-still"):
            status.record_busy_start(stamp, now=1000.0)
        if prep == "start-still":
            status.record_busy_still(stamp)
        assert status.busy_action(stamp, now=now) == expected


class TestLanguageFromConfig:
    def test_reads_owner_language(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"owner": {"language": "Portuguese"}}), encoding="utf-8"
        )
        assert status.owner_language(cfg) == "Portuguese"

    def test_falls_back_to_the_setup_draft_during_the_interview(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{}", encoding="utf-8")
        (tmp_path / ".setup-draft.json").write_text(
            json.dumps({"owner": {"language": "Portuguese"}}), encoding="utf-8"
        )
        assert status.owner_language(cfg) == "Portuguese"
