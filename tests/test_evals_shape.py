import json

from conftest import ROOT, load_module

ev = load_module("run_evals", "evals/run_evals.py")
vp = load_module("validate_priority", "pt-priority/scripts/validate_priority.py")


def scenarios():
    return sorted((ROOT / "evals" / "scenarios").glob("*.json"))


def test_six_scenarios_with_valid_context_shape():
    files = scenarios()
    assert len(files) == 6
    for path in files:
        s = json.loads(path.read_text())
        assert {"name", "context", "history", "expect"} <= set(s)
        assert vp.validate(s["context"], {"date": "x"}) != []


def test_check_catches_expectations():
    s = json.loads((ROOT / "evals/scenarios/02-not-now.json").read_text())
    bad = {"date": s["context"]["today"], "priority": "Launch the website rebrand",
           "why": [{"text": "t", "source": "calendar:none"}], "first_step": "x",
           "block": None, "carried_over": False}
    failures = ev.check(s, bad)
    assert any("rebrand" in f for f in failures)
