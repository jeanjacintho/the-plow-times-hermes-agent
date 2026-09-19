"""latch_mcp.py: the one MCP session every pt-* script uses to reach the Mac."""
from __future__ import annotations

import pytest

import latch_mcp as lm
from latch_mcp import LatchError


class TestSettle:
    def test_pending_is_polled_until_ready(self):
        calls = []

        def get_result(handle):
            calls.append(handle)
            if len(calls) < 2:
                return {"status": "pending", "handle": handle}
            return {"status": "ready", "result": {"path": "/Users/jj/Plow/pt/x.b64"}}

        out = lm.settle({"status": "pending", "handle": "h1"}, get_result, sleep=lambda _n: None)
        assert out["path"] == "/Users/jj/Plow/pt/x.b64"
        assert calls == ["h1", "h1"]

    @pytest.mark.parametrize("status", ["denied", "failed", "expired", "blocked"])
    def test_a_refused_call_raises_with_its_status(self, status):
        with pytest.raises(LatchError, match=f"latch {status}"):
            lm.settle({"status": status, "handle": "h"}, lambda _h: {}, sleep=lambda _n: None)


class TestUnwrap:
    def test_a_tool_error_raises_with_its_text(self):
        result = {"isError": True, "content": [
            {"type": "text", "text": "read failed: ENOENT: no such file or directory"}]}
        with pytest.raises(LatchError, match="ENOENT"):
            lm.unwrap_tool_result(result)

    def test_json_text_is_parsed(self):
        result = {"content": [{"type": "text", "text": '{"path": "/Users/jj/a", "content": "x"}'}]}
        assert lm.unwrap_tool_result(result) == {"path": "/Users/jj/a", "content": "x"}
