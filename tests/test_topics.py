"""topics.py -- the single validated writer for the topic store."""
from __future__ import annotations

import json
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
