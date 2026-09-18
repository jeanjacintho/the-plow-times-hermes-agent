import json

import pytest

from conftest import load_module

bc = load_module("build_context", "pt-priority/scripts/build_context.py")
hist = load_module("history", "pt-priority/scripts/history.py")

FILE_OK = {"status": "ok", "truncated": False,
           "sections": [{"id": "goals", "kind": "goals", "heading": "Goals", "text": "Raise"}]}
EVENTS_OK = {"date": "2026-09-16", "events": []}
DAY_OK = {"status": "ok", "free_blocks": [{"start": "09:00", "end": "11:00"}]}
CAL_OK = {"status": "ok", "events": [], "free_blocks": [{"start": "09:00", "end": "11:00"}]}


@pytest.fixture(autouse=True)
def pt_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    return tmp_path


def test_build_ok():
    c = bc.build("2026-09-16", "America/Sao_Paulo", FILE_OK, CAL_OK, [])
    assert c["today"] == "2026-09-16" and c["weekday"] == "Wednesday"
    assert c["tz"] == "America/Sao_Paulo"
    assert c["file"] == FILE_OK and c["calendar"] == CAL_OK
    assert c["history"] == [] and c["notes"] == []
    assert bc.has_input(c)


def test_notes_and_defaults():
    c = bc.build("2026-09-16", "UTC", None, None, [])
    assert c["file"]["status"] == "missing"
    assert c["calendar"]["status"] == "error"
    assert c["notes"] == ["file_missing", "calendar_unavailable"]
    assert not bc.has_input(c)
    c = bc.build("2026-09-16", "UTC", {"status": "empty", "truncated": False, "sections": []}, CAL_OK, [])
    assert c["notes"] == ["file_empty"] and bc.has_input(c)


def test_cli_reads_run_dir_and_history(pt_home, tmp_path, capsys):
    run = tmp_path / "run"
    (run / "desk-priority").mkdir(parents=True)
    (run / "desk-calendar").mkdir(parents=True)
    (run / "desk-priority" / "file.json").write_text(json.dumps(FILE_OK))
    (run / "desk-calendar" / "events.json").write_text(json.dumps(EVENTS_OK))
    (run / "desk-priority" / "day.json").write_text(json.dumps(DAY_OK))
    hist.record("2026-09-15", "Ship pricing page")
    bc.main(["--run-dir", str(run), "--tz", "UTC", "--now", "2026-09-16T12:00:00+00:00"])
    assert capsys.readouterr().out.strip() == "CONTEXT:ok NOTES:none"
    ctx = json.loads((run / "desk-priority" / "context.json").read_text())
    assert ctx["history"] == [{"date": "2026-09-15", "priority": "Ship pricing page", "status": "open"}]


def test_cli_calendar_unavailable_without_day_json(pt_home, tmp_path, capsys):
    run = tmp_path / "run"
    (run / "desk-priority").mkdir(parents=True)
    (run / "desk-calendar").mkdir(parents=True)
    (run / "desk-priority" / "file.json").write_text(json.dumps(FILE_OK))
    (run / "desk-calendar" / "events.json").write_text(json.dumps(EVENTS_OK))
    bc.main(["--run-dir", str(run), "--tz", "UTC", "--now", "2026-09-16T12:00:00+00:00"])
    assert capsys.readouterr().out.strip() == "CONTEXT:ok NOTES:calendar_unavailable"


def test_cli_nothing(pt_home, tmp_path, capsys):
    run = tmp_path / "run"
    run.mkdir()
    bc.main(["--run-dir", str(run), "--tz", "UTC", "--now", "2026-09-16T12:00:00+00:00"])
    assert capsys.readouterr().out.strip() == "CONTEXT:nothing"
    assert (run / "desk-priority" / "context.json").exists()
