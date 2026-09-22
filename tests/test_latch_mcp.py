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
            return {"status": "ready", "result": {"path": "/Users/test-owner/Plow/pt/x.b64"}}

        out = lm.settle({"status": "pending", "handle": "h1"}, get_result, sleep=lambda _n: None)
        assert out["path"] == "/Users/test-owner/Plow/pt/x.b64"
        assert calls == ["h1", "h1"]

    @pytest.mark.parametrize("status", ["denied", "failed", "expired", "blocked"])
    def test_a_refused_call_raises_with_its_status(self, status):
        with pytest.raises(LatchError, match=f"latch {status}"):
            lm.settle({"status": status, "handle": "h"}, lambda _h: {}, sleep=lambda _n: None)

    def test_a_blocked_call_carries_the_owner_action(self):
        blocked = {"status": "blocked", "diagnosis": {"owner_action": "Click Allow"}}
        with pytest.raises(LatchError, match="latch blocked: Click Allow"):
            lm.settle(blocked, lambda _h: {}, sleep=lambda _n: None)


class TestDecodeBody:
    @pytest.mark.parametrize("raw", [b"", b'{"jsonrpc": "2.0", "id": 1}', b"null", b'"result"'])
    def test_a_reply_with_no_result_or_error_is_refused(self, raw):
        with pytest.raises(LatchError, match="no result"):
            lm.decode_mcp_body("application/json", raw)

    def test_a_normal_reply_is_returned(self):
        body = b'{"jsonrpc":"2.0","id":1,"result":{"path":"/Users/test-owner/a"}}'
        assert lm.decode_mcp_body("application/json", body) == {
            "jsonrpc": "2.0", "id": 1, "result": {"path": "/Users/test-owner/a"},
        }


class TestUnwrap:
    def test_a_tool_error_raises_with_its_text(self):
        result = {"isError": True, "content": [
            {"type": "text", "text": "read failed: ENOENT: no such file or directory"}]}
        with pytest.raises(LatchError, match="ENOENT"):
            lm.unwrap_tool_result(result)

    def test_json_text_is_parsed(self):
        result = {"content": [{"type": "text", "text": '{"path": "/Users/test-owner/a", "content": "x"}'}]}
        assert lm.unwrap_tool_result(result) == {"path": "/Users/test-owner/a", "content": "x"}


class TestFinishCommand:
    @pytest.mark.parametrize("polled", [
        {"status": "blocked", "diagnosis": {"owner_action": "Click Allow"}},
        {"status": "blocked", "exit_code": 1, "diagnosis": {"owner_action": "Click Allow"}},
    ])
    def test_a_terminal_blocked_poll_reports_its_owner_action(self, polled):
        running = {"status": "running", "handle": "j"}
        with pytest.raises(LatchError, match="lp outcome unknown: Click Allow"):
            lm.finish_command(lambda *_: polled, running, "lp")

    def test_a_diagnosed_running_job_reports_its_owner_action(self):
        parked = {"status": "running", "handle": "j", "diagnosis": {"owner_action": "Click Allow"}}
        with pytest.raises(LatchError, match="lp outcome unknown: Click Allow"):
            lm.finish_command(lambda *_: {}, parked, "lp")


class TestConnect:
    """Which credential this install reaches the Mac with.

    A self-hosted install pastes a static DOMO_* pair into the home's .env; a
    Plow-hosted install never gets one, and used to fail every print on the
    missing variable. It derives its own relay URL instead.
    """

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for name in ("DOMO_DEVICE_UID", "DOMO_MCP_TOKEN", "PLOW_AGENT_TOKEN",
                     "PLOW_API_BASE"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("PLOW_API_BASE", "https://api.example")

    def test_a_static_pair_builds_its_own_device_url(self, monkeypatch):
        monkeypatch.setenv("DOMO_DEVICE_UID", "dev-1")
        monkeypatch.setenv("DOMO_MCP_TOKEN", "static-token")
        # Nothing may be fetched when the pair is present.
        monkeypatch.setattr(lm, "get_json", lambda *a, **k: pytest.fail("fetched"))

        client = lm.connect()

        assert client.url == "https://api.example/v1/relay/devices/dev-1/mcp"
        assert client.token == "static-token"

    def test_without_a_pair_it_derives_the_url_from_its_own_identity(self, monkeypatch):
        monkeypatch.setenv("PLOW_AGENT_TOKEN", "agent-token")
        seen = {}

        def fake_get(base, path, token, label):
            seen.update(base=base, path=path, token=token)
            # Verbatim, and deliberately NOT the shape connect() would build:
            # a proxied agent is handed a proxied URL.
            return {"mcp_url": "https://proxy.example/v1/relay/devices/usr-9/mcp"}

        monkeypatch.setattr(lm, "get_json", fake_get)

        client = lm.connect()

        assert seen == {"base": "https://api.example",
                        "path": "/v1/agents/me",
                        "token": "agent-token"}
        assert client.url == "https://proxy.example/v1/relay/devices/usr-9/mcp"
        assert client.token == "agent-token"

    @pytest.mark.parametrize("identity", [
        {"mcp_url": None},      # credential lacks relay:call
        {"mcp_url": "  "},
        {},
        "not an object",
    ])
    def test_no_url_means_this_credential_cannot_call_the_relay(self, monkeypatch, identity):
        monkeypatch.setenv("PLOW_AGENT_TOKEN", "agent-token")
        monkeypatch.setattr(lm, "get_json", lambda *a, **k: identity)

        with pytest.raises(LatchError, match="relay"):
            lm.connect()

    def test_a_half_pair_is_not_a_pair(self, monkeypatch):
        # Only one of the two set: fall through to the derived URL rather than
        # refusing, which is what used to happen.
        monkeypatch.setenv("DOMO_DEVICE_UID", "dev-1")
        monkeypatch.setenv("PLOW_AGENT_TOKEN", "agent-token")
        monkeypatch.setattr(
            lm, "get_json",
            lambda *a, **k: {"mcp_url": "https://api.example/v1/relay/devices/usr-9/mcp"},
        )

        assert lm.connect().token == "agent-token"
