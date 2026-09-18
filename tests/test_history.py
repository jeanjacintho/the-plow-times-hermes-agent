import json

import pytest

from conftest import load_module

hist = load_module("history", "pt-priority/scripts/history.py")


@pytest.fixture(autouse=True)
def pt_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    return tmp_path


def test_record_upserts_and_today():
    hist.record("2026-09-16", "A")
    hist.record("2026-09-16", "B")
    assert hist.today("2026-09-16") == {"date": "2026-09-16", "priority": "B", "status": "open"}
    assert len(hist.load()) == 1


def test_set_status():
    assert hist.set_status("2026-09-16", "done") is False
    hist.record("2026-09-16", "A")
    assert hist.set_status("2026-09-16", "done") is True
    assert hist.today("2026-09-16")["status"] == "done"


def test_recent_and_prune():
    hist.record("2026-08-01", "old")
    hist.record("2026-09-10", "x")
    hist.record("2026-09-15", "y")
    hist.record("2026-09-16", "today")
    assert [e["date"] for e in hist.recent("2026-09-16")] == ["2026-09-10", "2026-09-15"]
    assert "2026-08-01" not in [e["date"] for e in hist.load()]  # pruned (>30 days)


def test_streak_counts_consecutive_similar_days():
    for d in ("2026-09-13", "2026-09-14", "2026-09-15"):
        hist.record(d, "Close the seed extension with Fund X")
    assert hist.streak("2026-09-16", "close seed extension Fund X") == 3
    hist.record("2026-09-14", "Hire a designer")
    assert hist.streak("2026-09-16", "close seed extension Fund X") == 1


def test_streak_breaks_on_missing_day():
    hist.record("2026-09-13", "Same thing here")
    hist.record("2026-09-15", "Same thing here")
    assert hist.streak("2026-09-16", "Same thing here") == 1


@pytest.mark.parametrize("content", ["{broken", '{"a": 1}', '[{"date": "2026-09-15"}]'])
def test_unreadable_history_is_set_aside(pt_home, content, capsys):
    (pt_home / "history.json").write_text(content)
    hist.main(["today", "--date", "2026-09-16"])
    assert capsys.readouterr().out.strip() == "TODAY:none"
    assert (pt_home / "history.json.corrupt").read_text() == content
    hist.record("2026-09-16", "Fresh start")
    assert hist.today("2026-09-16")["priority"] == "Fresh start"


def test_cli(tmp_path, capsys):
    p = tmp_path / "priority.json"
    p.write_text(json.dumps({"date": "2026-09-16", "priority": "Ship pricing page"}))
    hist.main(["today", "--date", "2026-09-16"])
    hist.main(["record", "--date", "2026-09-16", "--priority-json", str(p)])
    hist.main(["today", "--date", "2026-09-16"])
    hist.main(["set", "--date", "2026-09-16", "--status", "skipped"])
    hist.main(["set", "--date", "2026-09-17", "--status", "done"])
    assert capsys.readouterr().out.splitlines() == [
        "TODAY:none", "RECORDED", "TODAY:open Ship pricing page",
        "STATUS:skipped", "STATUS:no-priority-today"]
