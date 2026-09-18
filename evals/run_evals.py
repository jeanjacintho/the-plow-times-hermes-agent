#!/usr/bin/env python3
"""Decision-quality scenarios for pt-priority. Calls a model; not part of `just test`.

usage: run_evals.py --model <id> [--only <name>]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request
from datetime import date as Date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pt-shared" / "scripts"))
sys.path.insert(0, str(ROOT / "pt-priority" / "scripts"))
import textnorm  # noqa: E402
import validate_priority  # noqa: E402


def scenario_streak(scenario, priority_text):
    by_date = {e["date"]: e for e in scenario["history"]}
    day, count = Date.fromisoformat(scenario["context"]["today"]), 0
    while True:
        day -= timedelta(days=1)
        entry = by_date.get(day.isoformat())
        if not entry or not textnorm.similar(entry["priority"], priority_text):
            return count
        count += 1


def check(scenario, priority):
    context = dict(scenario["context"], history=scenario["history"])
    text = str(priority.get("priority", ""))
    failures = validate_priority.validate(context, priority, scenario_streak(scenario, text))
    expect, low = scenario["expect"], textnorm.normalize(text)
    if "priority_contains_any" in expect and not any(w in low for w in expect["priority_contains_any"]):
        failures.append(f"expected one of {expect['priority_contains_any']} in '{text}'")
    for word in expect.get("priority_not_contains", []):
        if word in low:
            failures.append(f"'{word}' must not be in '{text}'")
    prefix = expect.get("cites_source_prefix")
    if prefix and not any(str(w.get("source", "")).startswith(prefix) for w in priority.get("why", [])):
        failures.append(f"no why cites {prefix}")
    if expect.get("no_advisor_cite") and any(str(w.get("source", "")).startswith("advisor:") for w in priority.get("why", [])):
        failures.append("must not cite an advisor")
    if expect.get("block_is_null") and priority.get("block") is not None:
        failures.append("block must be null")
    return failures


def prompt_for(scenario):
    skill = (ROOT / "pt-priority" / "SKILL.md").read_text()
    body = skill[skill.index("## Choose, in this order"):skill.index("## Validate")]
    context = dict(scenario["context"], history=scenario["history"])
    return (body + "\n\nLANG is English. DATE is " + context["today"] +
            ".\n\ncontext.json:\n" + json.dumps(context, indent=2) +
            "\n\nReply with only the priority.json object.")


def ask_model(model, prompt):
    if os.environ.get("ANTHROPIC_API_KEY"):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps({"model": model, "max_tokens": 1024,
                             "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        reply = json.load(urllib.request.urlopen(req, timeout=120))["content"][0]["text"]
    else:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                     "content-type": "application/json"})
        reply = json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    return json.loads(match.group(0)) if match else {}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--only")
    args = parser.parse_args(argv)
    files = sorted((ROOT / "evals" / "scenarios").glob("*.json"))
    passed = 0
    for path in files:
        scenario = json.loads(path.read_text())
        if args.only and scenario["name"] != args.only:
            continue
        failures = check(scenario, ask_model(args.model, prompt_for(scenario)))
        if failures:
            print(f"FAIL {scenario['name']}: " + " | ".join(failures))
        else:
            passed += 1
            print(f"PASS {scenario['name']}")
    print(f"{passed}/{len(files)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
