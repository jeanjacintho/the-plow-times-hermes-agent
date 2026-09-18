from conftest import ROOT, load_module

pa = load_module("parse_advisors", "pt-priority/scripts/parse_advisors.py")
FIX = ROOT / "tests" / "fixtures" / "advisors"


def test_parses_frontmatter_and_sections():
    out = pa.parse([{"name": "blueprint.md", "text": (FIX / "blueprint.md").read_text()}])
    a = out["advisors"][0]
    assert a["advisor"] == "Patrick Salyer (Mayfield)"
    assert a["stages"] == ["blueprint"] and a["domain"] == "b2b-saas-enterprise"
    kinds = {s["kind"]: s["id"] for s in a["sections"]}
    assert set(kinds) == {"signals", "focus", "avoid", "benchmarks", "exit"}
    assert out["errors"] == []


def test_file_without_frontmatter_is_an_error_not_a_crash():
    out = pa.parse([{"name": "loose.md", "text": "# Notes\nsomething"}])
    assert out["advisors"] == [] and out["errors"] == ["loose.md: no frontmatter"]


def test_stages_list_and_any():
    out = pa.parse([{"name": "x.md", "text": "---\nadvisor: A\nstages: pivot, any\n---\n## Focus first\n- Move\n"}])
    assert out["advisors"][0]["stages"] == ["pivot", "any"]
