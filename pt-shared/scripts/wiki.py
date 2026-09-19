"""wiki.py -- The Founder Times' pages in the owner's wiki, over Latch.

The wiki is plow-wiki: an Obsidian vault at ~/Plow/wiki in OKF v0.2, kept by
the `wiki` plugin Latch bundles. The paper owns one root,
projects/theplowtimes (writer `theplowtimes`, this agent's AGENT_ID), and
shares one page, entities/owner/goals.md. Pages move with plow_read_file and
plow_write_file (no approval inside ~/Plow); the CLI runs through
plow_run_command, under whatever approval mode the Mac is in.
"""
from __future__ import annotations

import yaml

from latch_mcp import LatchError
from latch_mcp import connect as latch_connect

WIKI = "~/Plow/wiki"
WRITER = "theplowtimes"
ROOT = f"projects/{WRITER}"
OVERVIEW = f"{ROOT}/{WRITER}.md"
QA = f"{ROOT}/qa.md"
GOALS = "entities/owner/goals.md"
SCHEMA = f"_meta/schemas/{ROOT}.md"


def split_page(text):
    """(frontmatter, body) of an OKF page; a page without frontmatter is ({}, text)."""
    if not text.startswith("---\n"):
        return {}, text
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        return {}, text
    return yaml.safe_load(head) or {}, body


def join_page(meta, body):
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{head}---\n{body}"


class Wiki:
    def __init__(self, call_tool):
        self._call = call_tool

    def read_path(self, path):
        """A file's text on the Mac, or None when it does not exist."""
        try:
            return self._call("plow_read_file", {"path": path})["content"]
        except LatchError as exc:
            if "ENOENT" in str(exc):
                return None
            raise

    def read(self, rel):
        return self.read_path(f"{WIKI}/{rel}")

    def write(self, rel, text):
        self._call("plow_write_file", {"path": f"{WIKI}/{rel}", "content": text})

    def run(self, *args, write=False):
        """`wiki <args>` through Latch's wiki plugin: (exit_code, output)."""
        params = {"argv": ["wiki", *args], "wait_ms": 60000,
                  "goal": f"Keep The Founder Times' pages in your wiki (wiki {args[0]})"}
        if write:
            params["write_paths"] = [WIKI]
        result = self._call("plow_run_command", params)
        if not isinstance(result, dict) or "exit_code" not in result:
            raise LatchError(f"wiki {args[0]} did not finish: {result}")
        return int(result["exit_code"]), str(result.get("output") or "")


def connect():
    return Wiki(latch_connect().call_tool)
