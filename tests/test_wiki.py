"""wiki.py: the paper's pages in the owner's wiki, checked by the real plow-wiki."""
from __future__ import annotations

from wiki import ROOT, Wiki, join_page, split_page


class TestPageFormat:
    def test_join_then_split_returns_the_same_page(self):
        meta = {"type": "Edition", "priority": {"headline": "Call Raj", "who": ["Raj — cousin"]},
                "time": "10:00"}
        assert split_page(join_page(meta, "# Body\n\n- a\n")) == (meta, "# Body\n\n- a\n")

    def test_a_page_without_frontmatter_is_all_body(self):
        assert split_page("# Just notes\n") == ({}, "# Just notes\n")


class TestWiki:
    def test_a_missing_page_reads_as_none(self, mac):
        assert Wiki(mac.call_tool).read("projects/theplowtimes/nope.md") is None

    def test_a_write_reads_back(self, mac):
        w = Wiki(mac.call_tool)
        w.write(f"{ROOT}/x.md", "hello\n")
        assert w.read(f"{ROOT}/x.md") == "hello\n"
