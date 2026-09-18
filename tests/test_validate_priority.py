import copy
import json

import pytest

from conftest import load_module

vp = load_module("validate_priority", "pt-priority/scripts/validate_priority.py")

CONTEXT = {
    "today": "2026-09-16", "weekday": "Wednesday", "tz": "UTC",
    "file": {"status": "ok", "truncated": False, "sections": [
        {"id": "goals", "kind": "goals", "heading": "Goals", "text": "Raise $1.5M by Sep 30."},
        {"id": "not-now", "kind": "not_now", "heading": "Not now", "text": "- Website rebrand project\n- Conference talks"},
    ]},
    "calendar": {"status": "ok",
                 "events": [{"id": "evt_1", "start": "14:00", "end": "15:00", "title": "Partner call",
                             "all_day": False, "tomorrow": False}],
                 "free_blocks": [{"start": "09:00", "end": "11:30"}]},
    "history": [], "notes": ["file_empty"],
}
GOOD = {
    "date": "2026-09-16",
    "priority": "Close the seed extension with Fund X",
    "why": [
        {"text": "Q3 goal", "source": "file:goals", "quote": "raise $1.5M by  sep 30"},
        {"text": "Partner call today", "source": "calendar:evt_1"},
    ],
    "first_step": "Send the updated deck before the 2pm call",
    "block": {"start": "09:00", "end": "11:00"},
    "carried_over": False,
}


def codes(priority, streak=0, context=CONTEXT):
    return [e.split(":")[0] for e in vp.validate(context, priority, streak)]


def bad(**changes):
    p = copy.deepcopy(GOOD)
    p.update(changes)
    return p


def test_good_is_valid():
    assert vp.validate(CONTEXT, GOOD) == []


@pytest.mark.parametrize("changes,expected", [
    ({"date": "2026-09-15"}, ["schema"]),
    ({"carried_over": "no"}, ["schema"]),
    ({"block": {"start": "9am", "end": "11:00"}}, ["schema"]),
    ({"priority": "  "}, ["priority_empty"]),
    ({"priority": "x" * 121}, ["priority_too_long"]),
    ({"priority": "Close the round; hire a designer"}, ["priority_is_list"]),
    ({"priority": "- Close the round"}, ["priority_is_list"]),
    ({"first_step": ""}, ["first_step_empty"]),
    ({"first_step": "y" * 161}, ["first_step_too_long"]),
    ({"why": []}, ["why_count"]),
    ({"why": [GOOD["why"][1]] * 4}, ["why_count"]),
    ({"why": [{"text": "t"}]}, ["why_source"]),
    ({"why": [{"text": "t", "source": "gut:feeling"}]}, ["why_source"]),
    ({"why": [{"text": "t", "source": "file:advice", "quote": "x"}]}, ["file_section_not_found"]),
    ({"why": [{"text": "t", "source": "file:goals"}]}, ["quote_missing"]),
    ({"why": [{"text": "t", "source": "file:goals", "quote": "raise $5M by never"}]}, ["quote_not_in_section"]),
    ({"why": [{"text": "t", "source": "file:goals", "quote": "—"}]}, ["quote_too_short"]),
    ({"why": [{"text": "t", "source": "file:goals", "quote": "Sep 30"}]}, ["quote_too_short"]),
    ({"why": [{"text": "t", "source": "calendar:evt_9"}]}, ["calendar_event_not_found"]),
    ({"block": {"start": "10:00", "end": "12:00"}}, ["block_not_free"]),
    ({"block": {"start": "10:00", "end": "10:00"}}, ["block_not_free"]),
    ({"priority": "Website rebrand project kickoff"}, ["matches_not_now"]),
])
def test_each_rule(changes, expected):
    assert codes(bad(**changes)) == expected


def test_null_block_is_fine():
    assert codes(bad(block=None)) == []


def test_repeated():
    assert codes(GOOD, streak=3) == ["repeated_3_days"]
    assert codes(GOOD, streak=2) == []


def test_short_section_may_be_quoted_whole():
    ctx = copy.deepcopy(CONTEXT)
    ctx["file"]["sections"].append({"id": "rules", "kind": "rules", "heading": "Rules", "text": "Ship it."})
    p = bad(why=[{"text": "t", "source": "file:rules", "quote": "ship it"}])
    assert codes(p, context=ctx) == []


def test_cli_valid_writes_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    run = tmp_path / "desk-priority"
    run.mkdir(parents=True)
    (run / "context.json").write_text(json.dumps(CONTEXT))
    (run / "priority.json").write_text(json.dumps(GOOD))
    vp.main(["--run-dir", str(run)])
    assert capsys.readouterr().out.strip() == "VALID"
    assert json.loads((run / "priority.json").read_text())["notes"] == ["file_empty"]


def test_cli_invalid(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PT_HOME", str(tmp_path))
    run = tmp_path / "desk-priority"
    run.mkdir(parents=True)
    (run / "context.json").write_text(json.dumps(CONTEXT))
    vp.main(["--run-dir", str(run)])
    assert capsys.readouterr().out.splitlines() == ["INVALID", "schema: priority.json unreadable"]
    (run / "priority.json").write_text(json.dumps(bad(priority="")))
    vp.main(["--run-dir", str(run)])
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "INVALID" and out[1].startswith("priority_empty:")
