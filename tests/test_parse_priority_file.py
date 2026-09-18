import json

from conftest import ROOT, load_module

ppf = load_module("parse_priority_file", "pt-priority/scripts/parse_priority_file.py")
FIX = ROOT / "tests" / "fixtures" / "priority"


def by_id(result):
    return {s["id"]: s for s in result["sections"]}


def test_missing():
    assert ppf.parse(None) == {"status": "missing", "truncated": False, "sections": []}


def test_bom_and_crlf():
    r = ppf.parse("\ufeff## Goals\r\nShip it\r\n")
    assert r["sections"] == [{"id": "goals", "kind": "goals", "heading": "Goals", "text": "Ship it"}]


def test_template_only_is_empty():
    r = ppf.parse((FIX / "template.md").read_text())
    assert r["status"] == "empty" and r["sections"] == []


def test_full_file_sections_and_kinds():
    r = ppf.parse((FIX / "full.md").read_text())
    s = by_id(r)
    assert r["status"] == "ok"
    assert list(s) == ["what-i-should-be-working-on", "goals", "projects-deadlines",
                       "advice-i-trust", "minhas-regras", "not-now", "random"]
    assert s["goals"]["kind"] == "goals"
    assert s["projects-deadlines"]["kind"] == "projects"
    assert s["advice-i-trust"]["kind"] == "advice"
    assert s["minhas-regras"]["kind"] == "rules"
    assert s["not-now"]["kind"] == "not_now"
    assert s["random"]["kind"] == "other"
    assert "### sub heading stays text" in s["random"]["text"]


def test_title_heading_with_text_is_kept_as_section():
    # "# What I should be working on" has text under it in full.md, so it is a section.
    s = by_id(ppf.parse((FIX / "full.md").read_text()))
    assert s["what-i-should-be-working-on"]["text"] == "I run a seed-stage fintech."


def test_bare_title_is_dropped_and_preamble_kept():
    r = ppf.parse("Just some notes up top.\n\n# Title\n## Goals\nShip it.\n")
    assert [x["id"] for x in r["sections"]] == ["preamble", "goals"]


def test_no_headings_is_one_preamble():
    r = ppf.parse("Focus on revenue. Talk to users.")
    assert r["sections"] == [{"id": "preamble", "kind": "other", "heading": "",
                              "text": "Focus on revenue. Talk to users."}]


def test_comments_removed_multiline():
    r = ppf.parse("## Goals\n<!-- a\nb -->\nReal goal\n")
    assert by_id(r)["goals"]["text"] == "Real goal"


def test_duplicate_ids():
    r = ppf.parse("## Goals\nA\n## Goals\nB\n")
    assert [x["id"] for x in r["sections"]] == ["goals", "goals-2"]


def test_truncation():
    r = ppf.parse("## Goals\n" + "é" * 40000)
    assert r["truncated"] is True
    assert len(json.dumps(r["sections"][0]["text"], ensure_ascii=False).encode()) <= ppf.MAX_BYTES + 2


def test_cli(tmp_path, capsys):
    out = tmp_path / "file.json"
    ppf.main([str(FIX / "full.md"), str(out)])
    assert capsys.readouterr().out.strip() == "FILE:ok SECTIONS:7"
    ppf.main([str(tmp_path / "nope.md"), str(out)])
    assert json.loads(out.read_text())["status"] == "missing"
