import json
from datetime import datetime
from zoneinfo import ZoneInfo

from conftest import ROOT, load_module

day = load_module("day_shape", "pt-priority/scripts/day_shape.py")
FIX = ROOT / "tests" / "fixtures" / "priority"
TZ = "America/Sao_Paulo"
MORNING = datetime(2026, 9, 16, 7, 30, tzinfo=ZoneInfo(TZ))


def payload(name):
    return json.loads((FIX / name).read_text())


def test_free_blocks_merge_overlaps_and_skip_short():
    blocks = day.free_blocks(payload("events-day.json"), MORNING)
    # 13:30-14:00 is only 30 min -> dropped; 12:00-13:30 overlap merged
    assert blocks == [
        {"start": "08:00", "end": "09:00"},
        {"start": "09:30", "end": "12:00"},
        {"start": "15:00", "end": "19:00"},
    ]


def test_all_day_does_not_block():
    p = {
        "events": [
            {"start": None, "end": None, "title": "Holiday", "all_day": True, "tomorrow": False},
        ]
    }
    assert day.validate_events(p) == []
    assert day.free_blocks(p, MORNING) == [{"start": "08:00", "end": "19:00"}]


def test_now_after_day_start_rounds_up():
    now = datetime(2026, 9, 16, 15, 7, tzinfo=ZoneInfo(TZ))
    assert day.free_blocks(payload("events-day.json"), now) == [{"start": "15:15", "end": "19:00"}]


def test_packed_day_has_no_blocks():
    assert day.free_blocks(payload("events-packed.json"), MORNING) == []


def test_event_clamped_from_yesterday_still_blocks_today():
    p = {"events": [
        {"start": "00:00", "end": "11:00", "title": "Offsite", "all_day": False, "tomorrow": False},
    ]}
    assert day.free_blocks(p, MORNING) == [{"start": "11:00", "end": "19:00"}]


def test_event_running_past_midnight_blocks_rest_of_day():
    p = {"events": [
        {"start": "17:00", "end": "23:59", "title": "Launch night", "all_day": False, "tomorrow": False},
    ]}
    assert day.free_blocks(p, MORNING) == [{"start": "08:00", "end": "17:00"}]


def test_validate_events_not_an_object():
    assert day.validate_events({"events": ["nope"]}) == ["events[0] is not an object"]


def test_validate_events_blank_title():
    p = {"events": [{"start": "09:00", "end": "10:00", "title": "  ", "all_day": False}]}
    assert day.validate_events(p) == ["events[0].title is blank"]


def test_validate_events_all_day_not_boolean():
    p = {"events": [{"start": None, "end": None, "title": "Holiday", "all_day": "yes"}]}
    assert day.validate_events(p) == ["events[0].all_day is not a boolean"]


def test_validate_events_times_not_hhmm():
    p = {"events": [{"start": "9am", "end": "10:00", "title": "Sync", "all_day": False}]}
    assert day.validate_events(p) == ["events[0].start is not HH:MM"]


def test_validate_events_ends_before_it_starts():
    p = {"events": [{"start": "11:00", "end": "10:00", "title": "Sync", "all_day": False}]}
    assert day.validate_events(p) == ["events[0] ends before it starts"]


def test_validate_events_missing_list():
    assert day.validate_events({}) == ["events.json has no events list"]


def test_cli_ok_and_invalid(tmp_path, capsys):
    out = tmp_path / "day.json"
    day.main(["free-blocks", str(FIX / "events-day.json"), str(out),
              "--tz", TZ, "--now", "2026-09-16T07:30:00-03:00"])
    assert capsys.readouterr().out.strip() == "DAY:ok BLOCKS:3"
    assert json.loads(out.read_text())["status"] == "ok"
    day.main(["free-blocks", str(tmp_path / "nope.json"), str(out), "--tz", TZ])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "DAY:invalid"
    assert json.loads(out.read_text()) == {"status": "error", "free_blocks": []}
