"""topics.py -- the single validated writer for the topic store."""
from __future__ import annotations

import json
import os
import pathlib
import re

import pytest

from conftest import load_module

topics = load_module("topics", "pt-intake/scripts/topics.py")


@pytest.fixture
def pt_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_HOME", str(tmp_path / "pt"))
    return tmp_path / "pt"


def read_store(pt_home):
    return json.loads((pt_home / "topics.json").read_text())["topics"]


class TestAdd:
    def test_add_creates_store_and_topic(self, pt_home, capsys):
        topics.main(["add", "--text", "new Anthropic API", "--kind",
                     "subscription", "--depth", "deep"])
        (added,) = read_store(pt_home)
        assert re.fullmatch(r"t_[0-9a-f]{4}", added["id"])
        assert added["text"] == "new Anthropic API"
        assert added["kind"] == "subscription"
        assert added["depth"] == "deep"
        assert added["status"] == "pending"
        assert added["last_edition_at"] is None

    def test_add_prints_envelope(self, pt_home, capsys):
        topics.main(["add", "--text", "x", "--kind", "one_off", "--depth", "quick"])
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["kind"] == "one_off"

    def test_blank_text_refused(self, pt_home):
        with pytest.raises(SystemExit):
            topics.main(["add", "--text", "   ", "--kind", "one_off",
                         "--depth", "quick"])

    def test_add_preserves_existing_topics(self, pt_home):
        topics.main(["add", "--text", "first", "--kind", "one_off", "--depth", "quick"])
        topics.main(["add", "--text", "second", "--kind", "subscription",
                     "--depth", "deep"])
        assert len(read_store(pt_home)) == 2

    def test_ids_are_unique(self, pt_home):
        seen = set()
        for i in range(40):
            topics.main(["add", "--text", f"t{i}", "--kind", "one_off",
                         "--depth", "quick"])
        for topic in read_store(pt_home):
            assert topic["id"] not in seen
            seen.add(topic["id"])


class TestTransitions:
    def add(self, kind, pt_home):
        topics.main(["add", "--text", "x", "--kind", kind,
                     "--depth", "quick" if kind == "one_off" else "deep"])
        return read_store(pt_home)[-1]["id"]

    def mark(self, tid, status, capsys=None):
        if capsys:
            capsys.readouterr()
        topics.main(["mark", tid, "--status", status])

    def test_subscription_full_cycle(self, pt_home, capsys):
        tid = self.add("subscription", pt_home)
        self.mark(tid, "running", capsys)
        self.mark(tid, "delivered", capsys)
        (topic,) = read_store(pt_home)
        assert topic["last_edition_at"] is not None
        self.mark(tid, "pending", capsys)
        (topic,) = read_store(pt_home)
        # The edition timestamp survives the cycle back to pending.
        assert topic["status"] == "pending"
        assert topic["last_edition_at"] is not None

    def test_oneoff_cannot_cycle_back(self, pt_home, capsys):
        tid = self.add("one_off", pt_home)
        self.mark(tid, "running", capsys)
        self.mark(tid, "delivered", capsys)
        with pytest.raises(SystemExit):
            self.mark(tid, "pending", capsys)

    def test_oneoff_running_to_pending_refused(self, pt_home, capsys):
        tid = self.add("one_off", pt_home)
        self.mark(tid, "running", capsys)
        with pytest.raises(SystemExit):
            self.mark(tid, "pending", capsys)

    def test_delivered_oneoff_is_terminal_for_cancel(self, pt_home, capsys):
        tid = self.add("one_off", pt_home)
        self.mark(tid, "running", capsys)
        self.mark(tid, "delivered", capsys)
        with pytest.raises(SystemExit):
            topics.main(["cancel", tid])

    def test_cancel_from_pending(self, pt_home, capsys):
        tid = self.add("subscription", pt_home)
        topics.main(["cancel", tid])
        (topic,) = read_store(pt_home)
        assert topic["status"] == "cancelled"


class TestResolve:
    def test_unique_prefix_matches(self, pt_home, capsys):
        topics.main(["add", "--text", "x", "--kind", "one_off", "--depth", "quick"])
        tid = read_store(pt_home)[0]["id"]
        capsys.readouterr()
        topics.main(["mark", tid[:3], "--status", "running"])
        assert read_store(pt_home)[0]["status"] == "running"

    def store_ids(self, pt_home, ids):
        (pt_home).mkdir(parents=True, exist_ok=True)
        (pt_home / "topics.json").write_text(json.dumps({
            "topics": [
                {"id": i, "text": "x", "kind": "subscription", "depth": "deep",
                 "status": "pending", "created_at": "now", "last_edition_at": None}
                for i in ids
            ]
        }))

    def test_ambiguous_prefix_refused(self, pt_home, monkeypatch):
        self.store_ids(pt_home, ["t_aaaa", "t_aaab"])
        with pytest.raises(SystemExit, match="matches 2 topics"):
            topics.main(["cancel", "t_aa"])

    def test_unknown_id_refused(self, pt_home):
        self.store_ids(pt_home, ["t_aaaa"])
        with pytest.raises(SystemExit, match="no topic matches"):
            topics.main(["cancel", "t_ffff"])


class TestBrokenStore:
    def test_garbage_refuses_to_read_as_empty(self, pt_home):
        pt_home.mkdir(parents=True)
        (pt_home / "topics.json").write_text("garbage")
        with pytest.raises(SystemExit, match="refusing"):
            topics.main(["list"])

    def test_wrong_shape_refuses(self, pt_home):
        pt_home.mkdir(parents=True)
        (pt_home / "topics.json").write_text(json.dumps({"topics": "nope"}))
        with pytest.raises(SystemExit, match="refusing"):
            topics.main(["list"])

    def test_idless_topic_refuses(self, pt_home):
        pt_home.mkdir(parents=True)
        (pt_home / "topics.json").write_text(json.dumps({"topics": [{"nope": 1}]}))
        with pytest.raises(SystemExit, match="refusing"):
            topics.main(["list"])

    def test_missing_store_is_a_fresh_instance(self, pt_home, capsys):
        topics.main(["list"])
        assert json.loads(capsys.readouterr().out) == {"topics": []}


class TestSections:
    def test_section_cycles_like_a_subscription(self, pt_home, capsys):
        topics.main(["add", "--text", "weather", "--kind", "section", "--depth", "quick"])
        tid = read_store(pt_home)[-1]["id"]
        topics.main(["mark", tid, "--status", "running"])
        topics.main(["mark", tid, "--status", "delivered"])
        topics.main(["mark", tid, "--status", "pending"])
        (topic,) = read_store(pt_home)
        assert topic["status"] == "pending"
        assert topic["last_edition_at"] is not None

    def test_section_has_no_run_on(self, pt_home, capsys):
        topics.main(["add", "--text", "weather", "--kind", "section", "--depth", "quick"])
        assert "run_on" not in read_store(pt_home)[-1]

    def test_deliver_at_stored_on_section(self, pt_home, capsys):
        topics.main(["add", "--text", "sports", "--kind", "section",
                     "--depth", "quick", "--deliver-at", "12:30"])
        topic = read_store(pt_home)[-1]
        assert topic["deliver_at"] == "12:30"
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["deliver_at"] == "12:30"

    def test_deliver_at_omitted_on_main_paper_section(self, pt_home):
        topics.main(["add", "--text", "dollar", "--kind", "section", "--depth", "quick"])
        assert "deliver_at" not in read_store(pt_home)[-1]

    def test_deliver_at_refused_on_non_section(self, pt_home):
        with pytest.raises(SystemExit, match="only meaningful for a section"):
            topics.main(["add", "--text", "x", "--kind", "subscription",
                         "--depth", "deep", "--deliver-at", "12:30"])

    @pytest.mark.parametrize("bad", ["12:3", "25:00", "12:60", "noon", "7:00"])
    def test_malformed_deliver_at_refused(self, pt_home, bad):
        with pytest.raises(SystemExit, match="strict HH:MM"):
            topics.main(["add", "--text", "sports", "--kind", "section",
                         "--depth", "quick", "--deliver-at", bad])

    def test_run_on_refused_on_non_assignment(self, pt_home):
        with pytest.raises(SystemExit, match="only meaningful for an assignment"):
            topics.main(["add", "--text", "clima", "--kind", "section",
                         "--depth", "quick", "--run-on", "2026-09-11"])


class TestAssignments:
    def add(self, pt_home, run_on="2026-09-11"):
        topics.main(["add", "--text", "iPhone 15 price", "--kind",
                     "assignment", "--depth", "quick", "--run-on", run_on])
        return read_store(pt_home)[-1]

    def test_run_on_required(self, pt_home):
        with pytest.raises(SystemExit, match="required for an assignment"):
            topics.main(["add", "--text", "x", "--kind", "assignment",
                         "--depth", "quick"])

    @pytest.mark.parametrize("bad", ["2026-9-1", "11/09/2026", "2026-13-01",
                                     "2026-02-30", "today"])
    def test_malformed_run_on_refused(self, pt_home, bad):
        with pytest.raises(SystemExit):
            topics.main(["add", "--text", "x", "--kind", "assignment",
                         "--depth", "quick", "--run-on", bad])

    def test_run_on_stored(self, pt_home):
        topic = self.add(pt_home)
        assert topic["run_on"] == "2026-09-11"
        assert topic["status"] == "pending"

    def test_assignment_delivered_is_terminal(self, pt_home, capsys):
        topic = self.add(pt_home)
        tid = topic["id"]
        topics.main(["mark", tid, "--status", "running"])
        topics.main(["mark", tid, "--status", "delivered"])
        with pytest.raises(SystemExit, match="cannot go"):
            topics.main(["mark", tid, "--status", "pending"])

    def test_delivered_assignment_cannot_be_cancelled(self, pt_home, capsys):
        topic = self.add(pt_home)
        tid = topic["id"]
        topics.main(["mark", tid, "--status", "running"])
        topics.main(["mark", tid, "--status", "delivered"])
        with pytest.raises(SystemExit, match="nothing to cancel"):
            topics.main(["cancel", tid])

    def test_pending_assignment_is_cancellable(self, pt_home, capsys):
        topic = self.add(pt_home)
        topics.main(["cancel", topic["id"]])
        (stored,) = read_store(pt_home)
        assert stored["status"] == "cancelled"


class TestSectionsDoNotDuplicate:
    """A `section` is evergreen, so adding one twice is never a second beat.

    Measured live 2026-09-16: an owner re-ran setup a handful of times and
    topics.json ended up with 48 sections covering five actual interests --
    technology 10x, AI 9x, Formula 1 9x, NFL 8x, Lakers 5x plus spelling
    variants. Every daily run researches every pending section, so the
    duplicates are a redundant newspaper paid for in tokens.
    """

    def add(self, tmp_path, text, kind="section", depth="quick"):
        import argparse

        return topics.cmd_add(argparse.Namespace(
            text=text, kind=kind, depth=depth, run_on=None,
            deliver_at=None, scheduled_for=None,
        ))

    def test_adding_the_same_section_twice_keeps_one(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(topics, "TOPICS_FILE", str(tmp_path / "topics.json"))
        self.add(tmp_path, "technology")
        capsys.readouterr()
        rc = self.add(tmp_path, "technology")
        assert rc == 0
        out = capsys.readouterr().out
        assert "duplicate" in out or "existing" in out
        kept = [t for t in topics.load_topics() if t["kind"] == "section"]
        assert len(kept) == 1

    def test_case_and_spacing_do_not_make_a_new_section(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(topics, "TOPICS_FILE", str(tmp_path / "topics.json"))
        self.add(tmp_path, "Formula 1")
        self.add(tmp_path, "  formula 1  ")
        capsys.readouterr()
        kept = [t for t in topics.load_topics() if t["kind"] == "section"]
        assert len(kept) == 1

    def test_a_genuinely_different_section_is_still_added(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(topics, "TOPICS_FILE", str(tmp_path / "topics.json"))
        self.add(tmp_path, "technology")
        self.add(tmp_path, "Formula 1")
        capsys.readouterr()
        kept = [t for t in topics.load_topics() if t["kind"] == "section"]
        assert len(kept) == 2

    def test_one_offs_may_repeat(self, tmp_path, monkeypatch, capsys):
        # "research X again" is a real second request; only evergreen
        # sections collapse.
        monkeypatch.setattr(topics, "TOPICS_FILE", str(tmp_path / "topics.json"))
        self.add(tmp_path, "a copy of my paper", kind="one_off")
        self.add(tmp_path, "a copy of my paper", kind="one_off")
        capsys.readouterr()
        kept = [t for t in topics.load_topics() if t["kind"] == "one_off"]
        assert len(kept) == 2


class TestReopenSections:
    """Measured live 2026-09-18: a second on-demand paper shipped desks
    only. Sections were stuck at delivered (the model marked delivered
    and never pending). Research only runs pending sections, so news
    vanished until something reopened them.
    """

    def test_delivered_and_running_sections_become_pending(self, pt_home, capsys):
        topics.main(["add", "--text", "AI", "--kind", "section", "--depth", "quick"])
        topics.main(["add", "--text", "F1", "--kind", "section", "--depth", "quick"])
        topics.main(["add", "--text", "once", "--kind", "one_off", "--depth", "quick"])
        ai, f1, once = (t["id"] for t in read_store(pt_home))
        topics.main(["mark", ai, "--status", "running"])
        topics.main(["mark", ai, "--status", "delivered"])
        topics.main(["mark", f1, "--status", "running"])
        topics.main(["mark", once, "--status", "running"])
        topics.main(["mark", once, "--status", "delivered"])
        capsys.readouterr()
        topics.main(["reopen-sections"])
        out = json.loads(capsys.readouterr().out)
        by_id = {t["id"]: t for t in read_store(pt_home)}
        assert by_id[ai]["status"] == "pending"
        assert by_id[f1]["status"] == "pending"
        assert by_id[once]["status"] == "delivered"
        assert set(out["reopened"]) == {ai, f1}

    def test_pending_and_cancelled_are_untouched(self, pt_home, capsys):
        topics.main(["add", "--text", "keep", "--kind", "section", "--depth", "quick"])
        topics.main(["add", "--text", "stop", "--kind", "section", "--depth", "quick"])
        stop = read_store(pt_home)[-1]["id"]
        topics.main(["cancel", stop])
        capsys.readouterr()
        topics.main(["reopen-sections"])
        by_id = {t["id"]: t for t in read_store(pt_home)}
        assert by_id[read_store(pt_home)[0]["id"]]["status"] == "pending"
        assert by_id[stop]["status"] == "cancelled"


class TestReopenStampsEdition:
    def add_running(self, kind, pt_home):
        topics.main(["add", "--text", "x", "--kind", kind, "--depth", "deep"])
        tid = read_store(pt_home)[-1]["id"]
        topics.main(["mark", tid, "--status", "running"])
        return tid

    @pytest.mark.parametrize("kind", ["section", "subscription"])
    def test_evergreen_delivery_stamps_last_edition(self, kind, pt_home, capsys):
        tid = self.add_running(kind, pt_home)
        assert topics.reopen_evergreen(delivered=[tid]) == [tid]
        (topic,) = read_store(pt_home)
        assert topic["status"] == "pending"
        assert topic["last_edition_at"] is not None

    def test_startup_reopen_of_a_dead_run_does_not_stamp(self, pt_home, capsys):
        self.add_running("section", pt_home)
        topics.reopen_evergreen()
        (topic,) = read_store(pt_home)
        assert topic["status"] == "pending"
        assert topic["last_edition_at"] is None

    def test_already_delivered_keeps_its_stamp(self, pt_home, capsys):
        tid = self.add_running("section", pt_home)
        topics.main(["mark", tid, "--status", "delivered", "--at", "2026-01-01T00:00:00Z"])
        topics.reopen_evergreen()
        assert read_store(pt_home)[0]["last_edition_at"] == "2026-01-01T00:00:00Z"


class TestConcurrentWriters:
    def test_parallel_adds_all_land(self, pt_home):
        # Each add is its own process, as two cron-fired papers would be. Without
        # the store lock they load the same snapshot and lose each other's topic.
        import subprocess, sys
        script = str(pathlib.Path(topics.__file__))
        env = {**os.environ, "PT_HOME": str(pt_home)}
        procs = [subprocess.Popen([sys.executable, script, "add", "--text", f"t{i}",
                                   "--kind", "section", "--depth", "quick"],
                                  env=env, stdout=subprocess.DEVNULL)
                 for i in range(8)]
        assert all(p.wait() == 0 for p in procs)
        assert len(read_store(pt_home)) == 8
