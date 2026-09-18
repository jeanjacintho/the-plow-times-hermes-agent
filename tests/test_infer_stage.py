import pytest

from conftest import load_module

ppf = load_module("parse_priority_file", "pt-priority/scripts/parse_priority_file.py")
infer = load_module("infer_stage", "pt-priority/scripts/infer_stage.py")

CASES = [
    ("## Company state\nARR: $2.4M. 7 referenceable customers. Two reps.", "blueprint", []),
    ("## Company state\n$0 revenue, 2 design partners, I do all the selling.", "discovery", []),
    ("## Company state\nARR $14M, 9 reps ramped, I am the bottleneck.", "scale", []),
    ("## Company state\nARR $6M but we are doing a down round and missed Q2.", "pivot", []),
    ("## Company state\nARR $2M and raising a Series A now.", "blueprint", ["fundraising"]),
    ("## Company state\nWe are a consumer app with 40k users.", "unknown", []),
]


@pytest.mark.parametrize("text,stage,mods", CASES)
def test_stage_inference(text, stage, mods, tmp_path):
    parsed = ppf.parse(text)
    out = infer.infer(parsed)
    assert out["stage"] == stage and out["modifiers"] == mods


def test_consumer_domain_is_flagged():
    out = infer.infer(ppf.parse("## Company state\nPLG self-serve, $300k ARR."))
    assert out["domain"] == "consumer-plg" and out["stage"] == "discovery"
